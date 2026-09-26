#!/usr/bin/env python3
"""Turn judge answers into edit records. No model calls.

    python3 apply.py RUN_DIR [--merged]

Reads tickets/judge/results.json (or judge/merged.json with --merged) and writes tickets/edits.json
(or tickets/merge_edits.json). Each record carries a status:
  error     the judge gave no accepted answer in every attempt
  excluded  the judge refuted the ticket or found it unsupported, the second model disagreed on
            the verdict, or an edit's evidence quote is not the code at the reviewed commit
  ready     none of the above
and the Summary, the edited texts, the deleted findings, and a severity that is the lower of the
ticket's planned severity and every model rating.
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json, load_run, lower, read_jsonl, tickets_dir  # noqa: E402
from evidence import in_code  # noqa: E402


def edit_record(item, answers, run):
    ed, cr = answers.get("editor") or {}, answers.get("critical")
    if not ed.get("ok") or (cr and not cr.get("ok")):
        return {"status": "error", "reasons": ["no accepted answer"]}
    r = ed["result"]
    reasons = []
    if r["verdict"] != "true":
        reasons.append(f"{r['basis']}: {r['reason'][:300]}")
    if cr and cr["result"]["verdict"] != r["verdict"]:
        reasons.append(f"second model verdict {cr['result']['verdict']} disagrees")
    missing = [f"{f['id']} {e['location']}" for f in r["findings"] if f["action"] != "keep"
               for e in f["evidence"] if not in_code(e, run["repo"], run["commit"])]
    if missing:
        reasons.append(f"evidence not in the code: {', '.join(missing)[:300]}")
    return {"status": "excluded" if reasons else "ready", "reasons": reasons,
            "severity": lower(item["severity"], r["severity"], cr["result"]["severity"] if cr else None),
            "summary": r["summary"].strip(),
            "texts": {f["id"]: f["text"] for f in r["findings"] if f["action"] == "edit"},
            "deleted": [f["id"] for f in r["findings"] if f["action"] == "delete"],
            "actions": dict(Counter(f["action"] for f in r["findings"]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--merged", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    run = load_run(d)
    t = tickets_dir(d)
    if a.merged:
        items = {gid: {"severity": g.get("priority") or g["severity"]} for gid, g in load_json(f"{t}/merges.json", {}).items()}
        answers, out = load_json(f"{t}/judge/merged.json", []), f"{t}/merge_edits.json"
    else:
        items = {u["id"]: u for u in read_jsonl(f"{t}/units.jsonl")}
        answers, out = load_json(f"{t}/judge/results.json", []), f"{t}/edits.json"
    records = {r["id"]: edit_record(items[r["id"]], r, run) for r in answers if r["id"] in items}
    json.dump(records, open(out, "w"), indent=1)
    print(f"wrote {out}: {dict(Counter(v['status'] for v in records.values()))}")
    acts = Counter()
    for v in records.values():
        acts.update(v.get("actions", {}))
    print(f"finding actions {dict(acts)}")
    for k, v in sorted(records.items()):
        if v["status"] != "ready":
            print(f"  {k} {v['status']}: {' | '.join(v['reasons'])[:200]}")


if __name__ == "__main__":
    main()
