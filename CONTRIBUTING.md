# Contributing

Thank you for helping make context regressions easier to investigate.

## Development setup

Python 3.10+ is required. The core package has no runtime dependencies.

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Run the offline demo before changing CLI output or HTML reports:

```sh
ctxsurgery demo --out artifacts/demo
```

Open `artifacts/demo/report.html` at a narrow and wide viewport. The report must remain usable offline, with no external assets or scripts.

## Useful contributions

- Small, reproducible context-regression cases with explicit assertions.
- Incorrect attribution, incomplete-budget, runner-error and non-monotonic-interaction edge cases.
- Provider compatibility improvements tested with local mock endpoints.
- Clearer evidence displays, accessible HTML and honest uncertainty labels.
- Documentation that helps users design better task-specific evaluators.

Discuss changes to experiment semantics, file schemas or new runtime dependencies before implementing a broad redesign. The current scope is snapshot-level restoration diagnosis, not a tracing backend or agent framework.

## Pull requests

1. Explain the failure or user need and the proposed behavior.
2. Add a regression test. Normal tests must run without API keys or network access.
3. Run the full test suite and include the result.
4. Update documentation if the CLI, schema or interpretation changes.
5. Keep the patch focused. Note AI assistance when relevant and verify generated code and tests yourself.

Do not commit keys, private prompts, proprietary traces, personal data or unredacted live reports. Sanitize a minimal reproduction instead. If the reproduction cannot be safely shared, describe its structure without attaching the original data.

## Evidence standards

- Label deterministic/synthetic fixtures explicitly; never present them as live model measurements.
- Provider failures are errors, not failed task assertions.
- Account for every call, including exceptions, against the budget.
- Distinguish `1-minimal` from globally minimum. Do not claim statistical significance from a pass threshold.
- Do not silently cache repeated trials or share state between experimental arms.
- Match claims to the actual evaluator and intervention, including character—not token—matched filler.
- Escape all untrusted content in reports; keep credentials out of outputs and exceptions.

Contributions are accepted under the repository's MIT license. Include attribution and license information for any third-party fixture or code you propose to add.
