#!/usr/bin/env python3
"""Create the run directory for one review and write run.json. No model calls.

    python3 init_run.py PROJECT_ROOT TARGET_PATH STATE_DIR

The run directory is ${XDG_CACHE_HOME:-~/.cache}/review-deep/<repo>-<commit12>, outside the
reviewed repository, so nothing the later stages write can be read by a judge. run.json records
the repository, the reviewed commit (HEAD at Step 1), the branch, the target path, the review
state directory, the judge checkout path, the default models, the files a judge must not see,
and the commit sentence tickets carry. Prints RUN_DIR and a warning when the working tree has
uncommitted changes, because reviewers read the live tree while judges read the commit.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DEFAULT_MODELS, JUDGE_EXCLUDE  # noqa: E402


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True).stdout.strip()


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__.split("\n\n")[1])
    root, target, state = (os.path.abspath(p) for p in sys.argv[1:4])
    commit = git(root, "rev-parse", "HEAD")
    if not commit:
        sys.exit(f"{root} has no commit")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    run = os.path.join(cache, "review-deep", f"{os.path.basename(root)}-{commit[:12]}")
    os.makedirs(run, exist_ok=True)
    existing = json.load(open(f"{run}/run.json")) if os.path.exists(f"{run}/run.json") else {}
    data = {
        "repo": root, "commit": commit, "branch": branch, "target_path": target, "state_dir": state,
        "run_dir": run, "checkout": f"{run}/checkout",
        "models": existing.get("models", DEFAULT_MODELS), "concurrency": existing.get("concurrency", 50),
        "judge_exclude": existing.get("judge_exclude", JUDGE_EXCLUDE),
        "commit_sentence": existing.get("commit_sentence",
                                        f"Paths and line numbers refer to commit {{{{{commit}}}}} on {branch}."),
    }
    json.dump(data, open(f"{run}/run.json", "w"), indent=1)
    dirty = [l for l in git(root, "status", "--porcelain").splitlines() if not l[3:].startswith((".llmtmp", ".serena"))]
    print(f"RUN_DIR={run}")
    print(f"COMMIT={commit}")
    if dirty:
        print(f"WARNING {len(dirty)} uncommitted changes. Reviewers read the live tree, judges read commit {commit[:12]}:")
        for l in dirty[:10]:
            print(f"  {l}")


if __name__ == "__main__":
    main()
