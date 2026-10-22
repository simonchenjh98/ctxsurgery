# Live context experiments: an authored policy and an archived-memory probe

These examples call a real model with explicit opt-in. They do **not** replay a
production incident. The two cases answer different questions and must not be
combined into a single benchmark score.

- **Cedar policy:** does one unedited model-generated handover preserve enough
  information to classify a fixed batch of webhook events?
- **Archived-memory probe:** can a new, deliberately targeted retrieval task
  recover two function defaults from an actual archived memory replacement?

The useful outcome is a recorded result, including a negative or incomplete
one. A connection error is not a wrong model answer. A passing compressed
context is not a repair. All attempted requests count toward the experiment
budget, including unsuccessful requests.

## Recorded results

The first three attempts are incomplete and remain part of the experiment
history. A fourth attempt completed with no reproduced Cedar regression.
They used `step-5-preview` at
`https://api.stepfun.com/step_plan/v1`, temperature zero, and three intended
replicates per diagnosis arm.

| Attempt | Calls attempted | Settings | Observed outcome |
| --- | ---: | --- | --- |
| Cedar 01, 2026-10-21 | 2 | 4,096 output tokens; 60-second timeout; reasoning effort unspecified | Connectivity check returned `OK`; compaction returned empty final content. Reported completion-token usage equalled the cap. No diagnosis ran. |
| Cedar 02, 2026-10-21 | 5 | 16,384 output tokens; 120-second timeout; reasoning effort unspecified | Connectivity and compaction completed; the unedited handover contained 90 whitespace-delimited words. Two original-context trials passed; the third raised a provider error. The baseline was incomplete. |
| Cedar 03, 2026-10-22 | 3 | Frozen Cedar 02 handover; 16,384 output tokens; 120-second timeout; reasoning effort `low` | One original-context trial passed and two had `connection_failed` errors. The baseline was incomplete. |
| Cedar 04, 2026-10-22 | 6 | Same frozen handover and model settings as Cedar 03 | Original context passed 3/3 and the compressed handover passed 3/3, with no request errors. Status: `already_passing`. No restoration or filler trials were needed. |

These Cedar attempts total **16 requests**, not 16 independent successful trials.
Attempt 01 did not retain a finish reason, so its token count alone does not
prove which provider-side termination condition occurred. Attempt 02 retained
only the exception type for its failed call; the precise error cause cannot be
reconstructed from that ledger. Later runs record bounded error codes without
recording exception bodies or credentials.

For Cedar 04, all six trials were fresh, not pooled with earlier passing calls.
The 90-word summary preserved enough information for this fixed batch under
these conditions. This is a **negative result for the context-loss hypothesis**
on this case, not evidence that context compression is always safe.

The archived probe completed on **2026-10-22** with **27 requests and no request
errors**, using `step-5-preview`, temperature zero, reasoning effort `low`, a
16,384 output-token cap, a 120-second timeout, and a 32-call ceiling. Its nine
arms each contained three new calls:

| Arm | Context supplied | Exact default retrieval |
| --- | --- | ---: |
| `e001` | Original archived memory | 3/3 |
| `e002` | Updated archived memory | 0/3 |
| `e003` | Updated memory + all three original fragments | 3/3 |
| `e004` | Updated memory + filler matched to all three fragments | 0/3 |
| `e005` | Updated memory + helper and suffix | 3/3 |
| `e006` | Updated memory + filler matched to helper and suffix | 0/3 |
| `e007` | Updated memory + suffix only | 0/3 |
| `e008` | Updated memory + helper only | 3/3 |
| `e009` | Updated memory + helper-matched filler | 0/3 |

The final retained fragment is `hyperbola-helper`. Removing it leaves the
updated memory alone, so the final ablation check reuses `e002`; it is not an
additional set of observations. The engine reports `localized` and `1-minimal`
at the predefined three-fragment granularity and a 3/3 pass threshold.

The conservative conclusion is: **for this deliberately targeted retrieval
task, appending the known helper section restored retrieval of two exact
defaults, while character-matched filler did not.** All failing arms returned
`null` for both missing defaults, as the task instructed. This measures loss of
recoverable source information, not a reasoning error or inappropriate refusal
by the model. It is not evidence of AIME improvement, broad reliability, or
automatic discovery of unknown failures.

The complete campaign used **43 attempted model-generation requests**: 16
Cedar requests (including incomplete pilots) plus 27 archived-probe requests.
Six credential-free connectivity probes are accounted for separately below.

Reviewed artifacts:

- [Cedar 04 report](results/2026-10-22/cedar-04/report.html) and [JSON](results/2026-10-22/cedar-04/report.json).
- [Archived-probe report, content-redacted](results/2026-10-22/archived-probe/report.html) and [JSON](results/2026-10-22/archived-probe/report.json).
- [Cedar 01 provenance](results/2026-10-22/cedar-01/provenance.json), [Cedar 02 provenance](results/2026-10-22/cedar-02/provenance.json), [Cedar 03 provenance](results/2026-10-22/cedar-03/provenance.json), [Cedar 04 provenance](results/2026-10-22/cedar-04/provenance.json), and [archived-probe provenance](results/2026-10-22/archived-probe/provenance.json).

### Local connectivity diagnosis

Before Cedar 04, six credential-free `GET /models` probes compared this
machine's configured proxy route with a direct route. The three proxy-routed
probes produced two timeouts and one HTTP 401; all three direct probes reached
HTTP 401 in roughly 0.2 seconds. HTTP 401 is expected without credentials and
shows that the HTTP endpoint was reached, not that model generation succeeded.
These requests generated no model completions and are separate from the model
generation counts above.

For the subsequent experiment process only, `api.stepfun.com` was added to
`NO_PROXY`; global proxy settings were left unchanged. Cedar 04 then completed
all six model calls. This is operational troubleshooting evidence, not a
controlled estimate of proxy reliability or proof of the cause of every earlier
error. Do not disable a required proxy by default: investigate your own network
path and organizational requirements before choosing a route.

## Case 1: Cedar webhook handover

`scripts/run_live_case.py` contains an original, fictional engineering policy,
nine fixed event inputs, an exact JSON evaluator, and a fixed summarization
request. Cedar is a training-only integration: no webhook is actually sent.

The policy includes idempotency requirements, retry delays, an HTTP 409
duplicate exception, an `amber` tenant override, and a manual-hold priority
rule. The model is asked for a standalone handover of at most 90 words that
preserves the operational rules. It is **not** instructed to omit a particular
rule. The generated text is used unchanged, even if it exceeds the requested
word target. The inputs and expected answers are not edited after observing
the model's responses.

The frozen fixture hash, covering fragments, task, expected JSON, and both
compaction prompts, is:

```text
877f89d9ea8bf12198e6e20d5fa8d25b75b0bb7ea9a06e2bc513ecc678c478cc
```

### Generate and diagnose a new handover

From the repository root, after installing ctxsurgery, configure an API key in
an environment variable through your normal secret-management mechanism.
Do not paste a key into a case, command history, issue, or report.

```sh
python scripts/run_live_case.py \
  --model step-5-preview \
  --base-url https://api.stepfun.com/step_plan/v1 \
  --api-key-env CTXSURGERY_EXPERIMENT_KEY \
  --out artifacts/cedar-new-run \
  --max-calls 36 \
  --repeats 3 \
  --max-output-tokens 16384 \
  --timeout 120 \
  --reasoning-effort low
```

The command makes one connectivity request, then one summary request, then
diagnosis requests subject to the remaining budget. It requires a new output
directory and never overwrites a previous attempt. The example uses a
provider-specific endpoint; choose a model, endpoint, and supported reasoning
setting appropriate to your account. `--reasoning-effort` is optional and is
omitted from the API payload when not supplied.

### Reuse a frozen handover, without pooling earlier trials

If a previous run produced a nonempty `case.json`, it can be reused verbatim.
The reviewed Cedar 02 case is included so the same handover can be tested
without generating a replacement:

```sh
python scripts/run_live_case.py \
  --model step-5-preview \
  --base-url https://api.stepfun.com/step_plan/v1 \
  --api-key-env CTXSURGERY_EXPERIMENT_KEY \
  --frozen-case examples/results/2026-10-22/cedar-02/case.json \
  --out artifacts/cedar-frozen-rerun \
  --max-calls 18 \
  --repeats 3 \
  --max-output-tokens 16384 \
  --timeout 120 \
  --reasoning-effort low
```

Frozen mode skips connectivity and summary generation. It validates that the
policy, task, and evaluator still match the fixed Cedar fixture. Every
diagnosis trial is newly requested. Prior passing trials are **not** spliced
into the new baseline, and earlier incomplete runs remain incomplete.

The recorded `source_case_sha256` identifies the exact reused case file.
Model settings in the rerun describe diagnosis, not the earlier summary
generation. Changing settings between attempts is not a controlled experiment
on reasoning effort or network configuration.

## Case 2: a newly authored retrieval probe on archived memories

`scripts/run_archived_probe.py` uses unchanged before/after memories imported
from the public Dynamic Cheatsheet archive. The upstream run used Claude 3.5
Sonnet; the live probe uses the model explicitly selected at invocation.
These are different stages and models, not a replay of the upstream run.

After inspecting a known omission, we authored this narrow task: return the
exact defaults for `t_range` and `points` in `find_min_max_value`, using `null`
for a missing value. The evaluator expects the two values from the original
memory, `[-5, 5]` and `1000`, as exact JSON. It does not execute the archived
Python or evaluate a mathematical solution.

This task is **post hoc and deliberately targeted**, not independently sampled
or preregistered. The original memory is manually grouped into three coarse
fragments: a prefix, the complete memory item containing the known helper,
and a suffix. Joining them with the original separators reproduces the
original text exactly. This tests restoration at that chosen granularity; it
does not demonstrate blind discovery of an unknown faulty line.

The after memory contains previous-content placeholders instead of some
concrete earlier content. If the model nevertheless answers correctly, the
passing result is retained and the engine does not force a repair finding.
This is **not an AIME-answer repair, AIME accuracy measurement, or production
incident**.

### Source and checksums

- Paper: [Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory](https://arxiv.org/abs/2504.07952), by Mirac Suzgun, Mert Yuksekgonul, Federico Bianchi, Dan Jurafsky, and James Zou.
- Repository: [suzgunmirac/dynamic-cheatsheet](https://github.com/suzgunmirac/dynamic-cheatsheet).
- Pinned commit: `5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9`.
- [Pinned source file](https://raw.githubusercontent.com/suzgunmirac/dynamic-cheatsheet/5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9/results/AIME_2024/claude-3-5-sonnet_DynamicCheatsheet_Cumulative.jsonl).
- Source file SHA256: `53734028cd3a9b17adc07ae712b9200fffa9d24c58212478d6808d788390edaa`.
- Record: index 28, zero-based; before is `steps[0].current_cheatsheet`; after is `final_cheatsheet`.
- Before UTF-8 SHA256: `3cc6d3194ea2be7a7baaadc8e086a5895c7b9b10c6165b56261bcf2efb6c4cb9`.
- After UTF-8 SHA256: `1b617ddcd3cc9c8dc863d0eefe196f2810510576ae31be621a280f236d8a2ab8`.

### Import and run

```sh
python scripts/import_public_example.py --out artifacts/public-memory
python scripts/run_archived_probe.py \
  --source artifacts/public-memory \
  --out artifacts/archived-probe-new-run \
  --model step-5-preview \
  --base-url https://api.stepfun.com/step_plan/v1 \
  --api-key-env CTXSURGERY_EXPERIMENT_KEY \
  --max-calls 32 \
  --repeats 3 \
  --max-output-tokens 16384 \
  --timeout 120 \
  --reasoning-effort low
```

The importer downloads the pinned public file only on explicit invocation.
The probe checks both local snapshot hashes before making any model call. It
does not regenerate or edit the archived summaries. The importer and probe
both require fresh output locations rather than overwriting prior evidence.
See [the static import example](public-dynamic-cheatsheet.md) for additional
source details and the difference between a textual diff and a live test.

## How to interpret a completed report

The diagnosis engine first tests the original and reduced contexts. It stops
if the original does not work, a request errors, or the reduced context already
passes. Only a reproduced failure proceeds to restoration and filler controls.
Restoration appends missing fragments; it does not replace the reduced text.

A positive localization requires a passing original, failing reduced context,
passing restoration, and failing character-matched filler under the selected
pass threshold. Greedy deletion then checks whether any single retained
fragment can be removed. A reported **1-minimal** repair is relative to the
chosen fragments, evaluator, runner, placement, and threshold; it is neither a
globally smallest text repair nor a general causal proof.

- Three sequential replicates are descriptive. They do not establish
  statistical significance, independence, robustness across seeds, or a model
  ranking. Temperature zero does not guarantee identical output.
- Exact JSON evaluation includes formatting and type requirements. A failure
  may reflect formatting rather than missing semantic knowledge.
- Filler matches Python character counts and newline positions, **not tokens**.
  It is not guaranteed semantically inert. Different context lengths can
  induce different model behavior.
- Candidate detection is lexical, not semantic. Adaptive deletion reuses
  completed arms within a run instead of resampling them; cached arms are not
  counted again as new observations.
- A provider error invalidates an arm. It must not be counted as evidence that
  the model lacks the answer. No automatic network retries are hidden in the
  ledger.
- A completed negative result is useful. Do not keep selecting new summaries
  until a desired failure appears and then report only the selected result.

## Artifacts, costs, privacy, and licensing

Each run writes local `provenance.json`, `calls.json`, and, once available,
`case.json`, `report.json`, and `report.html`. The call ledger is saved before
each request and updated afterward, including failures. It contains inputs,
final outputs, safe numeric usage fields, and bounded error metadata, not API
keys, authorization headers, raw exception bodies, or reasoning traces.

These live examples can spend API credits. `--max-calls` limits one invocation;
it does **not** enforce a global allowance across separate commands. The
recorded pilot/probe campaign imposed an additional shared limit of 48 attempted
model-generation requests across its runs and finished at 43. Track that total
explicitly for your own campaign; credential-free connectivity probes are
disclosed separately.
Token usage is not a price quote, and missing usage on an error does not prove
that the provider charged nothing.

`artifacts/` is Git-ignored. Review the contents before sharing reports: the
archived probe's local cases, ledgers, and HTML can include upstream-derived
memory content. Public delivery should use reviewed, content-redacted result
summaries, rerun code, source attribution, hashes, settings, and limitations,
not silently publish a complete archive or private research material.

The upstream repository's [MIT license](https://github.com/suzgunmirac/dynamic-cheatsheet/blob/5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9/LICENSE)
does not independently resolve rights in every third-party benchmark item.
This project distributes an importer and probe, not the full result archive.
Review applicable terms and preserve notices before redistributing extracted
memories. Local import does not relicense them under ctxsurgery's license.
