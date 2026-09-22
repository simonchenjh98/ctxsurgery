"""The public importer is tested offline; no test makes a network request."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_public_example.py"
SPEC = importlib.util.spec_from_file_location("import_public_example", SCRIPT)
importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(importer)


class Response(io.BytesIO):
    def __init__(self, raw, *, length=None, url=None):
        super().__init__(raw)
        self.headers = {} if length is None else {"Content-Length": length}
        self.url = importer.SOURCE_URL if url is None else url

    def geturl(self):
        return self.url


@pytest.fixture
def source(monkeypatch):
    rows = [{} for _ in range(28)]
    rows.append({
        "steps": [{"current_cheatsheet": "Retain this specific fact.\nUnicode: 学术"}],
        "final_cheatsheet": "[Previous content preserved...]",
        "input": "DO NOT EXPORT QUESTION",
        "final_output": "DO NOT EXPORT TRACE",
        "target": "DO NOT EXPORT ANSWER",
    })
    raw = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")
    monkeypatch.setattr(importer, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest())
    return raw


def test_extracts_only_memory_and_provenance(source):
    before, after, provenance = importer.extract_snapshots(source)
    assert before == "Retain this specific fact.\nUnicode: 学术"
    assert after == "[Previous content preserved...]"
    assert provenance["record_number_one_based"] == 29
    assert provenance["record_index_zero_based"] == 28
    assert provenance["before_sha256"] == hashlib.sha256(before.encode()).hexdigest()
    assert "DO NOT EXPORT" not in json.dumps([before, after, provenance])
    assert "No claim" in " ".join(provenance["limitations"])


def test_download_has_fixed_url_timeout_and_bounded_read(monkeypatch, source):
    calls = []

    def open_mock(request, timeout):
        calls.append((request.full_url, timeout))
        return Response(source, length=str(len(source)))

    monkeypatch.setattr(importer, "urlopen", open_mock)
    assert importer.download_source() == source
    assert calls == [(importer.SOURCE_URL, importer.TIMEOUT_SECONDS)]


@pytest.mark.parametrize("length", ["-1", "not-a-number", str(8 * 1024 * 1024 + 1)])
def test_rejects_invalid_content_length(monkeypatch, length):
    monkeypatch.setattr(importer, "urlopen", lambda *_a, **_k: Response(b"", length=length))
    with pytest.raises(importer.ExampleImportError):
        importer.download_source()


def test_size_limit_applies_without_content_length(monkeypatch):
    monkeypatch.setattr(importer, "MAX_DOWNLOAD_BYTES", 4)
    monkeypatch.setattr(importer, "urlopen", lambda *_a, **_k: Response(b"12345"))
    with pytest.raises(importer.ExampleImportError, match="size limit"):
        importer.download_source()


def test_rejects_redirected_response(monkeypatch):
    monkeypatch.setattr(
        importer, "urlopen", lambda *_a, **_k: Response(b"", url="https://example.invalid")
    )
    with pytest.raises(importer.ExampleImportError, match="redirect"):
        importer.download_source()


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError("timed out")])
def test_network_errors_are_actionable(monkeypatch, error):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(importer, "urlopen", fail)
    with pytest.raises(importer.ExampleImportError, match="download"):
        importer.download_source()


def test_rejects_wrong_hash_before_parsing(source):
    with pytest.raises(importer.ExampleImportError, match="SHA256"):
        importer.extract_snapshots(source + b"tampered")


@pytest.mark.parametrize("raw", [b"not json", b"\xff", b'{}', b'\n' * 28 + b'{"steps": []}'])
def test_rejects_malformed_structure(monkeypatch, raw):
    monkeypatch.setattr(importer, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(importer.ExampleImportError, match="structure"):
        importer.extract_snapshots(raw)


@pytest.mark.parametrize("value", [None, 42, "", ["not a string"]])
def test_rejects_non_string_snapshots(monkeypatch, value):
    raw = b"{}\n" * 28 + json.dumps({
        "steps": [{"current_cheatsheet": value}], "final_cheatsheet": "after"
    }).encode()
    monkeypatch.setattr(importer, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(importer.ExampleImportError, match="non-empty strings"):
        importer.extract_snapshots(raw)


def test_import_writes_utf8_memory_and_provenance(monkeypatch, source, tmp_path):
    monkeypatch.setattr(importer, "download_source", lambda: source)
    destination = tmp_path / "public-example"
    provenance = importer.import_example(destination)
    assert sorted(p.name for p in destination.iterdir()) == sorted(importer.OUTPUT_NAMES)
    assert (destination / "before.txt").read_text(encoding="utf-8").endswith("学术")
    assert json.loads((destination / "provenance.json").read_text()) == provenance
    assert "DO NOT EXPORT" not in "".join(p.read_text(encoding="utf-8") for p in destination.iterdir())


@pytest.mark.parametrize("name", importer.OUTPUT_NAMES)
def test_refuses_existing_outputs_before_network(monkeypatch, tmp_path, name):
    target = tmp_path / name
    target.write_text("user data", encoding="utf-8")

    def fail():
        pytest.fail("network called before overwrite check")

    monkeypatch.setattr(importer, "download_source", fail)
    with pytest.raises(FileExistsError, match="overwrite"):
        importer.import_example(tmp_path)
    assert target.read_text() == "user data"
    assert list(tmp_path.iterdir()) == [target]


def test_invalid_source_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(importer, "download_source", lambda: b"bad hash")
    destination = tmp_path / "missing"
    with pytest.raises(importer.ExampleImportError):
        importer.import_example(destination)
    assert not destination.exists()


def test_main_is_explicit_and_reports_static_only(monkeypatch, source, tmp_path, capsys):
    monkeypatch.setattr(importer, "download_source", lambda: source)
    assert importer.main(["--out", str(tmp_path)]) == 0
    assert "No causal diagnosis" in capsys.readouterr().out


def test_main_reports_failure_without_traceback(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(importer, "download_source", lambda: b"bad hash")
    with pytest.raises(SystemExit) as exc:
        importer.main(["--out", str(tmp_path)])
    assert exc.value.code == 1
    assert "SHA256 mismatch" in capsys.readouterr().err
