"""Opt-in live retrieval probe on pinned, public archived memory snapshots.

This is a NEW task selected after inspecting a known omission, not an AIME
replay or a production incident. No download or model call happens on import.
Raw source-derived records remain local; review content terms before sharing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from ctxsurgery.engine import diagnose
from ctxsurgery.models import Case
from ctxsurgery.providers import OpenAICompatibleRunner
from ctxsurgery.report import render_html
from import_public_example import SOURCE_COMMIT, SOURCE_SHA256, SOURCE_URL
from run_live_case import RecordedRunner, implementation_hashes, write_json


BEFORE_SHA256 = "3cc6d3194ea2be7a7baaadc8e086a5895c7b9b10c6165b56261bcf2efb6c4cb9"
AFTER_SHA256 = "1b617ddcd3cc9c8dc863d0eefe196f2810510576ae31be621a280f236d8a2ab8"
TASK = (
    "Read only the supplied archived memory. What are the exact default values "
    "of the t_range and points parameters in its Python function find_min_max_value? "
    "Return only JSON with exactly two keys: t_range (a two-element array, or null "
    "if the default is absent) and points (an integer, or null if the default is "
    "absent). A placeholder saying previous content is preserved does not provide "
    "that content. Do not infer defaults from typical numerical code or outside "
    "knowledge; use null for each missing default. Do not execute any code."
)
EXPECTED = {"t_range": [-5, 5], "points": 1000}
LIMITATIONS = [
    "Exploratory retrieval probe selected after inspecting a known omission; not an independently sampled benchmark.",
    "The task is new. It is not the original AIME question, an AIME answer repair, or a production incident.",
    "The two archived memories are unchanged. Three coarse fragments were manually defined around the known helper section.",
    "A repair concerns exact retrieval of two defaults only, not mathematical correctness or general memory quality.",
    "The model may guess the defaults even when absent; such an after-context pass must not be suppressed.",
    "Three sequential repeats are descriptive, not a significance test. Filler is character-matched, not token-matched.",
]


def split_before(before: str) -> list[dict]:
    blocks = [match for match in re.finditer(r"<memory_item>.*?</memory_item>", before, re.DOTALL)
              if "def find_min_max_value(" in match.group()]
    if len(blocks) != 1:
        raise ValueError("Expected exactly one archived helper section.")
    start, end = blocks[0].span()
    if before[start - 2:start] != "\n\n" or before[end:end + 2] != "\n\n":
        raise ValueError("Unexpected archived section boundaries.")
    fragments = [
        {"id": "memory-prefix", "text": before[:start - 2]},
        {"id": "hyperbola-helper", "text": before[start:end]},
        {"id": "memory-suffix", "text": before[end + 2:]},
    ]
    if not all(fragment["text"].strip() for fragment in fragments):
        raise ValueError("Expected nonempty prefix, helper and suffix.")
    if "\n\n".join(fragment["text"] for fragment in fragments) != before:
        raise ValueError("Fragmentation changed the original context.")
    return fragments


def load_case(source: Path) -> Case:
    texts = []
    for name, expected_hash in (("before.txt", BEFORE_SHA256), ("after.txt", AFTER_SHA256)):
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError(f"Pinned {name} checksum mismatch; no live call was made.")
        texts.append(raw.decode("utf-8"))
    before, after = texts
    return Case.from_dict({
        "version": 1, "name": "Archived memory: newly authored helper-default retrieval probe",
        "before": split_before(before), "after": after, "task": TASK,
        "evaluator": {"type": "json", "expected": EXPECTED},
    })


def run_probe(runner, source: Path, directory: Path, *, model: str, base_url: str,
              max_calls=30, repeats=3) -> dict:
    if type(max_calls) is not int or not 1 <= max_calls <= 48:
        raise ValueError("max_calls must be an integer from 1 to 48.")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be positive.")
    case = load_case(source)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "case.json", case.to_dict())
    metadata = {
        "kind": "new_retrieval_probe_on_public_archived_model_memories",
        "production_incident": False, "original_benchmark_task": False,
        "source_url": SOURCE_URL, "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "before_sha256": BEFORE_SHA256, "after_sha256": AFTER_SHA256,
        "source_record_index_zero_based": 28,
        "task_selection": "targeted_after_inspecting_known_missing_helper",
        "fragmentation": "three_coarse_groups_around_complete_helper_memory_item",
        "snapshots_edited": False, "model": model, "base_url": base_url,
        "temperature": 0, "reasoning_effort": getattr(runner, "reasoning_effort", None),
        "max_output_tokens": getattr(runner, "max_output_tokens", None),
        "timeout_seconds": getattr(runner, "timeout", None),
        "max_calls": max_calls, "repeats": repeats, "calls_used": 0,
        "status": "started", "limitations": LIMITATIONS,
        "implementation_sha256": {
            **implementation_hashes(),
            "scripts/run_archived_probe.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    write_json(directory / "provenance.json", metadata)
    logged = RecordedRunner(runner, directory, max_calls)
    logged.stage = "archived-retrieval-diagnosis"
    result = diagnose(case, logged, repeats=repeats, max_calls=max_calls)
    result["run"] = {
        "provider": "openai-compatible", "model": model, "synthetic": False,
        "task_origin": metadata["kind"], "production_incident": False,
        "original_benchmark_task": False, "reasoning_effort": metadata["reasoning_effort"],
        "max_output_tokens": metadata["max_output_tokens"],
        "timeout_seconds": metadata["timeout_seconds"],
    }
    result["limitations"] = LIMITATIONS + result["limitations"]
    write_json(directory / "report.json", result)
    (directory / "report.html").write_text(render_html(result), encoding="utf-8")
    metadata.update({key: result[key] for key in ("status", "calls_used", "minimality", "repair_ids")})
    write_json(directory / "provenance.json", metadata)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Output from import_public_example.py.")
    parser.add_argument("--out", type=Path, required=True, help="Fresh local output directory.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--max-calls", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=16384)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"))
    args = parser.parse_args(argv)
    runner = OpenAICompatibleRunner(
        model=args.model, base_url=args.base_url, api_key=os.environ.get(args.api_key_env),
        timeout=args.timeout, max_output_tokens=args.max_output_tokens,
        reasoning_effort=args.reasoning_effort,
    )
    result = run_probe(runner, args.source, args.out, model=args.model,
                       base_url=runner.base_url, max_calls=args.max_calls, repeats=args.repeats)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result["status"] in {"runner_error", "budget_exhausted"} else 0


if __name__ == "__main__":
    sys.exit(main())
