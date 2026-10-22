# Public example: a memory replaced by placeholders

This optional example imports two **archived, real model-produced memory
snapshots** from the public Dynamic Cheatsheet repository. The importer and
diff are static, not a live run or diagnosis. A separate [live retrieval probe](live-context-cases.md)
uses these snapshots for a newly authored task; it does not replay the original
benchmark. Installation, tests, and the offline demo do not download this source automatically.

## Import and inspect

From the repository root, after installing ctxsurgery:

```sh
python scripts/import_public_example.py --out artifacts/public-example
ctxsurgery diff artifacts/public-example/before.txt artifacts/public-example/after.txt
```

The first command explicitly downloads one fixed public source file, verifies
its SHA256, and writes only `before.txt`, `after.txt`, and `provenance.json`.
The importer has an 8 MiB download cap and a 15-second network socket timeout.
It refuses to overwrite any of those files; choose a new directory to re-import.
It does not execute code from the downloaded file or transmit local context.

## Exact provenance

- Authors: Mirac Suzgun, Mert Yuksekgonul, Federico Bianchi, Dan Jurafsky, and James Zou.
- Paper: [Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory](https://arxiv.org/abs/2504.07952), 2025.
- Repository: [suzgunmirac/dynamic-cheatsheet](https://github.com/suzgunmirac/dynamic-cheatsheet).
- Pinned commit: `5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9`.
- [Pinned raw results file](https://raw.githubusercontent.com/suzgunmirac/dynamic-cheatsheet/5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9/results/AIME_2024/claude-3-5-sonnet_DynamicCheatsheet_Cumulative.jsonl).
- Source SHA256: `53734028cd3a9b17adc07ae712b9200fffa9d24c58212478d6808d788390edaa`.
- Model / run: Claude 3.5 Sonnet, AIME 2024, DynamicCheatsheet Cumulative.
- Record: **29 (one-based), index 28 (zero-based), Question #29**.
- Before field: `steps[0].current_cheatsheet`.
- After field: `final_cheatsheet` (also equal to `steps[0].new_cheatsheet`).

The before memory is the preceding record's final memory. The after memory is
passed as `steps[0].current_cheatsheet` in the next record. These are actual
state replacements, not display truncation markers introduced by ctxsurgery.

## What the data establishes

At this update, the memory changes from **689 to 329 whitespace-delimited words**
(5,381 to 2,886 Python Unicode characters). It acquires ten previous-content
placeholders: seven exact `[Previous content preserved...]` markers and three
`[Previous content preserved with addition:]` markers. Concrete earlier text is
no longer present at those positions. These are word/character counts, not
model-token counts.

Expected UTF-8 snapshot SHA256 hashes (no added trailing newline):

- Before: `3cc6d3194ea2be7a7baaadc8e086a5895c7b9b10c6165b56261bcf2efb6c4cb9`.
- After: `1b617ddcd3cc9c8dc863d0eefe196f2810510576ae31be621a280f236d8a2ab8`.

## What it does not establish

Missing text is not necessarily useful or correct. Lexical change is not proof
of semantic loss, and this archived update does not establish a downstream
performance effect. The separate [live probe](live-context-cases.md) supplies
restoration/filler/ablation observations for a new, deliberately targeted
function-default retrieval task only. In particular, this is **not** evidence
that restoring a fragment fixes an AIME answer, and it is not an estimate of
how often current models lose context. Broader claims need their own explicit
tasks, evaluators, and controlled reruns.

## License and distribution boundary

The upstream repository publishes an
[MIT license at the pinned commit](https://github.com/suzgunmirac/dynamic-cheatsheet/blob/5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9/LICENSE),
copyright (c) 2025 Mirac Suzgun, and requests citation of its paper. This project
ships an importer and source attribution, **not** a copy of the full result
archive. The archive also contains third-party benchmark questions, so the
repository's software license should not be treated as independent permission
for every underlying benchmark's redistribution.

The importer exports only the two memory fields. It does not export problem
statements, answers, generator prompts, or model traces. Before redistributing
the imported memories, review the upstream and underlying content terms and
preserve applicable notices. Importing them locally does not relicense them
under ctxsurgery's license.
