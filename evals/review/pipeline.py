#!/usr/bin/env python3
"""Run review-deep Step 5 and every review-tickets stage on the harbor fixture.

    python3 pipeline.py WORK_DIR [--mode live|record|replay] [--cassettes DIR]

Builds the fixture into WORK_DIR, creates the run directory under WORK_DIR/cache, and runs every
scripted stage in the order the two SKILL.md files give, with decisions.json deferring Low tickets.
--mode live calls models. --mode record calls models and saves every call under --cassettes.
--mode replay answers every call from --cassettes without a process, so it costs nothing and runs
in seconds. Exits non-zero when any stage fails. Prints RUN_DIR.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RD = os.path.join(ROOT, "skills", "universal", "review-deep", "scripts")
RT = os.path.join(ROOT, "skills", "universal", "review-tickets", "scripts")
CASSETTES = os.path.join(HERE, "cassettes")
UV = ["uv", "run", "--quiet", "--with", "scikit-learn", "--with", "scipy", "--with", "numpy", "python"]

sys.path.insert(0, os.path.join(HERE, "fixture"))
import build  # noqa: E402


def stage(env, cmd, log):
    with open(log, "a") as f:
        f.write(f"\n$ {' '.join(os.path.basename(c) if c.endswith('.py') else c for c in cmd)}\n")
        f.flush()
        p = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
    if p.returncode:
        sys.exit(f"stage failed ({p.returncode}): {' '.join(cmd)}; see {log}")


def run(work, mode, cassettes):
    work = os.path.abspath(work)
    os.makedirs(work, exist_ok=True)
    repo, state, _ = build.build(work)
    env = {**os.environ, "XDG_CACHE_HOME": os.path.join(work, "cache")}
    env.pop("REVIEW_POOL_CASSETTE", None)
    if mode != "live":
        env["REVIEW_POOL_CASSETTE"] = f"{mode}:{os.path.abspath(cassettes)}"
    out = subprocess.run([sys.executable, f"{RD}/init_run.py", repo, repo, state], env=env, capture_output=True, text=True, check=True).stdout
    d = next(l.split("=", 1)[1] for l in out.splitlines() if l.startswith("RUN_DIR="))
    log = os.path.join(work, "pipeline.log")
    open(log, "w").write(out)
    py = [sys.executable]
    for cmd in ([*py, f"{RD}/checkout.py", d], [*py, f"{RD}/normalize.py", d], [*py, f"{RD}/collate.py", d],
                [*UV, f"{RD}/windows.py", d], [*py, f"{RD}/merge.py", d], [*py, f"{RD}/rank.py", d],
                [*py, f"{RD}/verify.py", d], [*py, f"{RD}/report.py", d],
                [*py, f"{RT}/plan.py", d], [*py, f"{RT}/recut.py", d],
                [*py, f"{RT}/judge.py", d], [*py, f"{RT}/apply.py", d],
                [*py, f"{RT}/judge.py", d, "--critical"], [*py, f"{RT}/apply.py", d],
                [*py, f"{RT}/siblings.py", d], [*py, f"{RT}/judge.py", d, "--merged"], [*py, f"{RT}/apply.py", d, "--merged"]):
        stage(env, cmd, log)
    json.dump({"defer_priorities": ["Low"]}, open(os.path.join(d, "tickets", "decisions.json"), "w"))
    stage(env, [*py, f"{RT}/assemble.py", d], log)
    stage(env, [*py, f"{RT}/checks.py", d], log)
    manifest = json.load(open(os.path.join(d, "tickets", "final", "manifest.json")))
    if any("deferred" in m.get("flags", []) for m in manifest):
        stage(env, [*py, f"{RT}/bundle.py", d, "--name", "harbor"], log)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--mode", default="replay", choices=["live", "record", "replay"])
    ap.add_argument("--cassettes", default=CASSETTES)
    a = ap.parse_args()
    print(f"RUN_DIR={run(a.work, a.mode, a.cassettes)}")


if __name__ == "__main__":
    main()
