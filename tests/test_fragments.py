from ctxsurgery.fragments import diff_snapshots, dropped_fragments
from ctxsurgery.models import Case, Fragment


def test_whitespace_is_not_loss():
    assert diff_snapshots("hello   world", "header\nhello\nworld\nfooter") == []


def test_changed_fragment_is_candidate():
    assert len(diff_snapshots("max_cost = 5\n\nretain", "max_cost = 50\n\nretain")) == 1
    assert diff_snapshots("max_cost = 5.", "max_cost = 50.")[0]["text"] == "max_cost = 5."


def test_subwords_are_not_retention():
    assert diff_snapshots("guard", "guardrail")[0]["text"] == "guard"


def test_unicode_and_stable_order():
    result = diff_snapshots("需要批准。\n\n保留。\n\n测试通过。", "保留。")
    assert [f["id"] for f in result] == ["f001", "f003"]


def test_structured_ids_preserved():
    case = Case("test", (Fragment("guard", "require CI"),), "", "test", {"type": "exact", "expected": "x"})
    assert dropped_fragments(case)[0].id == "guard"


def test_empty_snapshot_diff():
    assert diff_snapshots("", "some text") == []
