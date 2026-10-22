# Reviewed live-experiment evidence — 2026-10-22

See [the methods and rerun guide](../../live-context-cases.md) for the task
definitions, source attribution, settings, selection limits and full results.

| Directory | Attempted generations | Result |
| --- | ---: | --- |
| `cedar-01` | 2 | Empty summary; incomplete |
| `cedar-02` | 5 | Provider error during baseline; incomplete |
| `cedar-03` | 3 | Two connection errors during baseline; incomplete |
| `cedar-04` | 6 | Original and unchanged summary both pass 3/3 |
| `archived-probe` | 27 | Task-local helper restoration; tested 1-minimal at chosen granularity |

Total: **43 attempted generations**, including **3 provider/connection errors**.
The available usage records sum to **73,198 tokens**. Three calls have missing
usage; this sum is not complete billing usage or a price estimate. Six separate
credential-free HTTP connectivity probes generated no model completions.

Cedar inputs are original fictional engineering material. Its records include
all attempted generations, not just the final completed run. The frozen case
in `cedar-02/case.json` is reused without editing in the third and fourth runs.

The archived probe's JSON and HTML reports redact all candidate text and trial
outputs. The raw upstream memories, source-derived cases and request ledger are
not redistributed here. Recreate the inputs using the pinned importer and run
the explicit opt-in probe to obtain locally inspectable evidence. This is a
new targeted retrieval task, not a replay or repair of the original benchmark.

The final runs used a process-local `NO_PROXY` entry for `api.stepfun.com` after
local proxy failures were observed. This route adjustment is documented in the
methods guide; no global proxy or TLS verification setting was changed.

Source-code hashes in provenance identify the implementation used for each run.
Early pilots did not record every metadata field introduced later. Their files
are preserved as originally produced; missing values have not been invented.
