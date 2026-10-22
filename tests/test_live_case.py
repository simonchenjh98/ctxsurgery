"""Offline tests of the opt-in live example. These never make model calls."""

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

from ctxsurgery.models import Response, evaluate

spec = importlib.util.spec_from_file_location("live_example", Path(__file__).parents[1] / "scripts/run_live_case.py")
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


def test_fixture_evaluator_rejects_type_and_value_errors():
    case = example.make_case("summary")
    assert evaluate(json.dumps(example.EXPECTED), case.evaluator)
    altered = json.loads(json.dumps(example.EXPECTED))
    altered["g"]["delay_seconds"] = 5
    assert not evaluate(json.dumps(altered), case.evaluator)
    altered = json.loads(json.dumps(example.EXPECTED))
    altered["i"]["retry"] = 0
    assert not evaluate(json.dumps(altered), case.evaluator)


def test_no_regression_is_recorded_honestly(tmp_path):
    values = iter(["OK", "unmodified model summary"] + [json.dumps(example.EXPECTED)] * 6)
    directory = tmp_path / "trial"
    result = example.run_experiment(lambda *_: next(values), directory, model="offline-test", base_url="http://localhost/v1")
    assert result["status"] == "already_passing"
    assert result["calls_used"] == 8
    assert result["summary_edited"] is False
    assert json.loads((directory / "case.json").read_text())["after"] == "unmodified model summary"
    assert len(json.loads((directory / "calls.json").read_text())) == 8
    report = json.loads((directory / "report.json").read_text())
    assert report["calls_used"] == 8
    assert report["max_calls"] == 48
    assert report["diagnosis_calls_used"] == 6
    assert report["diagnosis_max_calls"] == 46
    assert report["preflight_calls_used"] == 2
    assert report["elapsed_ms"] >= report["diagnosis_elapsed_ms"]
    assert result["diagnosis_calls_used"] == 6
    assert result["preflight_calls_used"] == 2
    html = (directory / "report.html").read_text(encoding="utf-8")
    assert "8/48 total calls" in html
    assert "6/46 diagnosis calls" in html
    assert "not a production incident" in html
    assert "strict formatting can also fail" in html
    with pytest.raises(FileExistsError):
        example.run_experiment(lambda *_: "", directory, model="offline-test", base_url="http://localhost/v1")


def test_provider_error_counts_and_excludes_exception_secret(tmp_path):
    def fail(*_):
        raise ValueError("DO-NOT-LOG-THIS-SECRET")
    directory = tmp_path / "trial"
    result = example.run_experiment(fail, directory, model="offline-test", base_url="http://localhost/v1")
    assert result["status"] == "runner_error"
    assert result["calls_used"] == 1
    assert "DO-NOT-LOG" not in (directory / "calls.json").read_text()
    assert "DO-NOT-LOG" not in (directory / "provenance.json").read_text()


def test_total_budget_includes_smoke_and_summary(tmp_path):
    values = iter(["OK", "summary"])
    result = example.run_experiment(lambda *_: next(values), tmp_path / "trial", model="offline-test", base_url="http://localhost/v1", max_calls=2)
    assert result["status"] == "budget_exhausted"
    assert result["calls_used"] == 2


def test_recorded_runner_saves_usage_and_enforces_budget(tmp_path):
    runner = example.RecordedRunner(lambda *_: Response("OK", {"total_tokens": 3}), tmp_path, 1)
    assert runner("context", "task").output == "OK"
    with pytest.raises(RuntimeError):
        runner("context", "task")
    assert len(runner.calls) == 1
    assert runner.calls[0]["usage"] == {"total_tokens": 3}


def test_summary_length_violation_is_preserved_in_standalone_reports(tmp_path):
    summary = " ".join(["word"] * 91)
    values = iter(["OK", summary] + [json.dumps(example.EXPECTED)] * 6)
    directory = tmp_path / "trial"
    result = example.run_experiment(
        lambda *_: next(values), directory, model="offline-test", base_url="http://localhost/v1"
    )
    assert result["summary_words"] == 91
    assert result["summary_within_word_target"] is False
    assert json.loads((directory / "case.json").read_text())["after"] == summary
    report = json.loads((directory / "report.json").read_text())
    assert report["run"]["summary_words"] == 91
    assert report["run"]["summary_within_word_target"] is False
    html = (directory / "report.html").read_text(encoding="utf-8")
    assert "91 whitespace-delimited words" in html
    assert "90-word target was exceeded" in html


@pytest.mark.parametrize(
    ("outputs", "expected_status"),
    [(["unexpected"], "smoke_unexpected_output"), (["OK", ""], "empty_summary")],
)
def test_cli_early_failures_return_nonzero_without_diagnosis(
    tmp_path, monkeypatch, outputs, expected_status
):
    class OfflineRunner:
        def __init__(self, **kwargs):
            self.base_url = kwargs["base_url"]
            self.outputs = iter(outputs)

        def __call__(self, *_):
            return Response(next(self.outputs))

    monkeypatch.setattr(example, "OpenAICompatibleRunner", OfflineRunner)
    monkeypatch.delenv("CTXSURGERY_TEST_UNUSED_KEY", raising=False)
    directory = tmp_path / "cli-trial"
    exit_code = example.main([
        "--model", "offline-test", "--base-url", "http://localhost/v1",
        "--api-key-env", "CTXSURGERY_TEST_UNUSED_KEY", "--out", str(directory),
    ])
    assert exit_code != 0
    metadata = json.loads((directory / "provenance.json").read_text())
    assert metadata["status"] == expected_status
    assert metadata["calls_used"] == len(outputs)
    assert not (directory / "report.json").exists()


@pytest.mark.parametrize("budget", [True, 1, 49])
def test_invalid_budget_makes_no_calls(tmp_path, budget):
    with pytest.raises(ValueError):
        example.run_experiment(lambda *_: pytest.fail("unexpected call"), tmp_path / "trial", model="offline-test", base_url="http://localhost/v1", max_calls=budget)


def test_frozen_case_uses_fresh_diagnosis_without_regeneration(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(example.make_case("original summary").to_dict()), encoding="utf-8")
    values = iter([json.dumps(example.EXPECTED)] * 6)
    directory = tmp_path / "frozen-run"
    result = example.run_experiment(
        lambda *_: next(values), directory, model="offline-test", base_url="http://localhost/v1",
        frozen_case=source,
    )
    assert result["status"] == "already_passing"
    assert result["calls_used"] == 6
    assert result["preflight_calls_used"] == 0
    assert result["summary_mode"] == "frozen_existing_summary"
    assert result["source_case_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert all(call["stage"] == "diagnosis" for call in json.loads((directory / "calls.json").read_text()))
    assert json.loads((directory / "case.json").read_text())["after"] == "original summary"
    assert "not continuation or pooling" in (directory / "report.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("field", ["task", "before", "evaluator", "after"])
def test_frozen_case_rejects_changed_fixture_and_empty_summary(tmp_path, field):
    data = example.make_case("summary").to_dict()
    data[field] = {
        "task": "changed task", "before": [{"id": "x", "text": "changed policy"}],
        "evaluator": {"type": "exact", "expected": "changed"}, "after": " ",
    }[field]
    source = tmp_path / "changed.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    directory = tmp_path / "not-created"
    with pytest.raises(ValueError):
        example.run_experiment(
            lambda *_: pytest.fail("unexpected call"), directory,
            model="offline-test", base_url="http://localhost/v1", frozen_case=source,
        )
    assert not directory.exists()
