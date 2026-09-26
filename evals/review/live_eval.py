#!/usr/bin/env python3
"""Score a pipeline run on the harbor fixture against the truth table.

    python3 live_eval.py WORK_DIR --run     # run the pipeline with live models, then score
    python3 live_eval.py RUN_DIR            # score an existing run directory

Run it on demand after changing a model, an effort level, or a prompt. A live run makes about 30
model calls and cost $2.87 at list price when the cassettes were last recorded. Scores, from fixture/truth.json:
- wrong sentences removed: each known wrong sentence is absent from every ticket, deferred ones
  included
- true claims kept: each key phrase of a real defect appears in some ticket
- merges: each one-fix pair shares a ticket, and each same-pattern pair does not
- rendering: the wiki text for the backslash, en dash, and brace traps is exact
- priorities: each real defect's ticket falls in the allowed priorities
- isolation: no model call's event stream contains a decoy or later-fix marker
Prints every check and a total, and exits 1 when any check fails.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TRUTH = json.load(open(os.path.join(HERE, "fixture", "truth.json")))


def norm(s):
    return " ".join(re.sub(r"[`{}\\]", "", s).lower().split())


def tickets(run):
    out = []
    for p in sorted(glob.glob(os.path.join(run, "tickets", "final", "I*.json"))):
        t = json.load(open(p))
        context = t["description"].split("h3. Details")[0]
        out.append(dict(t, text=norm(t["summary"] + " " + context), raw=t["description"]))
    return out


def resolve(run, loc):
    repo = json.load(open(os.path.join(run, "run.json")))["repo"]
    for n, line in enumerate(open(os.path.join(repo, loc["path"])).read().split("\n"), 1):
        if loc["anchor"] in line:
            return f"{loc['path']}:{n}"
    raise SystemExit(f"anchor not found: {loc}")


def score(run):
    ts = tickets(run)
    checks = []
    for w in TRUTH["wrong_sentences"]:
        checks.append((f"wrong sentence removed ({w['defect']})", all(norm(w["text"]) not in t["text"] for t in ts)))
    for p in TRUTH["true_phrases"]:
        checks.append((f"true claim kept ({p['defect']}): {p['text']}", any(norm(p["text"]) in t["text"] for t in ts)))
    for g in TRUTH["same_ticket"]:
        locs = [resolve(run, l) for l in g["locations"]]
        checks.append((f"one-fix pair shares a ticket ({g['defect']})", any(all(l in t["locations"] for l in locs) for t in ts)))
    for g in TRUTH["separate_tickets"]:
        locs = [resolve(run, l) for l in g["locations"]]
        checks.append((f"same-pattern pair stays apart ({'/'.join(g['defects'])})", not any(all(l in t["locations"] for l in locs) for t in ts)))
    for r in TRUTH["rendering"]:
        checks.append((f"wiki rendering ({r['defect']}): {r['must_contain']}", any(r["must_contain"] in t["raw"] for t in ts)))
    for name, d in TRUTH["defects"].items():
        if d.get("priority"):
            phrase = next((p["text"] for p in TRUTH["true_phrases"] if p["defect"] == name), None)
            if not phrase:
                sys.exit(f"truth.json gives {name} a priority range but no true phrase to find its ticket by")
            hit = [t for t in ts if phrase and norm(phrase) in t["text"]]
            checks.append((f"priority of {name} in {d['priority']}", bool(hit) and all(t["priority"] in d["priority"] for t in hit)))
    streams = glob.glob(os.path.join(run, "**", "calls", "*.ndjson"), recursive=True)
    leaked = [os.path.relpath(p, run) for p in streams if any(m in open(p, errors="replace").read() for m in TRUTH["markers"])]
    if streams:
        checks.append((f"no decoy or later-fix marker in {len(streams)} model streams", not leaked))
    return checks, leaked


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.split("\n\n")[1])
    target = os.path.abspath(sys.argv[1])
    if "--run" in sys.argv:
        import pipeline
        target = pipeline.run(target, "live", pipeline.CASSETTES)
    checks, leaked = score(target)
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    for p in leaked:
        print(f"      marker found in {p}")
    passed = sum(ok for _, ok in checks)
    cost = 0.0
    for p in glob.glob(os.path.join(target, "**", "calls", "*.ndjson"), recursive=True):
        for line in open(p, errors="replace"):
            if line.startswith("{") and '"type":"result"' in line.replace(" ", ""):
                cost += json.loads(line).get("total_cost_usd") or 0
    print(f"{passed} of {len(checks)} checks pass, list cost ${cost:.2f}")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
