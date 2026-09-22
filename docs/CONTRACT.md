# MVP implementation contract

Package: `ctxsurgery`; all modules under `src/ctxsurgery`.

## Input

JSON case v1: `{ "version": 1, "name": "...", "before": [{"id":"f1","text":"..."}], "after": "...", "task":"...", "evaluator": {"type":"contains", "all":["..."], "none":["..."]} }`.
`before` may also be a string (split on blank lines); `after` may also be a fragment list. Evaluators: `contains` (case-sensitive substring constraints; at least one assertion), `exact` (`expected`, outer whitespace stripped), `json` (`expected` JSON value compared structurally with strict value types; no markdown fences).

`models.Case.from_dict(data)` -> Case; `.to_dict()` -> input dict. `models.Fragment(id,text)`. Case has `name`, `before` (tuple of Fragment), `after` (str), `task`, `evaluator` (dict); property `original_context` concatenates fragments with two newlines. `fragments.dropped_fragments(case)` -> tuple[Fragment] using whitespace-normalized, case-sensitive exact substring retention (not semantic matching). `fragments.diff_snapshots(before:str, after:str)` -> list of candidate dictionaries with `id`, `text`.

## Execution

`models.Response(output: str, usage: dict | None = None)`.
Runner signature `(context: str, task: str) -> str | Response`, ordinary callable. Error exceptions are caught by engine and become error trials, not negative evidence.
`engine.diagnose(case, runner, *, repeats=3, max_calls=96, pass_threshold=1.0, max_candidates=24)` -> plain JSON-serializable dict.

Result:
```
{
 "schema_version": 1, "case_name": str,
 "status": "localized" | "no_candidates" | "original_not_working" | "already_passing" | "restoration_failed" | "filler_also_repairs" | "budget_exhausted" | "runner_error" | "too_many_candidates" | "inconclusive",
 "summary": str, "repair_ids": [str], "minimality": "1-minimal" | "not-established",
 "candidates": [{"id":str,"text":str}],
 "experiments": [{"id":str,"kind":"before"|"after"|"restore"|"filler","fragment_ids":[str],"context_chars":int,"pass_rate":float,"valid":bool,"trials":[{"index":int,"passed":bool|null,"output":str|null,"error":str|null,"elapsed_ms":float,"usage":dict|null}]}],
 "checks": [{"removed_id":str,"restore_experiment":str,"filler_experiment":str|null,"repair_survives":bool|null}],
 "calls_used":int,"max_calls":int,"repeats":int,"pass_threshold":float,
 "limitations":[str], "elapsed_ms":float
}
```
Do not infer minimality from status alone. Engine does not include credentials, but context candidates and response output may be sensitive. CLI `--redact` must recursively redact candidate text, trial output/error and case name in the saved report (redacts error too because external exceptions can echo inputs). Provider adapter errors must never echo body or request headers. Engine maintains call count for failures too. Live reports must say provider/model selected by user. Offline demo result metadata must clearly say synthetic deterministic runner, NOT measured LLM behavior.

## Report

`report.render_html(result: Mapping) -> str`, zero external assets. CLI writes `report.json` and `report.html` to `--out DIRECTORY`. `result["run"]` optional metadata: `provider`, `model`, `synthetic` bool. Escaping all user-controlled text is mandatory. Never claim live measured behavior for synthetic results.

Implementation refinements: preserve the exact original string for the before arm (including CRLF, blank lines, and indentation); paragraph candidates are separate from this raw baseline. Match word boundaries so `limit=5` is not retained in `limit=50`. Reject duplicate keys at every depth in JSON-evaluated output. Results also record tool version, UTC timestamp, canonical case and snapshot SHA256 values, search strategy, and final restore/filler experiment references. See `METHODOLOGY.md` for evidence limits.

## CLI / provider agent ownership

Own `cli.py`, `providers.py`, `demo.py`, `__main__.py`, provider/CLI tests, `examples/release-guard.json`. Use lazy imports where concurrent modules are pending. CLI commands: `demo --out DIR`, `diff BEFORE AFTER [--out FILE]`, `diagnose CASE --provider openai --model MODEL [--base-url URL] [--api-key-env OPENAI_API_KEY] --out DIR`, `report RESULT_JSON --out HTML_PATH`. Optional `--repeats`, `--max-calls`, `--pass-threshold`, `--redact` on diagnosis/demo. Default provider URL https://api.openai.com/v1; allow loopback http for local models/tests, reject other insecure http and URL userinfo/query/fragments. Configurable timeout. Never require a real API key for synthetic demo. CLI exit 0 for completed diagnostic result including negative findings; 2 for invalid input/config; 3 for budget exhaustion/provider error. Redacted report does NOT stop inputs being sent to an explicitly selected live endpoint; document that.

## Report/docs agent ownership

Own `report.py`, `tests/test_report.py`, README.md, README.zh-CN.md, CONTRIBUTING.md, LICENSE, .github/workflows/tests.yml. Do not edit core, CLI, models, pyproject or examples. Use schema above. README snippets should reflect contracts, and explicitly label heuristic candidate detection, ordered greedy 1-minimal vs global minimum, no statistical guarantee, and character-matched filler vs token-matched placebo. Do not claim novelty or stars. CLI provider requests may carry private prompts: warn.
