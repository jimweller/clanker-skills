#!/usr/bin/env python3
"""Verify issues against the code, one isolated model process per issue.

    python3 verify.py RUN_DIR [--floor High] [--ids FILE]

Every issue in issues.jsonl rated at or above the floor (High by default, so Critical and High)
goes to the verify model (run.json models.verify, Opus at high by default) with its title, fix
location, and every member finding. The verifier tries to refute the issue, and returns a
verdict, quoted evidence, a failure scenario, the locations where the defect does not hold, the
members that describe a different defect, and its own severity. Every confirmed issue the
verifier rates Critical then goes, blind, to the second model (models.second, Fable at high by
default). Where both rate an issue, the lower rating wins downstream.

Every answer passes content_errors, which rejects placeholders and any path:line evidence quote that
is not the code at the reviewed commit, before it is accepted. An answer needs at least one path:line
quote. Other evidence entries, such as a file listing that shows a test file is absent, are kept
unchecked, because an absence has no source line to quote. Writes verify/results.jsonl and
verify/second.jsonl.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool  # noqa: E402
from common import RANK, load_run, prompt, read_jsonl, write_jsonl  # noqa: E402
from evidence import in_code  # noqa: E402

PLACEHOLDER = re.compile(r"^(test|todo|tbd|x|a|b|n/a|na|none|placeholder|example|\.+)$", re.I)
LOCATION = re.compile(r"^[^\s:]+:\d+(-\d+)?$")
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["true", "false"]},
        "basis": {"type": "string", "enum": ["confirmed", "refuted", "insufficient_evidence"]},
        "reason": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {"location": {"type": "string"}, "code": {"type": "string"}},
                                                "required": ["location", "code"]}},
        "failure_scenario": {"type": "string"},
        "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
        "severity_reason": {"type": "string"},
        "locations_not_confirmed": {"type": "array", "items": {"type": "string"}},
        "members_off_topic": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "basis", "reason", "evidence", "failure_scenario", "severity", "severity_reason",
                 "locations_not_confirmed", "members_off_topic"],
}


def content_errors(r, issue, run):
    errs = []
    ok_basis = ["confirmed"] if r["verdict"] == "true" else ["refuted", "insufficient_evidence"]
    if r["basis"] not in ok_basis:
        errs.append(f'basis "{r["basis"]}" does not match verdict "{r["verdict"]}"')
    if len(str(r["reason"]).strip()) < 100 or PLACEHOLDER.match(str(r["reason"]).strip()):
        errs.append("reason is a placeholder or too short to name the file, function, and line")
    if len(str(r["severity_reason"]).strip()) < 30:
        errs.append("severity_reason is too short")
    if r["verdict"] == "true" and len(str(r["failure_scenario"]).strip()) < 60:
        errs.append("failure_scenario is too short for a confirmed defect")
    quoted = [e for e in r["evidence"] if LOCATION.match(str(e["location"]).strip())]
    if not quoted:
        errs.append("evidence has no path:line entry, so quote at least one span of code that decided the verdict")
    for e in quoted:
        if PLACEHOLDER.match(str(e["code"]).strip()) or not in_code(e, run["repo"], run["commit"]):
            errs.append(f"evidence at {str(e['location'])[:80]} is not the code at that location, so copy the lines exactly")
    unknown = [m for m in r["members_off_topic"] if m not in issue["members"]]
    if unknown:
        errs.append(f"members_off_topic lists IDs that are not members: {' '.join(unknown)}")
    return errs


def render(issue):
    lines = [f"# {issue['id']}: {issue['title']}", "",
             f"- Severity assigned by the review: {issue['severity']} (votes: {', '.join(f'{k} {v}' for k, v in issue['severity_votes'].items())})",
             f"- Proposed fix location: {issue['location']}", f"- Sources: {', '.join(issue['sources'])}",
             f"- Files: {', '.join(issue['files'])}", f"- Findings grouped into this issue: {len(issue['members'])}", "", "## Findings", ""]
    for e in issue["evidence"]:
        sym = f" `{e['symbol']}`" if e.get("symbol") else ""
        lines += [f"### {e['id']} ({e['src']}/{e['area']}, {e['severity']}) {e['path']}:{e['line']}{sym}", "", e["text"], ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--floor", default="High", choices=list(RANK))
    ap.add_argument("--ids")
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    run = load_run(d)
    ids = set(json.load(open(a.ids))) if a.ids else None
    issues = {i["id"]: i for i in read_jsonl(f"{d}/issues.jsonl") if RANK[i["severity"]] <= RANK[a.floor] and (not ids or i["id"] in ids)}
    os.makedirs(f"{d}/verify", exist_ok=True)
    check = lambda r, t: content_errors(r, issues[t["id"]], run)
    tasks = [{"id": k, "prompt": prompt("verify.txt", checkout=run["checkout"], commit=run["commit"], issue=render(i))} for k, i in sorted(issues.items())]
    model, effort = run["models"]["verify"]
    first = pool.run(tasks, model=model, effort=effort, schema=SCHEMA, check=check, out_dir=f"{d}/verify/first", cwd=run["checkout"],
                     concurrency=run["concurrency"])
    old = {r["id"]: r for r in read_jsonl(f"{d}/verify/results.jsonl")} if os.path.exists(f"{d}/verify/results.jsonl") else {}
    for k, o in first.items():
        if o["ok"]:
            old[k] = {"id": k, **o["result"]}
    write_jsonl(f"{d}/verify/results.jsonl", [old[k] for k in sorted(old)])
    critical = [t for t in tasks if t["id"] in first and first[t["id"]]["ok"] and first[t["id"]]["result"]["verdict"] == "true"
                and first[t["id"]]["result"]["severity"] == "Critical"]
    model2, effort2 = run["models"]["second"]
    second = pool.run(critical, model=model2, effort=effort2, schema=SCHEMA, check=check, out_dir=f"{d}/verify/second",
                      cwd=run["checkout"], concurrency=run["concurrency"]) if critical else {}
    old2 = {r["id"]: r for r in read_jsonl(f"{d}/verify/second.jsonl")} if os.path.exists(f"{d}/verify/second.jsonl") else {}
    for k, o in second.items():
        if o["ok"]:
            old2[k] = {"id": k, **o["result"]}
    write_jsonl(f"{d}/verify/second.jsonl", [old2[k] for k in sorted(old2)])
    confirmed = sum(1 for k in first if first[k]["ok"] and first[k]["result"]["verdict"] == "true")
    print(f"verified {len(first)}: confirmed {confirmed}, no accepted answer {[k for k, o in first.items() if not o['ok']]}")
    print(f"second check on {len(second)} Critical, agree {sum(1 for o in second.values() if o['ok'] and o['result']['verdict'] == 'true')}")
    print(f"list cost ${pool.cost(first) + pool.cost(second)}")


if __name__ == "__main__":
    main()
