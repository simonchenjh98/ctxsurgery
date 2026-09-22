# What a diagnosis means

This tool localizes an **observed, task-specific restoration effect**, not a unique historical cause. It is intended for debugging a known regression after a context rewrite.

## Unit of intervention

A case defines original fragments, the compacted context, a task, and explicit assertions over the runner output. The runner receives a fresh context and task on every call. For stateful agents, the caller must reset hidden memory and tool state. Use a read-only sandbox: running a diagnosis must not repeat production side effects.

Candidates are original fragments that are not found as whitespace-normalized, word-boundary-aware substrings in the compacted context. A changed or paraphrased fragment can be a candidate even if its meaning was preserved. Contradictions, subtle semantic changes, and loss inside otherwise retained fragments are not comprehensively detected.

## Admission and controls

1. The original context must pass the chosen threshold.
2. The compacted context must fail that threshold.
3. Appending the candidate set must pass.
4. Appending filler of the same Python character count and newline layout must fail.

Without all four conditions, the result is not a localized content-specific repair. A provider error is neither a passing nor a failing task observation; the run stops with incomplete evidence. Every attempted call consumes the budget. The engine reserves a full arm's repeats before starting it, so a budget can end with unused calls.

Filler is ordinary unrelated text. It is **not guaranteed semantically neutral**, and character count is not token count. An observed difference can depend on wording, position, model priors or sampling. Actual provider token usage is recorded when supplied, but not used to claim token matching.

## Greedy deletion and ablation

Starting with the passing restoration, try deleting one fragment at a time in source order. Accept a deletion only if the smaller restoration passes and its own filler control fails. Restart the search after every accepted deletion. Finish only after every single-fragment deletion from the final set fails.

This yields a **1-minimal** set for observed outcomes: no one remaining fragment can be removed. It does not ensure the smallest number of fragments among all possible subsets. A different order may return another repair. Non-monotonic behavior means a set could still be reduced by removing multiple fragments together. If the complete restoration fails, this version does not search every possible subset.

Completed arms are memoized within the invocation. Each repeat is a fresh runner call, but looking up an arm again does not create another replicate or more evidence. Adaptive search and a few sequential repeats are not a significance test. Confirm an important finding in a fresh run with fresh samples and additional tasks.

## Reproducibility and privacy

JSON reports record the tool version, UTC start timestamp, canonical case SHA256, before/after context SHA256, thresholds, budget, experiment contexts' character counts, fragment sets, actual outputs/errors, usage when available, and final repair/control experiment IDs. The CLI adds execution provenance. The original case is needed to reconstruct inputs; reports deliberately do not embed the complete original task or retained context.

Hashes identify exact inputs but are not anonymization. Small or predictable inputs may be guessed. Keep private input cases and reports out of public repositories. `--redact` removes selected text fields, not every potentially identifying field. A user-selected live endpoint receives the case's context and task whether or not report redaction is enabled.

## What the supplied examples establish

- The synthetic config-interpreter demo verifies mechanics: two policy flags interact, a distractor is removable, filler does not supply the flags, and both leave-one-out ablations fail. It measures no LLM behavior.
- The optional public Dynamic Cheatsheet importer verifies a pinned archived pair of real memory snapshots and can feed a lexical diff. It does not show that lost text caused a wrong answer, and does not run a new model.
- The local HTTP integration test verifies request/response plumbing, not a remote model's quality or compatibility with every provider/model.

Real usefulness still requires user-supplied regressions, appropriate assertions, independent model runs, and replication across cases.
