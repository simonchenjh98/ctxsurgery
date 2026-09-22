import pytest

from ctxsurgery.engine import diagnose
from ctxsurgery.models import Case, Fragment, Response


def case(*texts, after="base"):
    return Case("guard", tuple(Fragment(f"f{i}", text) for i, text in enumerate(texts)), after, "respond", {"type": "exact", "expected": "PASS"})


def both(context, task):
    return "PASS" if "CI_REQUIRED" in context and "APPROVAL_REQUIRED" in context else "FAIL"


def test_two_interacting_fragments_and_distractor():
    result = diagnose(case("CI_REQUIRED", "APPROVAL_REQUIRED", "irrelevant"), both)
    assert result["status"] == "localized"
    assert result["minimality"] == "1-minimal"
    assert result["repair_ids"] == ["f0", "f1"]
    assert {check["removed_id"] for check in result["checks"]} == {"f0", "f1"}
    assert all(not check["repair_survives"] for check in result["checks"])
    assert result["calls_used"] == sum(len(e["trials"]) for e in result["experiments"])
    restore = next(e for e in result["experiments"] if e["kind"] == "restore")
    filler = next(e for e in result["experiments"] if e["kind"] == "filler")
    assert restore["context_chars"] == filler["context_chars"]


def test_replicates_are_real_calls():
    seen = []
    def runner(context, task):
        seen.append((context, task))
        return "PASS" if "GUARD" in context else "FAIL"
    result = diagnose(case("GUARD"), runner, repeats=4)
    assert result["calls_used"] == len(seen) == 16
    assert all(len(e["trials"]) == 4 for e in result["experiments"])


def test_original_not_working():
    result = diagnose(case("guard"), lambda c, t: "FAIL")
    assert result["status"] == "original_not_working"
    assert result["calls_used"] == 3


def test_compacted_already_passes():
    assert diagnose(case("guard"), lambda c, t: "PASS")["status"] == "already_passing"


def test_filler_confounded():
    subject = case("A" * 50)
    result = diagnose(subject, lambda c, t: "PASS" if len(c) >= 50 else "FAIL")
    assert result["status"] == "filler_also_repairs"
    assert result["minimality"] == "not-established"


def test_restoration_failure():
    subject = case("original")
    result = diagnose(subject, lambda c, t: "PASS" if c == "original" else "FAIL")
    assert result["status"] == "restoration_failed"


def test_runner_errors_not_negative_evidence_and_private_message_hidden():
    def runner(c, t):
        if c == "base":
            raise RuntimeError("private API secret")
        return "PASS"
    result = diagnose(case("guard"), runner)
    assert result["status"] == "runner_error"
    assert result["experiments"][-1]["valid"] is False
    assert result["experiments"][-1]["trials"][0]["passed"] is None
    assert "private API secret" not in str(result)


@pytest.mark.parametrize("budget", [1, 3, 7, 12, 15, 20])
def test_hard_budget_and_incomplete_minimality(budget):
    result = diagnose(case("CI_REQUIRED", "APPROVAL_REQUIRED", "other"), both, max_calls=budget)
    assert result["calls_used"] <= budget
    assert result["status"] == "budget_exhausted"
    assert result["minimality"] == "not-established"


def test_no_candidates_and_cap():
    assert diagnose(case("same", after="same"), both)["status"] == "no_candidates"
    result = diagnose(case("a", "b"), both, max_candidates=1)
    assert result["status"] == "too_many_candidates"
    assert result["calls_used"] == 0


@pytest.mark.parametrize("kwargs", [{"repeats": 0}, {"repeats": True}, {"max_calls": -1}, {"pass_threshold": 0}, {"pass_threshold": float("nan")}, {"pass_threshold": True}])
def test_invalid_run_settings(kwargs):
    with pytest.raises(ValueError):
        diagnose(case("guard"), both, **kwargs)


def test_noisy_calls_threshold_not_implicit_all():
    counts = {}
    def noisy(c, t):
        counts[c] = counts.get(c, 0) + 1
        return "PASS" if "guard" in c and counts[c] % 3 else "FAIL"
    assert diagnose(case("guard"), noisy, pass_threshold=0.66)["status"] == "localized"


def test_response_usage_preserved():
    result = diagnose(case("guard"), lambda c, t: Response("PASS" if "guard" in c else "FAIL", {"total_tokens": 7}))
    assert result["experiments"][0]["trials"][0]["usage"] == {"total_tokens": 7}


def test_restart_after_deletion_is_needed_for_interactions():
    # {A,B} OR {C} works. Deleting A leaves C; B then disappears too. C is necessary.
    def runner(c, t):
        return "PASS" if ("RULE_A" in c and "RULE_B" in c) or "RULE_C" in c else "FAIL"
    result = diagnose(case("RULE_A", "RULE_B", "RULE_C"), runner, repeats=1)
    assert result["repair_ids"] == ["f2"]
    assert result["checks"][0]["removed_id"] == "f2"
    assert result["minimality"] == "1-minimal"


def test_filler_preserves_unicode_characters_and_newline_layout():
    from ctxsurgery.engine import _filler_like
    text = "规则🙂\n\n第一\r\nabc"
    filler = _filler_like(text)
    assert len(filler) == len(text)
    assert [i for i, c in enumerate(filler) if c in "\r\n"] == [i for i, c in enumerate(text) if c in "\r\n"]


def test_fingerprints_and_repair_evidence_references():
    subject = case("CI_REQUIRED", "APPROVAL_REQUIRED", "other")
    result = diagnose(subject, both, repeats=1)
    again = diagnose(subject, both, repeats=1)
    assert result["case_sha256"] == again["case_sha256"]
    assert len(result["snapshot_sha256"]["before"]) == 64
    experiments = {e["id"]: e for e in result["experiments"]}
    restored = experiments[result["repair_experiment_id"]]
    filler = experiments[result["repair_filler_experiment_id"]]
    assert restored["fragment_ids"] == result["repair_ids"]
    assert filler["fragment_ids"] == result["repair_ids"]
    assert restored["pass_rate"] == 1 and filler["pass_rate"] == 0


def test_minimality_exhaustive_three_fragment_boolean_functions():
    # All 64 deterministic Boolean functions with an original PASS and empty FAIL.
    # Covers arbitrary non-monotonic interactions without a property-test dependency.
    words = ("FEATURE_A", "FEATURE_B", "FEATURE_C")
    for bits in range(64):
        passing_masks = {7} | {i + 1 for i in range(6) if bits & (1 << i)}
        def runner(context, task):
            mask = sum(1 << i for i, word in enumerate(words) if word in context)
            return "PASS" if mask in passing_masks else "FAIL"
        result = diagnose(case(*words), runner, repeats=1, max_calls=96)
        assert result["status"] == "localized"
        repair = sum(1 << int(i[1:]) for i in result["repair_ids"])
        assert repair in passing_masks
        assert all((repair & ~(1 << i)) not in passing_masks for i in range(3) if repair & (1 << i))
        assert result["calls_used"] <= 96


def test_original_arm_is_exact_raw_snapshot():
    original = "HEADER\n\n\nGUARD\n"
    subject = Case.from_dict({"version": 1, "name": "raw", "before": original, "after": "HEADER", "task": "t", "evaluator": {"type": "exact", "expected": "PASS"}})
    seen = []
    def runner(context, task):
        seen.append(context)
        return "PASS" if context == original else "FAIL"
    result = diagnose(subject, runner, repeats=1)
    assert seen[0] == original
    assert result["status"] == "restoration_failed"
