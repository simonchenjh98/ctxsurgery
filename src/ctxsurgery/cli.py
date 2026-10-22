"""Command-line interface. Run ``python -m ctxsurgery --help``."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def _read_text(path: str) -> str:
    with Path(path).open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Input exceeds the 4 MiB file limit.")
    return raw.decode("utf-8-sig")


def _read_json(path: str):
    return json.loads(_read_text(path))


def _write_text(path: Path, text: str):
    """Replace a complete output atomically; leave no partial report on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".ctxsurgery-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def redact_result(result: dict) -> dict:
    """Redact saved prompt fragments, outputs, errors, and case name.

    This is output redaction, not a promise to anonymize arbitrary user metadata.
    It does not change what is sent to a selected model endpoint.
    """
    result = copy.deepcopy(result)

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("text", "output", "error", "case_name") and item is not None:
                    value[key] = "[REDACTED]"
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result)
    result["redacted"] = True
    return result


def _save_result(result: dict, destination: str, redact: bool):
    from .report import render_html

    saved = redact_result(result) if redact else result
    encoded = json.dumps(saved, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    html = render_html(saved)
    out = Path(destination)
    _write_text(out / "report.json", encoded)
    _write_text(out / "report.html", html)


def _add_experiment_arguments(parser):
    parser.add_argument("--out", required=True, help="Directory for report.json and report.html")
    parser.add_argument("--repeats", type=int, default=3, help="Fresh runner calls per experimental arm (default: 3)")
    parser.add_argument("--max-calls", type=int, default=96, help="Hard total runner-call budget (default: 96)")
    parser.add_argument("--pass-threshold", type=float, default=1.0)
    parser.add_argument("--max-candidates", type=int, default=24)
    parser.add_argument("--redact", action="store_true", help="Redact fragment text, outputs, errors, and name in saved reports; not endpoint inputs")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ctxsurgery", description="Controlled restoration experiments for lost LLM context."
    )
    parser.add_argument("--version", action="version", version="ctxsurgery 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run a free, deterministic synthetic example (not LLM evidence)")
    _add_experiment_arguments(demo)
    diff = commands.add_parser("diff", help="Find candidate fragments missing from two UTF-8 text files")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--out", help="Write JSON to a file instead of stdout")
    diagnosis = commands.add_parser(
        "diagnose", help="Run a case against an explicitly selected OpenAI-compatible endpoint"
    )
    diagnosis.add_argument("case")
    diagnosis.add_argument("--provider", required=True, choices=("openai",))
    diagnosis.add_argument("--model", required=True)
    diagnosis.add_argument("--base-url", default="https://api.openai.com/v1")
    diagnosis.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable name, never the secret itself")
    diagnosis.add_argument("--timeout", type=float, default=30.0)
    diagnosis.add_argument("--max-output-tokens", type=int, default=1024)
    diagnosis.add_argument("--reasoning-effort", choices=("low", "medium", "high"), help="Optional reasoning effort; omitted by default. Requires endpoint support.")
    _add_experiment_arguments(diagnosis)
    report = commands.add_parser("report", help="Render saved result JSON as self-contained HTML")
    report.add_argument("result_json")
    report.add_argument("--out", required=True, help="Destination HTML file")
    report.add_argument("--redact", action="store_true")
    return parser


def _run_diagnosis(args):
    from .engine import diagnose

    if args.command == "demo":
        from .demo import demo_case, synthetic_runner

        case = demo_case()
        runner = synthetic_runner
        run = {"provider": "synthetic", "model": "deterministic-config-interpreter", "synthetic": True}
    else:
        from .models import Case
        from .providers import OpenAICompatibleRunner

        case = Case.from_dict(_read_json(args.case))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.api_key_env):
            raise ValueError("API key environment variable name is invalid.")
        runner = OpenAICompatibleRunner(
            model=args.model,
            base_url=args.base_url,
            api_key=os.environ.get(args.api_key_env),
            timeout=args.timeout,
            max_output_tokens=args.max_output_tokens,
            reasoning_effort=args.reasoning_effort,
        )
        run = {"provider": "openai-compatible", "model": args.model, "synthetic": False}
        if args.reasoning_effort is not None:
            run["reasoning_effort"] = args.reasoning_effort
        print("Live run: case context and task will be sent to the selected endpoint. Calls may incur charges.", file=sys.stderr)
    result = diagnose(
        case,
        runner,
        repeats=args.repeats,
        max_calls=args.max_calls,
        pass_threshold=args.pass_threshold,
        max_candidates=args.max_candidates,
    )
    result["run"] = run
    _save_result(result, args.out, args.redact)
    print(f"Status: {result['status']}; calls: {result['calls_used']}/{result['max_calls']}")
    if run["synthetic"]:
        print("Synthetic deterministic fixture only; not measured LLM behavior.")
    print(f"Reports: {Path(args.out).resolve() / 'report.html'}")
    return 3 if result["status"] in ("budget_exhausted", "runner_error") else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in ("demo", "diagnose"):
            return _run_diagnosis(args)
        if args.command == "diff":
            from .fragments import diff_snapshots

            data = diff_snapshots(_read_text(args.before), _read_text(args.after))
            encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            if args.out:
                _write_text(Path(args.out), encoded)
            else:
                print(encoded, end="")
            return 0
        from .report import render_html

        result = _read_json(args.result_json)
        if not isinstance(result, dict) or result.get("schema_version") != 1 or not isinstance(result.get("experiments"), list):
            raise ValueError("Expected a schema_version=1 diagnosis result.")
        _write_text(Path(args.out), render_html(redact_result(result) if args.redact else result))
        print(f"Report: {Path(args.out).resolve()}")
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        # Case validation messages may contain user input. Do not echo exception
        # details when --redact is requested, or on any input/configuration error.
        print(f"ctxsurgery: input, configuration, or output error ({type(exc).__name__}); check paths, JSON schema, endpoint and options.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ctxsurgery: interrupted; diagnosis was not completed.", file=sys.stderr)
        return 130
