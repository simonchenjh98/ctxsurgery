"""Conservative lexical candidates, not a semantic compression verifier."""

from __future__ import annotations

import re

from .models import Case, Fragment, parse_fragments


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _retained(text: str, normalized_after: str) -> bool:
    needle = _normalize(text)
    # Do not treat e.g. limit=5 as preserved in limit=50, or guard in guardrail.
    left = r"(?<!\w)" if re.match(r"\w", needle[0]) else ""
    right = r"(?!\w)" if re.match(r"\w", needle[-1]) else ""
    return re.search(left + re.escape(needle) + right, normalized_after) is not None


def dropped_fragments(case: Case) -> tuple[Fragment, ...]:
    after = _normalize(case.after)
    return tuple(fragment for fragment in case.before if not _retained(fragment.text, after))


def diff_snapshots(before: str, after: str) -> list[dict[str, str]]:
    """Compare plain-text snapshots split into paragraphs; preserve source order."""
    if not isinstance(before, str) or not isinstance(after, str):
        raise ValueError("snapshots must be strings")
    normalized = _normalize(after)
    return [
        {"id": fragment.id, "text": fragment.text}
        for fragment in parse_fragments(before)
        if not _retained(fragment.text, normalized)
    ]
