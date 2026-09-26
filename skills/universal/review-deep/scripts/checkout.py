#!/usr/bin/env python3
"""Make the clean checkout every judge reads. No model calls.

    python3 checkout.py RUN_DIR

Exports the reviewed commit with git archive into run.json "checkout" and removes every path in
"judge_exclude". The live working tree holds review state, editor caches, uncommitted edits, and
agent-instruction files, and judges that searched it read other reviewers' findings. A clone would
carry history, so a judge could restore an excluded file with git show or read later commits that
fix the defect; the export has no .git. An excluded name matches at any depth, so CLAUDE.md in a
subdirectory goes too. Rerunning recreates the checkout from scratch.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_run, run_dir  # noqa: E402


def excluded_paths(root, patterns):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        rel = os.path.relpath(dirpath, root)
        for name in list(dirnames) + filenames:
            path = os.path.normpath(os.path.join(rel, name))
            if any(path == p or name == p or path.endswith("/" + p) for p in patterns):
                hits.append(path)
                if name in dirnames:
                    dirnames.remove(name)
    return sorted(hits)


def make(run):
    dest = run["checkout"]
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    archive = subprocess.run(["git", "-C", run["repo"], "archive", run["commit"]], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", dest], input=archive.stdout, check=True)
    removed = excluded_paths(dest, run.get("judge_exclude", []))
    for p in removed:
        full = os.path.join(dest, p)
        shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)
    return removed


def main():
    d = run_dir()
    run = load_run(d)
    removed = make(run)
    print(f"checkout {run['checkout']} holds {run['commit'][:12]} with no git history, removed {len(removed)} excluded paths")
    for p in removed:
        print(f"  {p}")
    json.dump(removed, open(f"{d}/checkout_excluded.json", "w"), indent=1)


if __name__ == "__main__":
    main()
