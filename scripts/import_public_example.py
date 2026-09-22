"""Explicit, integrity-checked import of two public Dynamic Cheatsheet memories.

This script is not invoked by package installation or by the offline demo. It
downloads public data only when explicitly run. It never executes source data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


SOURCE_COMMIT = "5cfe3c37e8e52b1d858d0f3df46e7f17c50991b9"
SOURCE_REPOSITORY = "https://github.com/suzgunmirac/dynamic-cheatsheet"
SOURCE_PATH = (
    "results/AIME_2024/"
    "claude-3-5-sonnet_DynamicCheatsheet_Cumulative.jsonl"
)
SOURCE_URL = (
    "https://raw.githubusercontent.com/suzgunmirac/dynamic-cheatsheet/"
    f"{SOURCE_COMMIT}/{SOURCE_PATH}"
)
SOURCE_SHA256 = "53734028cd3a9b17adc07ae712b9200fffa9d24c58212478d6808d788390edaa"
RECORD_INDEX = 28
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 15
OUTPUT_NAMES = ("before.txt", "after.txt", "provenance.json")


class ExampleImportError(ValueError):
    """Source data cannot safely be imported."""


def download_source() -> bytes:
    """Fetch only the fixed source, enforcing byte and socket-timeout limits."""
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "ctxsurgery-public-example/0.1", "Accept": "text/plain"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != SOURCE_URL:
                raise ExampleImportError("Unexpected redirect from the pinned source URL.")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared_size = int(length)
                except ValueError as exc:
                    raise ExampleImportError("Invalid source Content-Length.") from exc
                if not 0 <= declared_size <= MAX_DOWNLOAD_BYTES:
                    raise ExampleImportError("Source exceeds the download size limit.")
            raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (URLError, TimeoutError, OSError) as exc:
        raise ExampleImportError("Could not download the pinned public source.") from exc
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise ExampleImportError("Source exceeds the download size limit.")
    return raw


def extract_snapshots(raw: bytes) -> tuple[str, str, dict]:
    """Validate the complete source, then extract memory fields only."""
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise ExampleImportError("Source exceeds the download size limit.")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ExampleImportError("Source SHA256 mismatch; no output was written.")
    try:
        lines = raw.decode("utf-8").splitlines()
        record = json.loads(lines[RECORD_INDEX])
        before = record["steps"][0]["current_cheatsheet"]
        after = record["final_cheatsheet"]
    except (UnicodeError, IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ExampleImportError("Pinned source has an unexpected record structure.") from exc
    if not isinstance(before, str) or not isinstance(after, str) or not before or not after:
        raise ExampleImportError("Snapshot fields must be non-empty strings.")
    provenance = {
        "kind": "public_archived_context_snapshots",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "source_url": SOURCE_URL,
        "source_sha256": digest,
        "source_license": "MIT",
        "source_license_url": f"{SOURCE_REPOSITORY}/blob/{SOURCE_COMMIT}/LICENSE",
        "source_copyright": "Copyright (c) 2025 Mirac Suzgun",
        "source_paper": "https://arxiv.org/abs/2504.07952",
        "record_index_zero_based": RECORD_INDEX,
        "record_number_one_based": RECORD_INDEX + 1,
        "before_field": "steps[0].current_cheatsheet",
        "after_field": "final_cheatsheet",
        "before_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
        "after_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
        "before_words_whitespace": len(before.split()),
        "after_words_whitespace": len(after.split()),
        "before_characters": len(before),
        "after_characters": len(after),
        "limitations": [
            "Static snapshot comparison only; no model calls or causal experiment.",
            "Deleted text need not be useful or correct; a lexical diff is not semantic loss.",
            "No claim that this update caused a downstream answer failure.",
            "Source prompts, problem statements, answers, and model traces are not exported.",
        ],
    }
    return before, after, provenance


def import_example(output_directory: Path) -> dict:
    """Import to explicit output paths, refusing to overwrite existing files."""
    output_directory = Path(output_directory)
    for name in OUTPUT_NAMES:
        target = output_directory / name
        # lexists also rejects broken symlinks without following them.
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to overwrite {target}; choose a new --out directory.")
    before, after, provenance = extract_snapshots(download_source())
    output_directory.mkdir(parents=True, exist_ok=True)
    contents = (
        before,
        after,
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
    )
    for name, content in zip(OUTPUT_NAMES, contents):
        # Exclusive mode also protects against files appearing after the precheck.
        with (output_directory / name).open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
    return provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="Destination directory; no overwrites.")
    args = parser.parse_args(argv)
    try:
        provenance = import_example(args.out)
    except (ExampleImportError, OSError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(
        f"Imported archived memory record {RECORD_INDEX + 1}: "
        f"{provenance['before_words_whitespace']} -> "
        f"{provenance['after_words_whitespace']} whitespace-delimited words."
    )
    print(f"Saved before.txt, after.txt, provenance.json to {args.out.resolve()}")
    print("Static source data only. No causal diagnosis or live model call was performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
