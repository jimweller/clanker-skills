"""The content check every judge-editor answer must pass before it is accepted."""
from judge import content_errors

UNIT = {"id": "U1", "members": [
    {"id": "F1", "text": "The fetch has no timeout. A stalled response hangs the loop."},
    {"id": "F2", "text": "The retry loop never backs off."},
]}
GOOD_EV = [{"location": "src/api.ts:3", "code": 'const res = await fetch("/api/admin/users");'}]


def answer(**over):
    a = {"verdict": "true", "basis": "confirmed", "reason": "r" * 100, "summary": "fetchUserList has no timeout on the admin path",
         "severity": "High", "severity_reason": "s" * 40,
         "findings": [
             {"id": "F1", "action": "keep", "text": UNIT["members"][0]["text"],
              "reason": "Line 3 awaits fetch with no signal, and the caller loops over every task in sequence.", "evidence": []},
             {"id": "F2", "action": "edit", "text": "The retry loop retries immediately.",
              "reason": "The loop has a fixed zero delay at line 4.", "evidence": GOOD_EV},
         ]}
    a.update(over)
    return a


def errs(a):
    return content_errors(a, UNIT, lambda e: e["code"] != "x")


def test_clean_answer_passes():
    assert errs(answer()) == []


def test_keep_needs_a_reason_for_each_claim():
    a = answer()
    a["findings"][0]["reason"] = ""
    assert any("keep with a reason too short" in e for e in errs(a))


def test_edit_must_change_the_text():
    a = answer()
    a["findings"][1]["text"] = UNIT["members"][1]["text"]
    assert any("unchanged, so use keep" in e for e in errs(a))


def test_edit_and_delete_need_evidence_in_the_code():
    a = answer()
    a["findings"][1]["evidence"] = [{"location": "a", "code": "const x = 1;"}, {"location": "src/api.ts:3", "code": "x"}]
    found = errs(a)
    assert any("not path:line" in e for e in found)
    assert any("is not the code at that location" in e for e in found)


def test_every_member_is_answered_once():
    a = answer()
    a["findings"] = a["findings"][:1]
    assert any("missing F2" in e for e in errs(a))


def test_summary_rules():
    assert any("15 to 80" in e for e in errs(answer(summary="x" * 90)))
    assert any("trailing period" in e for e in errs(answer(summary="The fetch has no timeout on the admin path.")))
    assert any("mentions the review" in e for e in errs(answer(summary="The reviewer says fetch has no timeout")))


def test_verdict_must_match_actions():
    a = answer(verdict="false", basis="refuted")
    assert any("some findings are kept or edited" in e for e in errs(a))
    a = answer(basis="refuted")
    assert any("does not match verdict" in e for e in errs(a))
