import pytest

from ctxsurgery.models import Case, Fragment, Response, evaluate


def data(**overrides):
    return dict(version=1, name="example", before="A\n\nB", after="A", task="test", evaluator={"type": "exact", "expected": "OK"}, **overrides)


def test_case_roundtrip():
    case = Case.from_dict(data())
    assert case.before == (Fragment("f001", "A"), Fragment("f002", "B"))
    assert case.original_context == "A\n\nB"
    assert Case.from_dict(case.to_dict()) == case


@pytest.mark.parametrize("field,value", [("version", True), ("version", 2), ("name", ""), ("before", ""), ("task", None), ("after", 2)])
def test_invalid_case(field, value):
    payload = data()
    payload[field] = value
    with pytest.raises(ValueError):
        Case.from_dict(payload)


def test_duplicate_ids_and_extra_fields_rejected():
    payload = data()
    payload["before"] = [{"id": "same", "text": "a"}, {"id": "same", "text": "b"}]
    with pytest.raises(ValueError, match="unique"):
        Case.from_dict(payload)
    payload = data()
    payload["tasks"] = "typo"
    with pytest.raises(ValueError):
        Case.from_dict(payload)


@pytest.mark.parametrize("evaluator", [
    {"type": "contains"}, {"type": "contains", "all": [""]},
    {"type": "contains", "all": "x"}, {"type": "contains", "all": ["x"], "none": ["x"]},
    {"type": "exact"}, {"type": "json", "expected": float("nan")},
    {"type": "json", "expected": {1: "x"}}, {"type": "unknown"},
])
def test_invalid_evaluators(evaluator):
    payload = data()
    payload["evaluator"] = evaluator
    with pytest.raises(ValueError):
        Case.from_dict(payload)


@pytest.mark.parametrize("output,expected,passed", [
    ('{"x": true}', {"x": True}, True), ('{"x": 1}', {"x": True}, False),
    ('[1,2]', [1, 2], True), ('[1.0,2]', [1, 2], False),
    ('```json\n{}\n```', {}, False), ('NaN', None, False), ('null', None, True),
])
def test_strict_json(output, expected, passed):
    assert evaluate(output, {"type": "json", "expected": expected}) is passed


def test_contains_and_exact():
    assert evaluate(" OK\n", {"type": "exact", "expected": "OK"})
    assert evaluate("done safely", {"type": "contains", "all": ["done"], "none": ["unsafe"]})
    assert not evaluate("DONE", {"type": "contains", "all": ["done"]})


def test_evaluator_copied():
    payload = data()
    case = Case.from_dict(payload)
    payload["evaluator"]["expected"] = "changed"
    assert case.evaluator["expected"] == "OK"


def test_response_usage_validation():
    with pytest.raises(ValueError):
        Response("x", {"tokens": float("inf")})


@pytest.mark.parametrize("output,expected", [
    ('{"ok":false,"ok":true}', {"ok": True}),
    ('{"ok":true,"ok":true}', {"ok": True}),
    ('{"nested":{"ok":false,"ok":true}}', {"nested": {"ok": True}}),
])
def test_json_duplicate_keys_never_pass(output, expected):
    assert not evaluate(output, {"type": "json", "expected": expected})


@pytest.mark.parametrize("original", ["HEADER\n\n\nGUARD", "  indented\n\n    code\n", "a\r\n\r\n\r\n  b\r\n"])
def test_string_before_preserves_exact_original(original):
    payload = data()
    payload["before"] = original
    case = Case.from_dict(payload)
    assert case.original_context == original
    assert case.to_dict()["before"] == original
    assert Case.from_dict(case.to_dict()).original_context == original


def test_direct_sdk_string_case_preserves_original():
    case = Case("name", "a\n\n\nb", "a", "task", {"type": "exact", "expected": "OK"})
    assert case.original_context == "a\n\n\nb"


def test_fragment_indentation_is_not_stripped():
    case = Case("name", "a\n\n    code\n", "a", "task", {"type": "exact", "expected": "OK"})
    assert case.before[1].text == "    code\n"
