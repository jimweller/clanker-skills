#!/usr/bin/env python3
"""Merge sibling tickets that share one fix, one isolated model process per issue.

    python3 siblings.py RUN_DIR [--ids FILE]

Recut splits an issue into one unit per file, which also splits a single defect seen from a caller
and its callee into two tickets. For every issue with two or more ready units, the sibling model
(run.json models.sibling, Opus at xhigh by default) partitions the units into groups, where one
group means a change at a single location resolves every ticket in it. Same-pattern defects that
each need their own change stay apart. Groups of two or more are written to tickets/merges.json as
<ISSUE>-M<n> with the group's Summary and severity. --ids limits the run to a JSON list of issue
IDs, and merges for other issues are kept.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool  # noqa: E402
from common import load_json, load_run, prompt, read_jsonl, tickets_dir  # noqa: E402

META = re.compile(r"\b(reviewer|reviewers|verifier|this ticket|the ticket|these tickets|finding|findings|merged)\b", re.I)
PLACEHOLDER = re.compile(r"^(test|todo|tbd|x|a|b|n/a|na|none|placeholder|example|\.+)$", re.I)
SCHEMA = {"type": "object", "properties": {"groups": {"type": "array", "items": {"type": "object", "properties": {
    "tickets": {"type": "array", "items": {"type": "string"}}, "summary": {"type": "string"},
    "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]}, "reason": {"type": "string"}},
    "required": ["tickets", "summary", "severity", "reason"]}}}, "required": ["groups"]}


def content_errors(r, group):
    errs = []
    want = [t["id"] for t in group["tickets"]]
    got = [i for g in r["groups"] for i in g["tickets"]]
    if sorted(got) != sorted(want):
        errs.append(f"groups must list each of {', '.join(want)} exactly once")
    for g in r["groups"]:
        if len(str(g["reason"]).strip()) < 60 or PLACEHOLDER.match(str(g["reason"]).strip()):
            errs.append(f"reason for {g['tickets']} is a placeholder or too short to name the code read")
        if len(g["tickets"]) > 1:
            s = str(g["summary"]).strip()
            if not 15 <= len(s) <= 80 or s.endswith(".") or "\n" in s:
                errs.append(f"summary for {g['tickets']} must be 15 to 80 characters on one line with no trailing period")
            if META.search(s):
                errs.append(f"summary for {g['tickets']} mentions how the defects were found")
    return errs


def groups_to_merge(t, ids):
    units = {u["id"]: u for u in read_jsonl(f"{t}/units.jsonl")}
    edits = load_json(f"{t}/edits.json", {})
    drop = set(load_json(f"{t}/decisions.json", {}).get("drop", {}))
    by_issue = defaultdict(list)
    for uid, e in edits.items():
        u = units.get(uid)
        if u and u["split"] and e["status"] == "ready" and uid not in drop:
            by_issue[u["issue"]].append(uid)
    out = []
    for issue, uids in sorted(by_issue.items()):
        if len(uids) < 2 or (ids and issue not in ids):
            continue
        tickets = []
        for uid in sorted(uids):
            u, e = units[uid], edits[uid]
            members = [m for m in u["members"] if m["id"] not in set(e.get("deleted", []))]
            tickets.append({"id": uid, "summary": e["summary"], "severity": e["severity"],
                            "findings": [{"path": u["path"], "line": m["line"], "symbol": m.get("symbol", ""),
                                          "text": e.get("texts", {}).get(m["id"], m["text"])} for m in members]})
        out.append({"issue": issue, "tickets": tickets})
    return out


def payload(g, run):
    block = "\n\n".join(f"[{t['id']}] {t['summary']}\n" + "\n".join(
        f"- {f['path']}:{f['line']}{' ' + f['symbol'] if f['symbol'] else ''}: {f['text']}" for f in t["findings"])
        for t in g["tickets"])
    return prompt("sibling.txt", checkout=run["checkout"], commit=run["commit"], tickets=block)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--ids")
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    run = load_run(d)
    t = tickets_dir(d)
    ids = set(json.load(open(a.ids))) if a.ids else None
    groups = groups_to_merge(t, ids)
    if not groups:
        print("no issue has two or more ready sibling tickets")
        return
    by_issue = {g["issue"]: g for g in groups}
    model, effort = run["models"]["sibling"]
    out = pool.run([{"id": g["issue"], "prompt": payload(g, run)} for g in groups], model=model, effort=effort, schema=SCHEMA,
                   check=lambda r, task: content_errors(r, by_issue[task["id"]]), out_dir=f"{t}/siblings",
                   cwd=run["checkout"], concurrency=run["concurrency"])
    merges = {k: v for k, v in load_json(f"{t}/merges.json", {}).items() if k.rsplit("-M", 1)[0] not in by_issue}
    failed = []
    for issue, o in sorted(out.items()):
        if not o["ok"]:
            failed.append(issue)
            continue
        n = 0
        for g in o["result"]["groups"]:
            if len(g["tickets"]) > 1:
                n += 1
                merges[f"{issue}-M{n}"] = {"units": sorted(g["tickets"]), "summary": g["summary"].strip(),
                                           "severity": g["severity"], "reason": g["reason"]}
    json.dump(merges, open(f"{t}/merges.json", "w"), indent=1)
    print(f"issues judged {len(out)}, merge groups {len(merges)}, units merged {sum(len(g['units']) for g in merges.values())}, "
          f"no accepted answer {failed}, list cost ${pool.cost(out)}")


if __name__ == "__main__":
    main()
