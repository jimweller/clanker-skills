"""Deterministic Step 5 rules: parsing, checkout, conservation audits, merge joining, verdict checks."""
import json

import checkout
import collate
import merge
import normalize
import verify


def test_normalize_reads_every_finding_and_assigns_components(repo):
    rows, bad = normalize.collect(str(repo["state"]))
    assert bad == []
    assert [(r["src"], r["severity"], r["path"], r["line"], r["symbol"]) for r in rows] == [
        ("claude", "High", "src/a.ts", 12, "login"), ("openai", "Critical", "src/a.ts", 12, "login"),
        ("claude", "Medium", "src/b.ts", 3, ""), ("ocr", "Low", "src/b.ts", 4, "")]
    assert {r["component"] for r in rows} == {"c01"} and rows[0]["id"] == "F1"


def test_normalize_reports_an_unparsable_bullet(repo):
    (repo["state"] / "gemini-data.md").write_text("## Data\n\n- **High** no location at all\n")
    rows, bad = normalize.collect(str(repo["state"]))
    assert len(bad) == 1


def test_checkout_is_the_commit_without_excluded_paths(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    (repo["repo"] / "src" / "a.ts").write_text("uncommitted edit\n")
    removed = checkout.make(run)
    co = repo["run"] / "checkout"
    assert sorted(removed) == [".claude", "CLAUDE.md", "pkg/CLAUDE.md"]
    assert (co / "src" / "a.ts").read_text().startswith("line 1") and not (co / ".llmtmp").exists()
    assert not (co / ".git").exists()


def test_collate_audit_finds_missing_duplicate_and_unknown_ids():
    answer = {"issues": [{"key": "c01-001", "title": "t", "location": "src/a.ts:12", "members": ["F1", "F2", "F2", "F9"]}],
              "dropped": [{"id": "F3", "reason": "says it is safe"}]}
    errs = collate.content_errors(answer, {"ids": ["F1", "F2", "F3", "F4"]})
    assert any("F4" in e and "unassigned" in e for e in errs)
    assert any("F2" in e and "more than once" in e for e in errs)
    assert any("F9" in e and "not in this component" in e for e in errs)


def test_merge_joins_groups_through_window_overlap():
    windows = {"g-01": {"keys": ["a", "b", "c"]}, "g-02": {"keys": ["c", "d", "e"]}}
    answers = {"g-01": {"groups": [{"keys": ["a", "c"], "title": "one defect", "location": "x:1"}]},
               "g-02": {"groups": [{"keys": ["c", "d", "z"], "title": "one defect again", "location": "x:2"}]}}
    groups, outside, repeated = merge.join(windows, answers)
    assert [g["keys"] for g in groups] == [["a", "c", "d"]] and outside == 1


def test_verify_check_rejects_placeholder_and_unquoted_evidence(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    issue = {"id": "I1", "members": ["F1", "F2"]}
    good = {"verdict": "true", "basis": "confirmed", "reason": "r" * 120, "failure_scenario": "f" * 90,
            "severity": "High", "severity_reason": "s" * 40, "locations_not_confirmed": [], "members_off_topic": [],
            "evidence": [{"location": "src/a.ts:12", "code": "line 12"}]}
    assert verify.content_errors(good, issue, run) == []
    bad = dict(good, reason="test", evidence=[{"location": "a:1", "code": "x"}], members_off_topic=["F7"])
    errs = verify.content_errors(bad, issue, run)
    assert any("reason" in e for e in errs) and any("evidence" in e for e in errs) and any("F7" in e for e in errs)


def test_verify_accepts_listing_evidence_for_an_absence_when_one_entry_quotes_code(repo):
    run = json.loads((repo["run"] / "run.json").read_text())
    issue = {"id": "I1", "members": ["F1"]}
    base = {"verdict": "true", "basis": "confirmed", "reason": "r" * 120, "failure_scenario": "f" * 90, "severity": "Low",
            "severity_reason": "s" * 40, "locations_not_confirmed": [], "members_off_topic": []}
    listing = {"location": "file listing (find . -type f)", "code": "./src/a.ts\n./src/b.ts"}
    ok = dict(base, evidence=[{"location": "src/a.ts:12", "code": "line 12"}, listing])
    assert verify.content_errors(ok, issue, run) == []
    only_listing = dict(base, evidence=[listing])
    assert any("quote" in e for e in verify.content_errors(only_listing, issue, run))
    bad_quote = dict(base, evidence=[{"location": "src/a.ts:12", "code": "test"}, listing])
    assert any("not the code" in e for e in verify.content_errors(bad_quote, issue, run))
