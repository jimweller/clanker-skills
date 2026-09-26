#!/usr/bin/env python3
"""Choose which verified issues become tickets. No model calls.

    python3 plan.py RUN_DIR [--floor High]

Reads issues.jsonl, verify/results.jsonl, verify/second.jsonl, and tickets/decisions.json. An
issue is planned when its review rating (issues.jsonl severity, the highest member rating) is at
or above the floor, High by default, and the verifier confirmed it. The floor picks what gets
verified and ticketed; it is not reapplied afterwards. A confirmed issue becomes a ticket at the
lower of the verifier's and the second check's ratings, even when that is below the floor, and
the operator decides later whether low tickets are deferred.
decisions.json may list "skip_issues" (already tracked elsewhere) and "include_issues" (issues
whose first verdict is unusable, such as a placeholder answer; the judge-editor verifies them
instead, and recut skips the verifier filters). The ticket type is Task when every area is a
non-defect area (testing, quality, architecture, SOLID, documentation) and Bug otherwise.
Writes tickets/plan.json.
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import NON_BUG_AREAS, RANK, load_json, lower, read_jsonl, tickets_dir  # noqa: E402


def select(issues, verify, second, floor, skip, include):
    plan = []
    for i in issues:
        iid = i["id"]
        if iid in skip:
            continue
        areas = sorted(set(i.get("areas", [])))
        entry = {"id": iid, "type": "Task" if areas and set(areas) <= NON_BUG_AREAS else "Bug", "areas": areas,
                 "title": i["title"]}
        if iid in include:
            plan.append(dict(entry, severity=i.get("severity", "High"), ignore_verify=True))
            continue
        v = verify.get(iid)
        if RANK.get(i.get("severity"), 9) > RANK[floor] or not v or v.get("verdict") != "true":
            continue
        plan.append(dict(entry, severity=lower(v.get("severity"), (second.get(iid) or {}).get("severity"))))
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--floor", default="High", choices=list(RANK))
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    t = tickets_dir(d)
    decisions = load_json(f"{t}/decisions.json", {})
    issues = read_jsonl(f"{d}/issues.jsonl")
    verify = {v["id"]: v for v in read_jsonl(f"{d}/verify/results.jsonl")}
    second = {v["id"]: v for v in read_jsonl(f"{d}/verify/second.jsonl")} if os.path.exists(f"{d}/verify/second.jsonl") else {}
    plan = select(issues, verify, second, a.floor, set(decisions.get("skip_issues", [])), set(decisions.get("include_issues", [])))
    json.dump(plan, open(f"{t}/plan.json", "w"), indent=1)
    print(f"planned {len(plan)} issues: {dict(Counter(p['severity'] for p in plan))}, {dict(Counter(p['type'] for p in plan))}")


if __name__ == "__main__":
    main()
