"""Plan selection, applying judge answers, and assembly, on a one-file fixture repository."""
import json

import apply as apply_stage
import assemble
import plan as plan_stage

EV = [{"location": "src/api.ts:3", "code": 'const res = await fetch("/api/admin/users");'}]


def test_plan_floor_applies_to_the_review_rating_and_keeps_the_lowered_one():
    issues = [{"id": "I1", "title": "a", "severity": "Critical", "areas": ["bug", "security"]},
              {"id": "I2", "title": "b", "severity": "High", "areas": ["testing"]},
              {"id": "I3", "title": "c", "severity": "High", "areas": ["bug"]},
              {"id": "I4", "title": "d", "severity": "Medium", "areas": ["bug"]},
              {"id": "I5", "title": "e", "severity": "High", "areas": ["bug"]}]
    verify = {"I1": {"verdict": "true", "severity": "Critical"}, "I2": {"verdict": "true", "severity": "High"},
              "I3": {"verdict": "false", "severity": "High"}, "I4": {"verdict": "true", "severity": "Medium"},
              "I5": {"verdict": "true", "severity": "Low"}}
    second = {"I1": {"verdict": "true", "severity": "High"}}
    plan = plan_stage.select(issues, verify, second, floor="High", skip=set(), include=set())
    assert [(p["id"], p["severity"], p["type"]) for p in plan] == [("I1", "High", "Bug"), ("I2", "High", "Task"), ("I5", "Low", "Bug")]


def test_plan_include_bypasses_the_verifier():
    issues = [{"id": "I3", "title": "c", "areas": ["bug"], "severity": "High"}]
    plan = plan_stage.select(issues, {"I3": {"verdict": "false", "reason": "test", "severity": "High"}}, {}, "High", set(), {"I3"})
    assert plan[0]["ignore_verify"] and plan[0]["severity"] == "High"


def unit(uid="I1", severity="High", members=None):
    return {"id": uid, "issue": uid.split("-")[0], "path": "src/api.ts", "severity": severity, "type": "Bug",
            "areas": ["bug"], "issue_title": "t", "split": "-" in uid,
            "members": members or [{"id": "F1", "line": 3, "symbol": "fetchUserList", "text": "Escape `\\` first. It hangs.", "severity": "High"}]}


def editor(**over):
    r = {"verdict": "true", "basis": "confirmed", "reason": "r" * 90, "summary": "fetchUserList has no timeout here",
         "severity": "Medium", "severity_reason": "s" * 40,
         "findings": [{"id": "F1", "action": "edit", "text": "It hangs.", "reason": "The first sentence is wrong.", "evidence": EV}]}
    r.update(over)
    return {"ok": True, "attempts": 1, "result": r, "rejections": [], "calls": []}


def test_apply_takes_the_lowest_rating_and_the_edits(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    e = apply_stage.edit_record(unit(severity="Critical"), {"editor": editor(severity="High"),
                                "critical": {"ok": True, "result": {"verdict": "true", "severity": "Medium"}}}, run)
    assert e["status"] == "ready" and e["severity"] == "Medium" and e["texts"] == {"F1": "It hangs."}


def test_apply_excludes_refuted_disputed_and_misquoted(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    refuted = editor(verdict="false", basis="refuted", findings=[{"id": "F1", "action": "delete", "text": "", "reason": "wrong claim here", "evidence": EV}])
    assert apply_stage.edit_record(unit(), {"editor": refuted}, run)["status"] == "excluded"
    disputed = {"editor": editor(), "critical": {"ok": True, "result": {"verdict": "false", "severity": "High"}}}
    assert apply_stage.edit_record(unit(), disputed, run)["status"] == "excluded"
    bad = editor(findings=[{"id": "F1", "action": "edit", "text": "x y", "reason": "reason given", "evidence": [{"location": "src/api.ts:3", "code": "not in the file at all"}]}])
    assert apply_stage.edit_record(unit(), {"editor": bad}, run)["status"] == "excluded"
    assert apply_stage.edit_record(unit(), {"editor": dict(editor(), ok=False)}, run)["status"] == "error"


def assemble_one(repo, units, edits, merges=None, merge_edits=None, decisions=None):
    run = json.loads((repo["run"] / "run.json").read_text())
    out = assemble.assemble(run, units, edits, merges or {}, merge_edits or {}, decisions or {}, str(repo["run"] / "final"))
    return out, {p.stem: json.loads(p.read_text()) for p in (repo["run"] / "final").glob("I*.json")}


def test_assemble_renders_context_and_exact_code(repo):
    e = {"I1": apply_stage.edit_record(unit(), {"editor": editor()}, json.loads((repo["run"] / "run.json").read_text()))}
    _, t = assemble_one(repo, [unit()], e)
    d = t["I1"]["description"]
    assert "* {{src/api.ts:3}} {{fetchUserList}} It hangs." in d
    assert '    const res = await fetch("/api/admin/users");' in d
    assert t["I1"]["priority"] == "Medium" and t["I1"]["labels"] == ["review-deep", "correctness"]


def test_assemble_merges_drops_and_defers(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    u1 = unit("I9-01", members=[{"id": "F1", "line": 3, "symbol": "", "text": "Caller side.", "severity": "High"}])
    u2 = dict(unit("I9-02", members=[{"id": "F2", "line": 12, "symbol": "", "text": "Callee side.", "severity": "High"}]))
    u3 = unit("I8", severity="Low", members=[{"id": "F3", "line": 5, "symbol": "", "text": "Minor.", "severity": "Low"}])
    u4 = unit("I7", members=[{"id": "F4", "line": 7, "symbol": "", "text": "Duplicate.", "severity": "High"}])
    keep = lambda fid: editor(severity="High", findings=[{"id": fid, "action": "keep", "text": "x", "reason": "r" * 60, "evidence": []}])
    edits = {u["id"]: apply_stage.edit_record(u, {"editor": keep(u["members"][0]["id"])}, run) for u in (u1, u2, u3, u4)}
    edits["I8"]["severity"] = "Low"
    merges = {"I9-M1": {"units": ["I9-01", "I9-02"], "summary": "One filter lets non-admins delete shared rows", "severity": "Critical"}}
    manifest, t = assemble_one(repo, [u1, u2, u3, u4], edits, merges, {}, {"drop": {"I7": "duplicate"}, "defer_priorities": ["Low"]})
    flags = {m["id"]: m["flags"] for m in manifest}
    assert flags["I9-01"] == ["merged-into-I9-M1"] and flags["I7"] == ["dropped"]
    assert "deferred" in t["I8"]["flags"] and "I9-01" not in t
    m = t["I9-M1"]
    assert m["locations"] == ["src/api.ts:3", "src/api.ts:12"] and m["priority"] == "High"
    assert "backslash" not in m["description"]
    assert "Escape backslash first" in json.dumps(assemble_one(repo, [unit()], {"I1": apply_stage.edit_record(
        unit(), {"editor": editor(findings=[{"id": "F1", "action": "keep", "text": "", "reason": "r" * 60, "evidence": []}])}, run)})[1]["I1"])
