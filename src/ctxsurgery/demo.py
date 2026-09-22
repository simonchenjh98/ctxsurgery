"""Deterministic synthetic fixture, NOT measured LLM behavior."""

from __future__ import annotations

import json
import re


def demo_case():
    from .models import Case

    return Case.from_dict(
        {
            "version": 1,
            "name": "Synthetic release-guard context loss",
            "before": [
                {
                    "id": "instructions",
                    "text": "Read release policy configuration. Unspecified boolean flags default to false.",
                },
                {"id": "ci-gate", "text": "release.require_ci = true"},
                {"id": "approval-gate", "text": "release.require_approval = true"},
                {"id": "release-note", "text": "release.note = 'Use a friendly release title.'"},
            ],
            "after": "Read release policy configuration. Unspecified boolean flags default to false.",
            "task": "Return only JSON with the boolean fields require_ci and require_approval from the release policy.",
            "evaluator": {
                "type": "json",
                "expected": {"require_ci": True, "require_approval": True},
            },
        }
    )


def synthetic_runner(context: str, task: str) -> str:
    """A tiny config interpreter used to validate the experimental pipeline.

    This does not simulate LLM uncertainty, instruction following, or semantics.
    It computes output from context rather than hardcoding an experimental result.
    """
    config = {}
    for key, value in re.findall(
        r"^release\.([A-Za-z_]+)\s*=\s*(true|false)\s*$", context, re.MULTILINE
    ):
        config[key] = value == "true"
    return json.dumps(
        {"require_ci": config.get("require_ci", False), "require_approval": config.get("require_approval", False)},
        sort_keys=True,
    )
