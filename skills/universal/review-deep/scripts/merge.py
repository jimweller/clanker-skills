#!/usr/bin/env python3
"""Merge issues that describe the same defect across components, one model process per window.

    python3 merge.py RUN_DIR

Reads windows.json. The merge model (run.json models.merge, Opus at high by default) returns
groups of keys that one code change fixes. The same pattern in independent places stays apart:
an earlier rule that also merged "the same kind of defect with the same kind of fix" produced one
issue of 77 findings across 24 files, and tickets built from it cited locations that did not
support the claim. Groups from overlapping windows that share a key are joined. Keys outside
their window and keys repeated within a window are dropped and counted. Writes
global_merges.json as {"groups": [{keys, title, location, window_groups}]}.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool  # noqa: E402
from common import load_run, prompt, run_dir  # noqa: E402

SCHEMA = {"type": "object", "properties": {"groups": {"type": "array", "items": {"type": "object", "properties": {
    "keys": {"type": "array", "items": {"type": "string"}}, "title": {"type": "string"}, "location": {"type": "string"}},
    "required": ["keys", "title", "location"]}}}, "required": ["groups"]}


def content_errors(r, window):
    errs, seen = [], set()
    allowed = set(window["keys"])
    for g in r["groups"]:
        if len(g["keys"]) < 2:
            errs.append(f"group {g['keys']} has fewer than two keys, so leave it out")
        outside = [k for k in g["keys"] if k not in allowed]
        if outside:
            errs.append(f"keys not in this window: {' '.join(outside)}")
        again = [k for k in g["keys"] if k in seen]
        if again:
            errs.append(f"keys in more than one group: {' '.join(again)}")
        seen.update(g["keys"])
        if not str(g["title"]).strip() or not str(g["location"]).strip():
            errs.append(f"group {g['keys']} needs a title and a location")
    return errs


def join(windows, answers):
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    window_groups, outside, repeated = [], 0, 0
    for w, res in sorted(answers.items()):
        allowed, seen = set(windows[w]["keys"]), set()
        for g in res["groups"]:
            keys = []
            for k in g["keys"]:
                if k not in allowed:
                    outside += 1
                elif k in seen:
                    repeated += 1
                else:
                    seen.add(k)
                    keys.append(k)
            if len(keys) >= 2:
                window_groups.append({"keys": keys, "title": g["title"], "location": g["location"]})
                for k in keys[1:]:
                    parent[find(k)] = find(keys[0])
    joined = defaultdict(list)
    for g in window_groups:
        joined[find(g["keys"][0])].append(g)
    groups = []
    for parts in joined.values():
        best = max(parts, key=lambda g: len(g["keys"]))
        groups.append({"keys": sorted({k for g in parts for k in g["keys"]}), "title": best["title"], "location": best["location"],
                       "window_groups": len(parts)})
    groups.sort(key=lambda g: -len(g["keys"]))
    return groups, outside, repeated


def main():
    d = run_dir()
    run = load_run(d)
    windows = json.load(open(f"{d}/windows.json"))
    tasks = [{"id": w, "prompt": prompt("merge.txt", checkout=run["checkout"], count=len(v["keys"]), issues=v["text"])}
             for w, v in sorted(windows.items())]
    model, effort = run["models"]["merge"]
    out = pool.run(tasks, model=model, effort=effort, schema=SCHEMA, check=lambda r, t: content_errors(r, windows[t["id"]]),
                   out_dir=f"{d}/merge", cwd=run["checkout"], concurrency=run["concurrency"])
    answers = {w: o["result"] for w, o in out.items() if o["ok"]}
    groups, outside, repeated = join(windows, answers)
    json.dump({"groups": groups}, open(f"{d}/global_merges.json", "w"), indent=1)
    print(f"windows {len(windows)}, accepted {len(answers)}, without an accepted answer {sorted(set(windows) - set(answers))}")
    print(f"groups {len(groups)} over {sum(len(g['keys']) for g in groups)} issues, dropped keys outside {outside} repeated {repeated}, "
          f"list cost ${pool.cost(out)}")


if __name__ == "__main__":
    main()
