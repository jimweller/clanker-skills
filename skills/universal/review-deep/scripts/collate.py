#!/usr/bin/env python3
"""Group each component's findings into issues, one isolated model process per component.

    python3 collate.py RUN_DIR

Reads findings.jsonl. Each component's findings go, in full, into one prompt for the collate
model (run.json models.collate, Opus at high by default), which returns issues and drops. The
content check requires every finding ID exactly once, in an issue or in dropped, with no unknown
IDs, and a rejected answer is retried with the missing IDs named. After the last attempt, IDs the
model never placed are written to unassigned.jsonl and reported. Writes issues-by-component.jsonl
(key, component, title, location, members, severity as the highest member rating, sources,
areas, files) and dropped.jsonl.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool  # noqa: E402
from common import RANK, load_run, prompt, read_jsonl, run_dir, write_jsonl  # noqa: E402

ISSUE = {"type": "object", "properties": {"key": {"type": "string"}, "title": {"type": "string"}, "location": {"type": "string"},
                                          "members": {"type": "array", "items": {"type": "string"}}},
         "required": ["key", "title", "location", "members"]}
DROP = {"type": "object", "properties": {"id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["id", "reason"]}
SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": ISSUE}, "dropped": {"type": "array", "items": DROP}},
          "required": ["issues", "dropped"]}


def content_errors(r, comp):
    errs, seen, dup, unknown = [], set(), [], []
    expected = set(comp["ids"])
    for i in r["issues"]:
        for fid in i["members"]:
            if fid not in expected:
                unknown.append(fid)
            elif fid in seen:
                dup.append(fid)
            else:
                seen.add(fid)
        if not str(i["title"]).strip() or not str(i["location"]).strip():
            errs.append(f"issue {i['key']} needs a title and a location")
    for d in r["dropped"]:
        if d["id"] not in expected:
            unknown.append(d["id"])
        elif d["id"] in seen:
            dup.append(d["id"])
        else:
            seen.add(d["id"])
    missing = sorted(expected - seen)
    if missing:
        errs.append(f"these IDs are unassigned, so put each in an issue or in dropped: {' '.join(missing)}")
    if dup:
        errs.append(f"these IDs appear more than once: {' '.join(sorted(set(dup)))}")
    if unknown:
        errs.append(f"these IDs are not in this component: {' '.join(sorted(set(unknown)))}")
    if len({i['key'] for i in r['issues']}) != len(r["issues"]):
        errs.append("issue keys must be unique")
    return errs


def render(findings):
    out, path = [], None
    for f in findings:
        if f["path"] != path:
            path = f["path"]
            out.append(f"\n## {path}\n")
        sym = f" `{f['symbol']}`" if f.get("symbol") else ""
        out.append(f"{f['id']} L{f['line']} {f['severity']} {f['src']}/{f['area']}{sym} {f['text']}")
    return "\n".join(out).strip()


def main():
    d = run_dir()
    run = load_run(d)
    findings = read_jsonl(f"{d}/findings.jsonl")
    by_comp = defaultdict(list)
    for f in findings:
        by_comp[f["component"]].append(f)
    comps = {c: {"ids": [f["id"] for f in fs]} for c, fs in by_comp.items()}
    tasks = [{"id": c, "prompt": prompt("collate.txt", component=c, checkout=run["checkout"], count=len(fs), findings=render(fs))}
             for c, fs in sorted(by_comp.items())]
    model, effort = run["models"]["collate"]
    out = pool.run(tasks, model=model, effort=effort, schema=SCHEMA, check=lambda r, t: content_errors(r, comps[t["id"]]),
                   out_dir=f"{d}/collate", cwd=run["checkout"], concurrency=run["concurrency"])
    by_id = {f["id"]: f for f in findings}
    issues, dropped, unassigned = [], [], []
    for c in sorted(by_comp):
        r = out[c]["result"] or {"issues": [], "dropped": []}
        seen, expected = set(), set(comps[c]["ids"])
        for i in r["issues"]:
            kept = [fid for fid in i["members"] if fid in expected and fid not in seen]
            seen.update(kept)
            if kept:
                ms = [by_id[x] for x in kept]
                issues.append({"key": i["key"], "component": c, "title": i["title"].strip(), "location": i["location"].strip(),
                               "members": kept, "severity": min((m["severity"] for m in ms), key=RANK.get),
                               "severity_votes": dict(Counter(m["severity"] for m in ms)), "sources": sorted({m["src"] for m in ms}),
                               "areas": sorted({m["area"] for m in ms}), "files": sorted({m["path"] for m in ms})})
        for x in r["dropped"]:
            if x["id"] in expected and x["id"] not in seen:
                seen.add(x["id"])
                dropped.append({**by_id[x["id"]], "drop_reason": x["reason"]})
        unassigned += [by_id[x] for x in sorted(expected - seen)]
    write_jsonl(f"{d}/issues-by-component.jsonl", issues)
    write_jsonl(f"{d}/dropped.jsonl", dropped)
    write_jsonl(f"{d}/unassigned.jsonl", unassigned)
    grouped = sum(len(i["members"]) for i in issues)
    print(f"findings {len(findings)} = grouped {grouped} + dropped {len(dropped)} + unassigned {len(unassigned)}")
    print(f"issues {len(issues)}, components without an accepted answer {[c for c, o in out.items() if not o['ok']]}, "
          f"list cost ${pool.cost(out)}")


if __name__ == "__main__":
    main()
