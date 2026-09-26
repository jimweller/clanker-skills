"""Re-cutting verified issues into one unit per file, from the reviewers' own text."""
from recut import build

F = {
    "F1": {"id": "F1", "path": "src/a.ts", "line": 3, "symbol": "go", "src": "claude", "severity": "High", "text": "short"},
    "F2": {"id": "F2", "path": "src/a.ts", "line": 3, "symbol": "go", "src": "openai", "severity": "Medium", "text": "a longer text"},
    "F3": {"id": "F3", "path": "src/b.ts", "line": 9, "symbol": "", "src": "gemini", "severity": "High", "text": "callee"},
    "F4": {"id": "F4", "path": "src/b.ts", "line": 20, "symbol": "", "src": "ocr", "severity": "Low", "text": "off topic"},
    "F5": {"id": "F5", "path": "src/b.ts", "line": 30, "symbol": "", "src": "ocr", "severity": "High", "text": "unconfirmed"},
    "F6": {"id": "F6", "path": "src/c.ts", "line": 999, "symbol": "", "src": "ocr", "severity": "High", "text": "bad line"},
}
ISSUES = {"I1": {"id": "I1", "title": "t", "members": ["F1", "F2", "F3", "F4", "F5", "F6"], "areas": ["bug"]}}
VERIFY = {"I1": {"members_off_topic": ["F4"], "locations_not_confirmed": ["src/b.ts:28-31 (guarded upstream)"]}}
PLAN = [{"id": "I1", "severity": "High", "type": "Bug", "areas": ["bug"]}]
LINES = {"src/a.ts": 10, "src/b.ts": 40, "src/c.ts": 50}


def units_for(plan=PLAN):
    return build(plan, ISSUES, F, VERIFY, lambda p: LINES.get(p))


def test_splits_by_file_with_suffixed_ids():
    units, drops, empty = units_for()
    assert [(u["id"], u["path"]) for u in units] == [("I1-01", "src/a.ts"), ("I1-02", "src/b.ts")]


def test_verifier_filters_and_bad_lines_drop_members():
    units, drops, empty = units_for()
    assert drops == {"off-topic": 1, "not-confirmed": 1, "bad-location": 1}
    assert [m["id"] for m in units[1]["members"]] == ["F3"]


def test_same_line_collapses_to_highest_severity_then_longest_text():
    units, _, _ = units_for()
    a = units[0]["members"]
    assert len(a) == 1 and a[0]["id"] == "F1" and a[0]["collapsed"] == ["F2"]


def test_single_file_issue_keeps_its_id():
    issues = {"I2": {"id": "I2", "title": "t", "members": ["F3"], "areas": ["bug"]}}
    units, _, _ = build([{"id": "I2", "severity": "High", "type": "Bug", "areas": []}], issues, F, {"I2": {}}, lambda p: LINES.get(p))
    assert units[0]["id"] == "I2" and not units[0]["split"]


def test_ignore_verify_skips_the_verifier_filters():
    plan = [dict(PLAN[0], ignore_verify=True)]
    units, drops, _ = units_for(plan)
    assert "off-topic" not in drops and "not-confirmed" not in drops
