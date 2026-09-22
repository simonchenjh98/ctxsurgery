# Context Surgery Implementation Plan

**Goal:** Ship a local-first, installable Python tool that tests whether restoring specific dropped context fragments repairs a task, with length-matched filler controls and honest evidence limits.

**Architecture:** Dependency-free Python SDK and CLI. Explicit JSON cases provide original fragments, compacted context, a task, and a deterministic evaluator. A bounded experiment engine evaluates original/compacted/restored/filler conditions and searches for a deletion-minimal repair. Local HTML and JSON reports preserve errors and uncertainty. An optional OpenAI-compatible HTTP adapter runs real models; an explicitly synthetic offline demo needs no credentials.

**Tech Stack:** Python 3.10+, standard library, pytest for development, setuptools packaging, self-contained HTML.

## Tasks and acceptance criteria

1. Define validated contracts in `src/ctxsurgery/models.py` and fragment comparison in `fragments.py`. Test invalid schemas, exact retention, changed fragments, and Unicode with `python -m pytest tests/test_models.py tests/test_fragments.py`.
2. Implement bounded experiments in `engine.py`. Test original-working admission, compacted failure, restore/filler contrast, interacting fragments, ablation, call budgets, runner errors, and incomplete searches in `tests/test_engine.py`. Errors must never count as valid causal evidence. Call every replicate independently. Describe the result as 1-minimal only after complete ablation checks, never globally minimal.
3. Add `providers.py`, `demo.py`, and `cli.py`. Test offline end-to-end execution and a local HTTP stub; never spend API credits silently. Validate provider URLs and redact credentials from exceptions. Publish no private inputs.
4. Implement `report.py` with a self-contained HTML report, accessible layout, safe HTML escaping, and explicit controls/limitations. Test hostile HTML inputs and incomplete results.
5. Add English README, Chinese quickstart, MIT license, contribution guide, examples, and GitHub Actions. Document synthetic-vs-live evidence and char-vs-token matching clearly.
6. Verify full pytest suite, wheel build/install, console script, demo JSON/HTML, and CLI failure behavior. Review public data licensing before including any external fixture. Open the final report locally and provide runnable commands.

## Scope boundaries

- New independent directory only; preserve the dirty parent workspace and existing paperswipe-atlas.
- No private research logs, API credentials, external telemetry, or automatic publication.
- No causal proof beyond this task/evaluator/model; no statistical significance claim from a few repeats.
- No 1,000-star promise; demonstrate a useful technical wedge first.
