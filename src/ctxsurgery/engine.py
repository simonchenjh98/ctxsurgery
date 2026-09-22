"""Budgeted restoration, filler control, and greedy deletion experiments."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import time
from typing import Callable

from .fragments import dropped_fragments
from .models import Case, Response, evaluate

Runner = Callable[[str, str], str | Response]
_FILLER = "The sky is blue. A leaf is green. "


def _filler_like(text: str) -> str:
    # Preserve newline positions and Python character count, NOT token count.
    chars = iter((_FILLER * (len(text) // len(_FILLER) + 1)))
    return "".join(char if char in "\r\n" else next(chars) for char in text)


class _BudgetExhausted(Exception):
    pass


class _RunnerError(Exception):
    pass


def diagnose(
    case: Case,
    runner: Runner,
    *,
    repeats: int = 3,
    max_calls: int = 96,
    pass_threshold: float = 1.0,
    max_candidates: int = 24,
) -> dict:
    """Return task-local evidence; never assert a global or statistical causal proof.

    Every replicate calls the runner. Completed experiment arms are reused within
    this invocation during search, not resampled or counted as new observations.
    Stateful runners must be reset by the caller for every invocation.
    """
    if not isinstance(case, Case) or not callable(runner):
        raise ValueError("diagnose requires a Case and callable runner")
    for value, label in ((repeats, "repeats"), (max_calls, "max_calls"), (max_candidates, "max_candidates")):
        if type(value) is not int or value < 1:
            raise ValueError(f"{label} must be a positive integer")
    if type(pass_threshold) not in (int, float) or not math.isfinite(pass_threshold) or not 0 < pass_threshold <= 1:
        raise ValueError("pass_threshold must be finite and in (0, 1]")
    started = time.monotonic()
    candidates = dropped_fragments(case)
    texts = {fragment.id: fragment.text for fragment in candidates}
    canonical_case = json.dumps(case.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result = {
        "schema_version": 1,
        "tool_version": "0.1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_sha256": hashlib.sha256(canonical_case.encode("utf-8")).hexdigest(),
        "snapshot_sha256": {
            "before": hashlib.sha256(case.original_context.encode("utf-8")).hexdigest(),
            "after": hashlib.sha256(case.after.encode("utf-8")).hexdigest(),
        },
        "strategy": "ordered-greedy-deletion-with-restart",
        "case_name": case.name,
        "status": "inconclusive",
        "summary": "Diagnosis did not complete.",
        "repair_ids": [],
        "repair_experiment_id": None,
        "repair_filler_experiment_id": None,
        "minimality": "not-established",
        "candidates": [{"id": f.id, "text": f.text} for f in candidates],
        "experiments": [], "checks": [],
        "calls_used": 0, "max_calls": max_calls, "repeats": repeats,
        "pass_threshold": float(pass_threshold),
        "limitations": [
            "Evidence is specific to this task, evaluator, runner, snapshot, and append-at-end placement.",
            "Candidates use whitespace-normalized substring matching, not semantic equivalence or contradiction detection.",
            "Filler matches Python character count and newline positions, not model token count or semantic neutrality.",
            "A 1-minimal repair means no single retained fragment can be removed at the chosen pass threshold; it is not a globally smallest repair.",
            "Finite, sequential repeats and adaptive search do not establish statistical significance, reproducibility across seeds, or universal causality.",
            "Completed arms are reused only within this run; repeats are separate calls, and stateful runners must be reset for each call.",
            "Full restoration failure does not rule out other repairs, replacement rather than appending, or non-monotonic subsets.",
        ],
        "elapsed_ms": 0.0,
    }
    cache: dict[tuple[str, tuple[str, ...]], dict] = {}

    def finish(status: str, summary: str) -> dict:
        result["status"] = status
        result["summary"] = summary
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        return result

    def run(kind: str, ids: tuple[str, ...] = ()) -> dict:
        key = (kind, ids)
        if key in cache:
            return cache[key]
        if result["calls_used"] + repeats > max_calls:
            raise _BudgetExhausted
        if kind == "before":
            context = case.original_context
        elif kind == "after" or not ids:
            context = case.after
        else:
            addition = "\n\n".join(texts[i] for i in ids)
            context = case.after + "\n\n" + (_filler_like(addition) if kind == "filler" else addition)
        experiment = {
            "id": f"e{len(result['experiments']) + 1:03d}", "kind": kind,
            "fragment_ids": list(ids), "context_chars": len(context),
            "pass_rate": 0.0, "valid": False, "trials": [],
        }
        result["experiments"].append(experiment)
        for index in range(1, repeats + 1):
            trial_started = time.monotonic()
            trial = {"index": index, "passed": None, "output": None, "error": None, "elapsed_ms": 0.0, "usage": None}
            result["calls_used"] += 1
            try:
                response = runner(context, case.task)
                if isinstance(response, str):
                    response = Response(response)
                if not isinstance(response, Response):
                    raise TypeError("runner must return str or Response")
                trial["output"] = response.output
                trial["usage"] = deepcopy(response.usage)
                trial["passed"] = evaluate(response.output, case.evaluator)
            except Exception as exc:
                # Generic error text avoids leaking credentials/inputs from adapters.
                trial["error"] = f"Runner raised {type(exc).__name__}; exception message omitted for privacy."
            trial["elapsed_ms"] = round((time.monotonic() - trial_started) * 1000, 3)
            experiment["trials"].append(trial)
        experiment["valid"] = all(t["error"] is None for t in experiment["trials"])
        experiment["pass_rate"] = sum(t["passed"] is True for t in experiment["trials"]) / repeats
        cache[key] = experiment
        if not experiment["valid"]:
            raise _RunnerError
        return experiment

    def passes(experiment: dict) -> bool:
        return experiment["valid"] and experiment["pass_rate"] >= pass_threshold

    if len(candidates) > max_candidates:
        return finish("too_many_candidates", f"Found {len(candidates)} candidate fragments; split or curate the case (limit {max_candidates}).")
    if not candidates:
        return finish("no_candidates", "No lexically missing fragments were found. This does not establish that the context is semantically intact.")
    try:
        original = run("before")
        if not passes(original):
            return finish("original_not_working", "The original context does not pass at the chosen threshold; context loss cannot be isolated with this case.")
        compacted = run("after")
        if passes(compacted):
            return finish("already_passing", "The compacted context already passes at the chosen threshold; there is no reproduced failure to repair.")
        current = tuple(texts)
        restored = run("restore", current)
        if not passes(restored):
            return finish("restoration_failed", "Appending every candidate did not repair the task. Other placements, subsets, or causes remain possible.")
        result["repair_ids"] = list(current)
        result["repair_experiment_id"] = restored["id"]
        placebo = run("filler", current)
        result["repair_filler_experiment_id"] = placebo["id"]
        if passes(placebo):
            return finish("filler_also_repairs", "Both restored fragments and character-matched filler pass; content-specific restoration is not isolated.")

        # Restart after each accepted deletion. This is important for interactions:
        # checks made against a larger set do not prove final-set necessity.
        while True:
            checks = []
            removed = False
            for fragment_id in current:
                smaller = tuple(i for i in current if i != fragment_id)
                reduced = run("restore", smaller) if smaller else compacted
                check = {
                    "removed_id": fragment_id, "restore_experiment": reduced["id"],
                    "filler_experiment": None, "repair_survives": passes(reduced),
                }
                checks.append(check)
                result["checks"] = checks
                if not passes(reduced):
                    continue
                control = run("filler", smaller)
                check["filler_experiment"] = control["id"]
                if passes(control):
                    return finish("filler_also_repairs", "A smaller restoration and its filler both pass. A content-specific minimal repair is not established.")
                current = smaller
                result["repair_ids"] = list(current)
                result["repair_experiment_id"] = reduced["id"]
                result["repair_filler_experiment_id"] = control["id"]
                result["checks"] = []
                removed = True
                break
            if not removed:
                result["minimality"] = "1-minimal"
                return finish("localized", f"Observed a {len(current)}-fragment repair with a failing filler control; every single-fragment ablation fails at the chosen threshold.")
    except _BudgetExhausted:
        return finish("budget_exhausted", "Call budget exhausted before a complete diagnosis. Partial observations are preserved; minimality is not established.")
    except _RunnerError:
        return finish("runner_error", "One or more runner calls errored. Errors are not evidence of task failure; diagnosis is incomplete.")
