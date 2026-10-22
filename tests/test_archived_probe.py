"""Offline synthetic fixtures only; no archived text or live API is required."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from ctxsurgery.models import evaluate


@pytest.fixture
def probe(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("archived_probe", scripts / "run_archived_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path, monkeypatch, probe):
    # Original test-only material, not a copy of third-party source memories.
    before = "Test prefix\n\n<memory_item>\ndef find_min_max_value(): pass\n</memory_item>\n\nTest suffix"
    after = "Test-only summary"
    directory = tmp_path / "source"
    directory.mkdir()
    for name, text in (("before", before), ("after", after)):
        raw = text.encode("utf-8")
        (directory / f"{name}.txt").write_bytes(raw)
        monkeypatch.setattr(probe, name.upper() + "_SHA256", hashlib.sha256(raw).hexdigest())
    return directory


def test_grouping_preserves_every_character(probe, source):
    case = probe.load_case(source)
    assert case.original_context.encode("utf-8") == (source / "before.txt").read_bytes()
    assert [fragment.id for fragment in case.before] == ["memory-prefix", "hyperbola-helper", "memory-suffix"]
    assert case.after == "Test-only summary"
    assert evaluate(json.dumps(probe.EXPECTED), case.evaluator)
    assert not evaluate('{"t_range":null,"points":null}', case.evaluator)


def test_hash_mismatch_prevents_network_and_output(probe, source, tmp_path):
    (source / "after.txt").write_text("modified", encoding="utf-8")
    out = tmp_path / "not-created"
    with pytest.raises(ValueError, match="checksum"):
        probe.run_probe(lambda *_: pytest.fail("unexpected call"), source, out,
                        model="offline-test", base_url="http://localhost/v1")
    assert not out.exists()


def test_already_passing_is_not_forced_into_repair(probe, source, tmp_path):
    out = tmp_path / "run"
    result = probe.run_probe(lambda *_: json.dumps(probe.EXPECTED), source, out,
                             model="offline-test", base_url="http://localhost/v1")
    assert result["status"] == "already_passing"
    assert result["calls_used"] == 6
    assert result["original_benchmark_task"] is False
    assert result["snapshots_edited"] is False
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["snapshot_sha256"]["before"] == probe.BEFORE_SHA256
    assert "not the original AIME question" in (out / "report.html").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        probe.run_probe(lambda *_: pytest.fail("unexpected call"), source, out,
                        model="offline-test", base_url="http://localhost/v1")


def test_known_helper_is_localized_only_by_observed_arms(probe, source, tmp_path):
    def offline_runner(context, task):
        found = "def find_min_max_value(" in context
        return json.dumps(probe.EXPECTED if found else {"t_range": None, "points": None})
    result = probe.run_probe(offline_runner, source, tmp_path / "run",
                             model="offline-test", base_url="http://localhost/v1")
    assert result["status"] == "localized"
    assert result["minimality"] == "1-minimal"
    assert result["repair_ids"] == ["hyperbola-helper"]
    assert result["calls_used"] == 27


@pytest.mark.parametrize("text", ["no helper", "prefix\n<memory_item>def find_min_max_value()</memory_item>\n\nsuffix"])
def test_unexpected_sections_are_rejected(probe, text):
    with pytest.raises(ValueError):
        probe.split_before(text)
