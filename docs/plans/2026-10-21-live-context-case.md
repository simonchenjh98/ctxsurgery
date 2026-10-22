# Live context-regression case implementation plan

**Goal:** Measure, rather than assume, a context-loss regression with a live model and publish a rerunnable, honestly labelled example.

**Architecture:** Use an original fictional webhook policy as public-safe input. Ask the selected model to summarize it without instructing omission, then use the existing diagnosis engine with a fixed JSON evaluator. Save every request's public input, response, error, usage and settings locally. No private conversation or credential enters the case.

**Tech stack:** Python standard library, existing ctxsurgery SDK, an explicitly authorized OpenAI-compatible endpoint.

## Evidence boundary

- This is an authored engineering task with live model observations, not a production incident or replay of the archived AIME task.
- A natural model-produced summary is kept verbatim. Do not manually remove instructions or adjust assertions after seeing responses.
- At most 48 live calls across this session's pilot and diagnostics, including errors; no automatic retries.
- Negative results, incomplete budgets and provider errors are retained and reported distinctly.
- Character-matched filler is not token-matched; repeated temperature-zero calls do not constitute a significance test.

## Steps

1. Freeze the original policy, fixed input batch, exact JSON assertions and 90-word summarization request in an example script. Add offline tests for the fixture, call accounting, exclusive outputs and provenance.
2. Load the user-authorized provider key only into the invoking process environment. Verify the selected endpoint with one bounded smoke call, recording only safe response metadata.
3. Generate one summary and save it unchanged. Run before/after/restoration/filler and greedy ablations through the existing engine, at three repeats per arm and a remaining shared budget.
4. Review outputs for assertion validity, data disclosure and non-causal alternatives. Publish only a reviewed public-safe artifact and clearly state whether a regression was established.
5. Run the complete offline tests, build the package and inspect the generated report. Commit only scoped example, tests and documentation changes; verify remote CI after publication.

## Acceptance

The useful deliverable is a transparent runnable experiment, with a measured positive or negative result. A positive claim requires a passing original baseline, failing reduced context, passing restoration and failing filler; the engine must establish the claimed minimality. Absence of that pattern must not be called a repair.

## Continuation on 2026-10-22

- Preserve pilots 01 (2 calls, empty summary) and 02 (5 calls, runner error).
- Reuse pilot 02's unmodified 90-word summary and fixed evaluator. Run fresh
  independent before/after replicates; do not pool earlier successful trials.
- Use the documented optional `reasoning_effort=low`, keeping the second
  pilot's 16,384 output-token cap and 120-second timeout. Record this setting
  change; do not interpret it as a controlled comparison of reasoning effort.
- Record only bounded machine error codes, never provider error bodies.
- If the authored policy has no reproduced regression, publish that negative
  result. A separately labelled exploratory retrieval probe may then test
  an already-archived public memory replacement, without altering the source
  snapshots. It must not be called an AIME repair or a production incident.
- Keep the total across all pilots and probes at or below 48 attempted calls.
  A new directory is required for each run. Raw archive-derived records stay
  local; publish source attribution, rerun code, and a content-redacted result.

### Transport diagnosis before the fourth attempt

The existing process proxy routes HTTPS through localhost. Three unauthenticated
GET probes to the authorized provider's models endpoint through that proxy gave
two connection timeouts and one HTTP 401 response. Three direct probes all gave
HTTP 401 within about 0.2 seconds. These are connectivity probes, not generation
trials; 401 is expected when deliberately omitting credentials.

The fourth attempt retains the frozen case and model settings from attempt 03.
Only its process environment adds `api.stepfun.com` to `NO_PROXY`; no system
proxy configuration is changed. Before this attempt, 10 generation attempts
have been recorded. Preserve all failed attempts and do not pool their trials.
