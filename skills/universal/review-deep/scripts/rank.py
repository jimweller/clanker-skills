#!/usr/bin/env python3
"""Apply the cross-component merges, rank, and write the single issue list. No model calls.

    python3 rank.py RUN_DIR

Reads issues-by-component.jsonl and global_merges.json (absent means no merges). Writes
issues.jsonl with IDs I0001 onward, ranked by severity, then number of sources, then number of
findings, with every member finding inlined as evidence, and issues.md as a table.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RANK, read_jsonl, run_dir  # noqa: E402

ORDER = ("id", "severity", "title", "location", "sources", "severity_votes", "areas", "files", "components", "merged_from",
         "members", "evidence")


def main():
    d = run_dir()
    findings = {f["id"]: f for f in read_jsonl(f"{d}/findings.jsonl")}
    by_key = {i["key"]: i for i in read_jsonl(f"{d}/issues-by-component.jsonl")}
    groups = json.load(open(f"{d}/global_merges.json"))["groups"] if os.path.exists(f"{d}/global_merges.json") else []
    merged, used, bad, reused = [], set(), [], []
    for g in groups:
        keys = []
        for k in g["keys"]:
            if k not in by_key:
                bad.append(k)
            elif k in used:
                reused.append(k)
            else:
                keys.append(k)
        if len(keys) < 2:
            continue
        used.update(keys)
        merged.append({"title": g["title"].strip(), "location": g["location"].strip(), "members": [f for k in keys for f in by_key[k]["members"]],
                       "merged_from": keys, "components": sorted({by_key[k]["component"] for k in keys})})
    for k, i in by_key.items():
        if k not in used:
            merged.append({"title": i["title"], "location": i["location"], "members": i["members"], "merged_from": [k],
                           "components": [i["component"]]})
    for i in merged:
        ms = [findings[f] for f in i["members"]]
        i["severity"] = min((m["severity"] for m in ms), key=RANK.get)
        i["severity_votes"] = dict(Counter(m["severity"] for m in ms))
        i["sources"] = sorted({m["src"] for m in ms})
        i["areas"] = sorted({m["area"] for m in ms})
        i["files"] = sorted({m["path"] for m in ms})
        i["evidence"] = [{k: m[k] for k in ("id", "src", "area", "severity", "path", "line", "symbol", "text", "suggestion")
                          if m.get(k) not in (None, "")} for m in ms]
    merged.sort(key=lambda i: (RANK[i["severity"]], -len(i["sources"]), -len(i["members"]), i["location"]))
    width = max(4, len(str(len(merged))))
    for n, i in enumerate(merged, 1):
        i["id"] = f"I{n:0{width}d}"
    with open(f"{d}/issues.jsonl", "w", encoding="utf-8") as fh:
        for i in merged:
            fh.write(json.dumps({k: i[k] for k in ORDER}) + "\n")
    with open(f"{d}/issues.md", "w", encoding="utf-8") as fh:
        fh.write(f"# Issues ({len(merged)})\n\n| ID | Severity | Sources | Findings | Location | Title |\n| -- | -- | -- | -- | -- | -- |\n")
        for i in merged:
            fh.write(f"| {i['id']} | {i['severity']} | {','.join(i['sources'])} | {len(i['members'])} | `{i['location']}` | "
                     f"{i['title'].replace('|', chr(92) + '|')} |\n")
    print(f"issues {len(merged)} from {len(by_key)} component issues, merged groups {sum(1 for i in merged if len(i['merged_from']) > 1)}")
    print(f"unknown keys {len(bad)}, keys reused across groups {len(reused)}, by severity {dict(Counter(i['severity'] for i in merged))}")


if __name__ == "__main__":
    main()
