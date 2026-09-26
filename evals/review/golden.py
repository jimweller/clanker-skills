#!/usr/bin/env python3
"""Snapshot a pipeline run's outputs as the golden set, or compare a run with it. No model calls.

    python3 golden.py save RUN_DIR
    python3 golden.py diff RUN_DIR

The golden set is every stage output that replay must reproduce exactly: findings, issues, merges,
verdicts, the report, the ticket plan, units, edits, merges, every final ticket, the postable list,
and the bundle. Files that hold absolute paths or timings (run.json, pool logs, judge answer
records, call streams) are left out, and the bundle ticket's attachment path is compared by name.
diff prints each differing file and exits 1 when there is one.
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden")
FILES = ["findings.jsonl", "issues-by-component.jsonl", "global_merges.json", "issues.jsonl", "verify/results.jsonl",
         "verify/second.jsonl", "report.md", "tickets/plan.json", "tickets/units.jsonl", "tickets/edits.json", "tickets/merges.json",
         "tickets/merge_edits.json", "tickets/postable.json", "tickets/final/manifest.json"]


def members(run):
    rels = [f for f in FILES if os.path.exists(os.path.join(run, f))]
    rels += sorted(os.path.relpath(p, run) for p in glob.glob(os.path.join(run, "tickets", "final", "I*.json")))
    rels += sorted(os.path.relpath(p, run) for p in glob.glob(os.path.join(run, "tickets", "bundle", "*")))
    return rels


def normalized(path):
    if path.endswith("bundle/ticket.json"):
        t = json.load(open(path))
        t["attachment"] = os.path.basename(t["attachment"])
        return json.dumps(t, sort_keys=True)
    return open(path, encoding="utf-8").read()


def save(run):
    if os.path.exists(GOLDEN):
        shutil.rmtree(GOLDEN)
    for rel in members(run):
        dest = os.path.join(GOLDEN, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w", encoding="utf-8").write(normalized(os.path.join(run, rel)))
    print(f"saved {len(members(run))} files to {GOLDEN}")


def diff(run):
    want = sorted(os.path.relpath(p, GOLDEN) for p in glob.glob(os.path.join(GOLDEN, "**", "*"), recursive=True) if os.path.isfile(p))
    got = members(run)
    problems = [f"missing from run: {r}" for r in want if r not in got] + [f"not in golden: {r}" for r in got if r not in want]
    for rel in want:
        if rel in got and normalized(os.path.join(run, rel)) != open(os.path.join(GOLDEN, rel), encoding="utf-8").read():
            problems.append(f"differs: {rel}")
    return problems


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("save", "diff"):
        sys.exit(__doc__.split("\n\n")[1])
    run = os.path.abspath(sys.argv[2])
    if sys.argv[1] == "save":
        save(run)
        return
    problems = diff(run)
    for p in problems:
        print(p)
    print("golden matches" if not problems else f"{len(problems)} differences")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
