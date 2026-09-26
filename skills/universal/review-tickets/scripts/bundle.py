#!/usr/bin/env python3
"""Bundle every deferred ticket into one ticket with a markdown attachment. No model calls.

    python3 bundle.py RUN_DIR [--name NAME]

Collects the tickets flagged deferred in tickets/final/, rebuilds each one's findings in
markdown from the unit, edit, and merge records, and writes tickets/bundle/<name>-deferred.md and
tickets/bundle/ticket.json with the summary, type Bug, the lowest deferred priority, the
review-deep label plus every category among the bundled tickets, a wiki description, and the
attachment path. Each entry has the summary, its categories, and each finding as path:line with
its symbol and text. Entries are sorted by the first file they touch. NAME defaults to the
repository directory name.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RANK, load_json, load_run, read_jsonl, tickets_dir  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--name")
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    run = load_run(d)
    t = tickets_dir(d)
    name = a.name or os.path.basename(run["repo"].rstrip("/"))
    units = {u["id"]: u for u in read_jsonl(f"{t}/units.jsonl")}
    edits = load_json(f"{t}/edits.json", {})
    merges = load_json(f"{t}/merges.json", {})
    merge_edits = load_json(f"{t}/merge_edits.json", {})

    def findings(uid, texts=None, deleted=()):
        u, e = units[uid], edits[uid]
        texts = dict(e.get("texts", {}), **(texts or {}))
        gone = set(e.get("deleted", [])) | set(deleted)
        return [{"path": u["path"], "line": m["line"], "symbol": m.get("symbol", ""), "text": texts.get(m["id"], m["text"])}
                for m in u["members"] if m["id"] not in gone]

    entries, priorities = [], []
    for m in json.load(open(f"{t}/final/manifest.json")):
        if "summary_source" not in m or "deferred" not in m["flags"]:
            continue
        tk = json.load(open(f"{t}/final/{m['id']}.json"))
        priorities.append(tk["priority"])
        if m["id"] in merges:
            me = merge_edits.get(m["id"], {})
            fs = [f for uid in merges[m["id"]]["units"] for f in findings(uid, me.get("texts"), me.get("deleted", []))]
        else:
            fs = findings(m["id"])
        fs.sort(key=lambda f: (f["path"], f["line"]))
        entries.append({"summary": tk["summary"], "categories": tk["labels"][1:], "findings": fs})
    if not entries:
        sys.exit("no deferred tickets")
    entries.sort(key=lambda e: (e["findings"][0]["path"], e["findings"][0]["line"]))
    lowest = max(priorities, key=RANK.get)
    lines = [f"# {lowest}-severity defects in {name}", "",
             f"Paths and line numbers refer to commit `{run['commit']}`.", "",
             f"The file lists {len(entries)} defects, sorted by the first file each one touches.", ""]
    for n, e in enumerate(entries, 1):
        lines += [f"## {n}. {e['summary']}", "", f"Categories are {', '.join(e['categories'])}.", ""]
        for f in e["findings"]:
            symbol = f" `{f['symbol']}`" if f["symbol"] else ""
            lines.append(f"- `{f['path']}:{f['line']}`{symbol} {' '.join(f['text'].split())}")
        lines.append("")
    os.makedirs(f"{t}/bundle", exist_ok=True)
    path = f"{t}/bundle/{name.lower()}-deferred-defects.md"
    open(path, "w").write("\n".join(lines).rstrip() + "\n")
    sentence = run.get("commit_sentence") or f"Paths and line numbers refer to commit {{{{{run['commit']}}}}}."
    ticket = {"summary": f"{len(entries)} {lowest.lower()}-severity defects across the {name} codebase, listed in the attachment"[:80],
              "type": "Bug", "priority": lowest,
              "labels": ["review-deep"] + sorted({c for e in entries for c in e["categories"]}),
              "description": "\n".join(["{panel:bgColor=#deebff}", "h3. Context",
                                        f"The attached file lists {len(entries)} {lowest.lower()}-severity defects in the {name} codebase. "
                                        "Each entry names the files and lines involved and describes the defect.",
                                        "{panel}", "", "h3. Details", sentence]),
              "attachment": path}
    json.dump(ticket, open(f"{t}/bundle/ticket.json", "w"), indent=1)
    print(f"bundled {len(entries)} tickets, {sum(len(e['findings']) for e in entries)} findings, into {path}")
    print(f"summary ({len(ticket['summary'])} chars): {ticket['summary']}")


if __name__ == "__main__":
    main()
