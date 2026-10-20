# ctxsurgery

**Find which missing context fragments repair a failing task.**

[中文说明](README.zh-CN.md) · Python 3.10+ · MIT · Alpha

Your agent worked before a context rewrite and fails afterward. A trace shows *what disappeared*. `ctxsurgery` tests *which missing pieces restore the behavior*—and whether adding neutral text produces the same apparent repair.

Give it a before/after context pair, a task, an executable evaluator and a runner. It runs controlled restoration experiments, shrinks the repair, and produces a local JSON ledger plus a self-contained HTML report.

```text
before succeeds → after fails → restore missing fragments → compare filler
                                      ↓
                          remove one fragment at a time
                                      ↓
                           tested 1-minimal repair
```

No dashboard service, database or runtime dependencies. Not a context compressor or a new agent framework.

## Try it in one minute

Clone the repository and run the offline demo:

```sh
git clone https://github.com/simonchenjh98/ctxsurgery.git
cd ctxsurgery
python -m pip install -e .
ctxsurgery demo --out artifacts/demo
```

Open `artifacts/demo/report.html`; the underlying evidence is in `artifacts/demo/report.json`.

The demo runs locally, needs no API key, and uses a **synthetic deterministic runner—not an LLM**. It demonstrates the debugging workflow, not measured model performance. Nothing is published or sent to a model provider by `demo`.

Expected finding: `ci-gate` and `approval-gate` restore the two required release-policy flags; a friendly-title note is removable. The runner is a small configuration interpreter, so the result comes from the context it receives, not a hardcoded diagnosis.

To use the module entry point instead: `python -m ctxsurgery demo --out artifacts/demo`.

## Bring a real case

Save this as `case.json`:

```json
{
  "version": 1,
  "name": "Release approval lost during summarization",
  "before": [
    {"id": "format", "text": "Answer with exactly one uppercase word."},
    {"id": "approval", "text": "A release without explicit approval must be answered BLOCKED."}
  ],
  "after": "Answer with exactly one uppercase word.",
  "task": "The release has no explicit approval. Should it proceed?",
  "evaluator": {"type": "exact", "expected": "BLOCKED"}
}
```

Configure the provider key in your environment, then choose a model available to you:

```sh
ctxsurgery diagnose case.json --provider openai --model YOUR_MODEL --out artifacts/live
```

The default endpoint is `https://api.openai.com/v1`, using `OPENAI_API_KEY`. Model calls may incur charges. Start with an explicit budget:

```sh
ctxsurgery diagnose case.json --provider openai --model YOUR_MODEL --repeats 3 --max-calls 48 --out artifacts/live
```

This example may already pass after context loss: a model can infer sensible release behavior without the missing instruction. In that case, `already_passing` is the correct result, not a failed demo. Use a real regression and an evaluator that captures the behavior you care about.

For a compatible endpoint, use `--base-url https://YOUR_HOST/v1` and optionally `--api-key-env YOUR_KEY_VARIABLE`. HTTPS is required except for loopback HTTP endpoints such as `http://127.0.0.1:8000/v1`. Credentials must stay in environment variables, not case files or command-line key arguments.

Loopback endpoints can run without a key. The initial adapter uses the OpenAI-compatible chat-completions shape (`system` context, `user` task, `temperature=0`, `max_tokens`); models requiring different parameters may need an SDK runner. `--max-output-tokens` defaults to 1024 and `--timeout` to 30 seconds. There are no automatic retries or redirect-following.

### Inspect or re-render without model calls

```sh
ctxsurgery diff before.txt after.txt
ctxsurgery diff before.txt after.txt --out candidates.json
ctxsurgery report artifacts/live/report.json --out artifacts/live/report.html
```

Text snapshots are split on blank lines. Use explicit fragment IDs in JSON when you want stable, meaningful experimental units. `after` also accepts a fragment list.

### A real, archived context-loss example

The optional [Dynamic Cheatsheet example](examples/public-dynamic-cheatsheet.md) imports two public, archived model-produced memory snapshots at a pinned commit. It shows earlier text replaced by previous-content placeholders:

```sh
python scripts/import_public_example.py --out artifacts/public-example
ctxsurgery diff artifacts/public-example/before.txt artifacts/public-example/after.txt
```

The importer explicitly downloads a fixed public source and verifies its checksum; normal installation, tests and `demo` do not download it. This is **static diff evidence only**: no live rerun, no causal diagnosis, and no demonstrated downstream answer repair. Attribution, exact provenance, content-license boundaries and interpretation limits are documented with the example.

### Evaluators

| Type | Configuration | Passing means |
| --- | --- | --- |
| `exact` | `{"type":"exact","expected":"BLOCKED"}` | Exact string equality after trimming outer whitespace |
| `contains` | `{"type":"contains","all":["BLOCKED"],"none":["APPROVED"]}` | All required case-sensitive substrings present; forbidden substrings absent |
| `json` | `{"type":"json","expected":{"allowed":false}}` | Valid JSON, structurally equal with strict value types; no Markdown fences |

A `contains` evaluator must include at least one assertion. These checks are intentionally simple: poor assertions can produce misleading results. Validate your evaluator before diagnosing context loss.

## Python SDK

Wrap your own agent or model as a callable. It receives the context and task and returns a string, or `ctxsurgery.models.Response` with optional usage metadata.

```python
import json
from pathlib import Path

from ctxsurgery.engine import diagnose
from ctxsurgery.models import Case
from ctxsurgery.report import render_html

case = Case.from_dict(json.loads(Path("case.json").read_text(encoding="utf-8")))

def runner(context: str, task: str) -> str:
    # Replace with your own agent/model invocation.
    # Each invocation must start with independent/reset state.
    return your_agent.run(context=context, task=task)

result = diagnose(case, runner, repeats=3, max_calls=48)
Path("report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
Path("report.html").write_text(render_html(result), encoding="utf-8")
print(result["status"], result["repair_ids"], result["minimality"])
```

`your_agent` is your integration, not a bundled dependency. Use a side-effect-free runner: diagnosis makes repeated calls. If an agent can write files, send messages or spend money, isolate it in a sandbox and disable those effects. Reset memory between calls; otherwise experimental arms contaminate one another.

## How to interpret the evidence

1. Candidate detection finds before-fragments not retained as whitespace-normalized exact substrings in the after-context, with word-boundary checks to avoid partial-word matches.
2. Original and reduced contexts establish whether there is a reproducible regression under the selected evaluator.
3. Restoration adds the candidates back. A character-matched neutral-filler arm tests whether adding non-specific text can also repair the result.
4. Ordered greedy deletion checks whether each candidate can be removed while preserving the tested repair criterion.
5. Every fresh runner call, output/error and pass/fail outcome is saved. Errors consume budget and invalidate evidence; they do not count as task failures.

The output records both `status` and `minimality`. Read both. `localized` with `minimality: "1-minimal"` supports a tested repair for this case; it does not identify a unique cause or the globally smallest subset. Inconclusive and negative outcomes are first-class results, including:

- Original context does not pass: no working baseline has been established.
- Reduced context already passes: no regression is demonstrated by this evaluator.
- Restoration fails, or filler also repairs: the proposed explanation is not isolated.
- Runner errors or budget exhaustion: the experiment is incomplete; do not treat it as a negative finding.

CLI exit codes: `0` for completed diagnostics (including negative findings), `2` for invalid input/configuration, `3` for budget exhaustion or runner/provider error.

### Boundaries

- **Heuristic candidates.** Paraphrases may be flagged as missing. Fragment boundaries affect the experiment.
- **1-minimal, not global minimum.** Search order and non-monotonic fragment interactions matter. No exhaustive subset search is claimed.
- **Characters, not tokens.** Neutral filler is matched by character count, not token count. It is not a perfect placebo; prompt position and wording can affect results.
- **No statistical guarantee.** Three repeated samples are not a significance test. A pass threshold is a decision rule, not confidence in causality.
- **Repair is not provenance.** Appending a fragment tests that intervention. It does not recreate the original prompt position, hidden state or all causes of a production failure.
- **Evaluator-dependent.** A successful response can still violate an untested constraint. Use assertions covering the behavior that matters.
- **Not production-trajectory replay.** v0.1 handles a context snapshot plus a task. Tool-state replay, trace imports and semantic matching are not implemented.

## Privacy

`demo`, `diff`, and `report` need no network. Live `diagnose` sends the task and context variants to the endpoint you explicitly select. There is no analytics or report telemetry.

Reports can include proprietary context, model outputs and errors. Add `--redact` to `demo` or `diagnose` to redact case name, candidate text, trial output and error fields in saved reports:

```sh
ctxsurgery diagnose case.json --provider openai --model YOUR_MODEL --redact --out artifacts/redacted
```

**Redaction does not prevent prompts from being sent to the live endpoint.** It is not a general secret scanner. Fragment IDs and other metadata can still be sensitive. Review both JSON and HTML before sharing; do not commit private cases or generated live reports.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution scope and test expectations. The project is an early, deliberately narrow tool: clear evidence and honest failure states matter more than an impressive-looking diagnosis.

Licensed under [MIT](LICENSE).
