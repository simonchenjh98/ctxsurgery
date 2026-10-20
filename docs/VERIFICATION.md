# v0.1 local verification — 2026-09-22

Environment: Windows, Python 3.12.4. No real model API key was configured and no paid model call was made.

## Completed

- Full local suite: **159 passed**, including case validation, strict evaluators, raw snapshot preservation, lexical candidates, hard call budgets, provider errors, HTML escaping, CLI integration, and public-import integrity checks.
- Exhaustive check over all 64 three-fragment Boolean functions with an original PASS and empty FAIL: every returned repair passes and every single-fragment ablation fails. This tests deterministic search correctness, not stochastic model reliability.
- Actual localhost HTTP integration: CLI → chat-completions adapter → engine → JSON/HTML report; checked successful diagnosis and HTTP failure handling. Remote vendor compatibility was not inferred from this test.
- Built a dependency-free wheel with local setuptools, installed it into a fresh project-local virtual environment, and ran the installed console script. Import resolved from the environment's site-packages, not the source directory.
- Installed offline demo: `localized`, `1-minimal`, **30 calls / 10 arms / 3 trials per arm**. Final repair is `ci-gate` plus `approval-gate`; `release-note` is excluded. Both leave-one-out restorations fail; the matching filler fails.
- Public Dynamic Cheatsheet importer: fetched the fixed commit, verified the full-file SHA256, and extracted memory-only before/after snapshots. 689 → 329 whitespace-delimited words; static lexical diff identified 15 candidate paragraphs. This is not a causal diagnosis.
- Opened the generated HTML in the local browser and visually checked the report. Synthetic provenance, experiment counts, repair IDs and evidence limits are visible.
- Scoped source scan found no user-machine paths or common API-token patterns. This is a basic check, not a comprehensive security audit.

## Reproduce

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ctxsurgery demo --out artifacts/demo
python scripts/import_public_example.py --out artifacts/public-example
python -m ctxsurgery diff artifacts/public-example/before.txt artifacts/public-example/after.txt --out artifacts/public-example/candidates.json
python -m build
```

The public import command performs a network download; the tests and demo do not require an external model. On the development host, pytest/pip temporary-directory creation required execution outside the Windows agent sandbox; the suite itself completed normally there.

## Not yet established

- Effectiveness on a live model or a collection of real production regressions.
- Statistical confidence, globally minimum repairs, or token-matched controls.
- Remote GitHub Actions results: a Windows/Linux Python 3.10/3.12/3.13 matrix is configured but has not run remotely.
- GitHub/PyPI publication, package-name availability, or distribution/usage metrics.

Generated reports, public downloads, test temporary directories, built artifacts and the virtual environment are ignored by Git. Private cases were not imported.

## Publication preflight — 2026-10-21

The full local suite was rerun before publication: **159 passed in 2.94 seconds**. This run required permission to reach the local HTTP test server outside the agent sandbox; it made no real model calls. The September results above are retained as a dated historical record. Publication and remote CI status should be checked on the linked GitHub repository, not inferred from the old verification date.
