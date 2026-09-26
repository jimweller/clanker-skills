#!/usr/bin/env python3
"""Re-cut each planned issue into one unit per file, built from the reviewers' own findings.

    python3 recut.py RUN_DIR

Reads tickets/plan.json, issues.jsonl, findings.jsonl, and verify/results.jsonl. For each planned
issue it keeps the member findings the verifier did not mark off-topic, whose line does not fall
in a locations_not_confirmed range on the same path, and whose line exists at the commit. A plan
entry with ignore_verify skips both verifier filters. Kept findings are grouped by file. An issue
with one file keeps its ID, and an issue with several yields <ID>-01, <ID>-02, and so on in path
order. Findings on the same line collapse to one: highest severity, then longest text.

The unit, not the issue, is the ticket. A themed issue that merged 77 findings across 24 files
produced tickets whose locations did not support the claim; per-file units fixed that, and a later
step merges units back only when a single change fixes them. Writes tickets/units.jsonl.
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RANK, load_json, load_run, read_jsonl, run_dir, tickets_dir, write_jsonl  # noqa: E402
from evidence import lines_at  # noqa: E402

LOC = re.compile(r"^\s*([^\s:()]+):(\d[\d,\- ]*)")


def spans(loc):
    m = LOC.match(loc)
    if not m:
        return None, []
    out = []
    for part in m.group(2).split(","):
        r = re.match(r"\s*(\d+)(?:-(\d+))?", part)
        if r:
            out.append((int(r.group(1)), int(r.group(2) or r.group(1))))
    return m.group(1), out


def build(plan, issues, findings, verify, line_count):
    units, drops, empty = [], Counter(), []
    for p in plan:
        iid = p["id"]
        v = {} if p.get("ignore_verify") else verify.get(iid, {})
        not_confirmed = [spans(x) for x in v.get("locations_not_confirmed", [])]
        off_topic = set(v.get("members_off_topic", []))
        kept = []
        for mid in issues[iid]["members"]:
            f = findings[mid]
            n = line_count(f["path"])
            if mid in off_topic:
                drops["off-topic"] += 1
            elif any(path == f["path"] and any(a <= f["line"] <= b for a, b in s) for path, s in not_confirmed):
                drops["not-confirmed"] += 1
            elif n is None or not 1 <= f["line"] <= n:
                drops["bad-location"] += 1
            else:
                kept.append(f)
        if not kept:
            empty.append(iid)
            continue
        by_path = defaultdict(list)
        for f in kept:
            by_path[f["path"]].append(f)
        paths = sorted(by_path)
        for k, path in enumerate(paths, 1):
            by_line = defaultdict(list)
            for f in by_path[path]:
                by_line[f["line"]].append(f)
            members = []
            for line in sorted(by_line):
                rep = min(by_line[line], key=lambda f: (RANK.get(f["severity"], 9), -len(f["text"])))
                members.append({"id": rep["id"], "line": line, "symbol": rep.get("symbol", ""), "src": rep.get("src", ""),
                                "severity": rep["severity"], "text": rep["text"],
                                "collapsed": sorted(f["id"] for f in by_line[line] if f["id"] != rep["id"])})
            units.append({"id": iid if len(paths) == 1 else f"{iid}-{k:02d}", "issue": iid, "path": path,
                          "severity": p["severity"], "type": p["type"], "areas": p["areas"],
                          "issue_title": issues[iid]["title"], "split": len(paths) > 1, "members": members})
    return units, dict(drops), empty


def main():
    d = run_dir()
    run = load_run(d)
    t = tickets_dir(d)
    plan = load_json(f"{t}/plan.json")
    if plan is None:
        sys.exit("tickets/plan.json not found; run plan.py first")
    issues = {i["id"]: i for i in read_jsonl(f"{d}/issues.jsonl")}
    findings = {f["id"]: f for f in read_jsonl(f"{d}/findings.jsonl")}
    verify = {v["id"]: v for v in read_jsonl(f"{d}/verify/results.jsonl")}

    def line_count(path):
        lines = lines_at(run["repo"], run["commit"], path)
        return None if lines is None else len(lines)

    units, drops, empty = build(plan, issues, findings, verify, line_count)
    write_jsonl(f"{t}/units.jsonl", units)
    print(f"units {len(units)} from {len({u['issue'] for u in units})} issues, members {sum(len(u['members']) for u in units)}")
    print(f"member drops {drops}, issues with no kept member {empty}")


if __name__ == "__main__":
    main()
