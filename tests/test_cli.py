import json
from pathlib import Path

from ctxsurgery.cli import main, redact_result
from ctxsurgery.demo import demo_case, synthetic_runner


def test_demo_runner_requires_both_flags():
    case = demo_case()
    assert json.loads(synthetic_runner(case.original_context, case.task)) == {
        "require_ci": True, "require_approval": True
    }
    assert json.loads(synthetic_runner(case.after, case.task)) == {
        "require_ci": False, "require_approval": False
    }
    assert json.loads(synthetic_runner("release.require_ci = true", case.task)) == {
        "require_ci": True, "require_approval": False
    }


def test_example_matches_embedded_demo():
    path = Path(__file__).resolve().parents[1] / "examples" / "release-guard.json"
    from ctxsurgery.models import Case
    assert Case.from_dict(json.loads(path.read_text(encoding="utf-8"))).to_dict() == demo_case().to_dict()


def test_demo_end_to_end(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert result["status"] == "localized"
    assert set(result["repair_ids"]) == {"ci-gate", "approval-gate"}
    assert result["minimality"] == "1-minimal"
    assert result["run"]["synthetic"] is True
    assert result["calls_used"] <= 96
    assert (tmp_path / "report.html").is_file()
    assert "not measured LLM" in capsys.readouterr().out


def test_redaction_is_nonmutating_recursive():
    original = {"case_name": "PRIVATE", "candidates": [{"text": "SECRET"}], "experiments": [
        {"trials": [{"output": "OUTPUT", "error": "ERROR"}, {"output": None, "error": None}]}
    ]}
    result = redact_result(original)
    encoded = json.dumps(result)
    for marker in ("PRIVATE", "SECRET", "OUTPUT", "ERROR"):
        assert marker not in encoded
    assert original["case_name"] == "PRIVATE"
    assert result["experiments"][0]["trials"][1]["error"] is None


def test_redacted_demo(tmp_path):
    assert main(["demo", "--out", str(tmp_path), "--redact"]) == 0
    for name in ("report.html", "report.json"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "release.require_ci = true" not in text
        assert "Synthetic release-guard context loss" not in text


def test_budget_exhaustion_is_exit_three(tmp_path):
    assert main(["demo", "--out", str(tmp_path), "--max-calls", "1"]) == 3
    result = json.loads((tmp_path / "report.json").read_text())
    assert result["status"] == "budget_exhausted"
    assert result["calls_used"] <= 1


def test_invalid_case_is_exit_two_and_does_not_echo_inputs(tmp_path, capsys):
    case = tmp_path / "bad.json"
    case.write_text('{"SECRET":"PRIVATE", "version": 23}', encoding="utf-8")
    assert main(["diagnose", str(case), "--provider", "openai", "--model", "test", "--out", str(tmp_path / "out")]) == 2
    output = capsys.readouterr()
    assert "PRIVATE" not in output.err
    assert "SECRET" not in output.err
    assert not (tmp_path / "out" / "report.json").exists()


def test_invalid_options_exit_two(tmp_path):
    assert main(["demo", "--out", str(tmp_path), "--pass-threshold", "nan"]) == 2


def test_diff_and_report_commands(tmp_path, capsys):
    before = tmp_path / "before.txt"
    after = tmp_path / "after.txt"
    diff = tmp_path / "diff.json"
    before.write_text("Keep this.\n\nLost policy.", encoding="utf-8")
    after.write_text("Keep this.", encoding="utf-8")
    assert main(["diff", str(before), str(after), "--out", str(diff)]) == 0
    assert [item["text"] for item in json.loads(diff.read_text())] == ["Lost policy."]
    assert main(["diff", str(before), str(after)]) == 0
    assert "Lost policy." in capsys.readouterr().out
    assert main(["demo", "--out", str(tmp_path / "run")]) == 0
    html = tmp_path / "rendered.html"
    assert main(["report", str(tmp_path / "run" / "report.json"), "--out", str(html)]) == 0
    assert "<html" in html.read_text(encoding="utf-8").lower()


def test_missing_file_and_bad_report_are_exit_two(tmp_path):
    assert main(["diff", str(tmp_path / "missing"), str(tmp_path / "missing2")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert main(["report", str(bad), "--out", str(tmp_path / "out.html")]) == 2
