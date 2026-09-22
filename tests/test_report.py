from html.parser import HTMLParser

import pytest

from ctxsurgery.report import render_html


def result_fixture():
    return {
        "schema_version": 1,
        "case_name": "Release guard",
        "status": "localized",
        "summary": "Restoring f2 repairs the regression.",
        "repair_ids": ["f2"],
        "minimality": "1-minimal",
        "candidates": [{"id": "f2", "text": "Require approval before release."}],
        "experiments": [
            {
                "id": "e1", "kind": "restore", "fragment_ids": ["f2"],
                "context_chars": 88, "pass_rate": 1.0, "valid": True,
                "trials": [{"index": 1, "passed": True, "output": "Require approval", "error": None, "elapsed_ms": 4.2}],
            },
            {
                "id": "e2", "kind": "filler", "fragment_ids": ["f2"],
                "context_chars": 88, "pass_rate": 0.0, "valid": True,
                "trials": [{"index": 1, "passed": False, "output": "Release now", "error": None, "elapsed_ms": 3.8}],
            },
        ],
        "checks": [{"removed_id": "f2", "restore_experiment": "e2", "filler_experiment": None, "repair_survives": False}],
        "calls_used": 2, "max_calls": 96, "repeats": 1, "pass_threshold": 1.0,
        "limitations": ["A deterministic example is not model evaluation."], "elapsed_ms": 8,
        "run": {"synthetic": True, "provider": "synthetic", "model": "release-guard"},
    }


def test_report_shows_evidence_provenance_and_boundaries():
    html = render_html(result_fixture())
    for expected in ("Release guard", "Synthetic · deterministic demo", "not measured LLM behavior", "1-minimal", "not a globally smallest repair", "character-matched", "token-matched placebo", "Repair breaks", 'href="#experiment-1"', "Require approval"):
        assert expected in html
    assert "<script" not in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_report_escapes_all_dynamic_text():
    malicious = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
    result = result_fixture()
    result.update(case_name=malicious, summary=malicious, status=malicious, repair_ids=[malicious], minimality=malicious, limitations=[malicious])
    result["run"] = {"synthetic": False, "provider": malicious, "model": malicious}
    result["candidates"] = [{"id": malicious, "text": malicious}]
    result["checks"] = [{"removed_id": malicious, "restore_experiment": malicious, "filler_experiment": malicious}]
    result["experiments"][0].update(id=malicious, kind=malicious, fragment_ids=[malicious])
    result["experiments"][0]["trials"][0].update(output=malicious, index=malicious)
    result["experiments"][1]["trials"][0].update(error=malicious, passed=None)
    html = render_html(result)
    assert malicious not in html
    assert "&lt;img" in html
    assert "&quot;alert(1)&quot;" in html
    assert "ERROR · not evidence" in html
    assert "Live · user-selected runner" in html


def test_minimality_not_inferred_from_status():
    result = result_fixture()
    result["minimality"] = "not-established"
    html = render_html(result)
    assert "Minimality was not established" in html
    assert "No single retained fragment" not in html


def test_invalid_experiment_does_not_display_valid_pass_rate():
    result = result_fixture()
    result["experiments"][0]["valid"] = False
    result["experiments"][0]["trials"][0].update(passed=None, error="Timeout", output=None)
    html = render_html(result)
    assert "Invalid" in html
    assert "0/1 passed · 1 errors" in html
    assert "ERROR · not evidence" in html


def test_empty_or_incomplete_report_has_explicit_unknown_provenance():
    html = render_html({})
    assert "Execution provenance not recorded" in html
    assert "No experiments recorded" in html
    assert "No missing-fragment candidates recorded" in html
    assert "Minimality was not established" in html


@pytest.mark.parametrize("unsafe_number", [float("nan"), float("inf"), -999, 999, '1; background:url(https://example.com)'])
def test_numeric_fields_cannot_inject_css_or_crash(unsafe_number):
    result = result_fixture()
    result.update(calls_used=unsafe_number, max_calls=unsafe_number, repeats=unsafe_number, pass_threshold=unsafe_number, elapsed_ms=unsafe_number)
    result["experiments"][0].update(context_chars=unsafe_number, pass_rate=unsafe_number)
    html = render_html(result)
    assert "url(https" not in html
    assert "width:nan" not in html
    assert "width:inf" not in html
    assert "width:-" not in html


def test_duplicate_untrusted_ids_do_not_produce_user_controlled_anchors():
    result = result_fixture()
    for exp in result["experiments"]:
        exp["id"] = '" onclick="alert(1)'
    html = render_html(result)
    assert 'id="experiment-0"' in html
    assert 'id="experiment-1"' in html
    assert 'onclick="' not in html


def test_no_active_content_or_remote_assets():
    class Audit(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in {"script", "iframe", "object", "embed", "form", "link", "img"}
            for name, value in attrs:
                assert not name.startswith("on")
                if name in {"src", "href"}:
                    assert value.startswith("#")

    Audit().feed(render_html(result_fixture()))


def test_rejects_non_mapping_input():
    with pytest.raises(TypeError, match="mapping"):
        render_html([])
