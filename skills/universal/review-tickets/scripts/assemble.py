#!/usr/bin/env python3
"""Assemble one Jira ticket file per unit or merged group. No model calls.

    python3 assemble.py RUN_DIR

Reads tickets/units.jsonl, edits.json, merges.json, merge_edits.json, and decisions.json. Writes
tickets/final/<ID>.json, tickets/final/manifest.json, and tickets/postable.json.

A ticket's Context is one bullet per kept finding, in the reviewer's words after the judge's edits,
converted to Jira wiki markup by wiki.to_wiki. Details is the commit sentence and up to MAX_BLOCKS
code windows copied from git at the reviewed commit, taken round-robin across the ticket's files.
A unit that is not ready is skipped. A merged group becomes <ISSUE>-M<n>, and its units are
flagged merged-into. decisions.json "drop" removes tickets, and "defer_priorities" keeps tickets
assembled and checked but flags them deferred and out of postable.json. A merged ticket's priority
is the lower of its group's rating, its judge-editor rating, and the highest priority among its
units.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CATEGORY, RANK, load_json, load_run, read_jsonl, run_dir, tickets_dir  # noqa: E402
from evidence import lines_at  # noqa: E402
from wiki import code as wiki_code  # noqa: E402
from wiki import to_wiki  # noqa: E402

MAX_BLOCKS = 4
BEFORE, AFTER = 2, 5
# Languages seen rendering in posted tickets. Any other extension uses "none", which Jira shows as
# plain monospace; an unknown language name is not guaranteed to render.
LANG = {".ts": "javascript", ".tsx": "javascript", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".sh": "bash", ".py": "python", ".sql": "sql", ".cs": "csharp"}


def windows(n, lines):
    spans = []
    for line in sorted(lines):
        a, b = max(1, line - BEFORE), min(n, line + AFTER)
        if spans and a <= spans[-1][1] + 1:
            spans[-1] = (spans[-1][0], max(spans[-1][1], b))
        else:
            spans.append((a, b))
    return spans


def render(run, tid, issue, typ, areas, priority, summary, source, members, defer, out_dir):
    source_of = lambda p: lines_at(run["repo"], run["commit"], p)
    context = []
    for m in members:
        head = f"{{{{{m['path']}:{m['line']}}}}}" + (" " + wiki_code(m["symbol"]) if m.get("symbol") else "")
        context.append(f"* {head} {to_wiki(m['text'])}")
    paths = list(dict.fromkeys(m["path"] for m in members))
    per_path = {p: windows(len(source_of(p)), [m["line"] for m in members if m["path"] == p]) for p in paths}
    spans, depth = [], 0
    while len(spans) < MAX_BLOCKS and any(depth < len(v) for v in per_path.values()):
        for p in paths:
            if depth < len(per_path[p]) and len(spans) < MAX_BLOCKS:
                spans.append((p, *per_path[p][depth]))
        depth += 1
    total = sum(len(v) for v in per_path.values())
    flags = [f"code-windows-capped-{total}-to-{MAX_BLOCKS}"] if total > MAX_BLOCKS else []
    spans.sort(key=lambda x: (paths.index(x[0]), x[1]))
    sentence = run.get("commit_sentence") or f"Paths and line numbers refer to commit {{{{{run['commit']}}}}}."
    details = [sentence, ""]
    for p, a, b in spans:
        lang = LANG.get(os.path.splitext(p)[1], "none")
        details += [f"{{code:{lang}}}", f"// {p}:{a}-{b}", "\n".join(source_of(p)[a - 1:b]), "{code}", ""]
    description = "\n".join(["{panel:bgColor=#deebff}", "h3. Context", *context, "{panel}", "", "h3. Details", *details]).rstrip() + "\n"
    if not summary:
        flags.append("no-summary")
    if priority in defer:
        flags.append("deferred")
    ticket = {"id": tid, "issue": issue, "summary": summary, "summary_source": source, "priority": priority, "type": typ,
              "labels": ["review-deep"] + sorted({CATEGORY.get(a, a) for a in areas}),
              "locations": [f"{m['path']}:{m['line']}" for m in members], "members": [m["id"] for m in members],
              "description": description, "flags": flags}
    json.dump(ticket, open(f"{out_dir}/{tid}.json", "w"), indent=1)
    return {"id": tid, "summary_source": source, "flags": flags, "members": len(members)}


def assemble(run, units, edits, merges, merge_edits, decisions, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".json"):
            os.remove(os.path.join(out_dir, f))
    drop, defer = decisions.get("drop", {}), set(decisions.get("defer_priorities", []))
    merged_into = {uid: gid for gid, g in merges.items() for uid in g["units"]}
    manifest, ready = [], {}
    for u in units:
        ed = edits.get(u["id"], {})
        if ed and ed["status"] != "ready":
            manifest.append({"id": u["id"], "flags": [ed["status"]]})
            continue
        if u["id"] in drop:
            manifest.append({"id": u["id"], "flags": ["dropped"], "reason": drop[u["id"]]})
            continue
        gone = set(ed.get("deleted", []))
        members = [dict(m, path=u["path"], text=ed.get("texts", {}).get(m["id"], m["text"])) for m in u["members"] if m["id"] not in gone]
        if not members:
            manifest.append({"id": u["id"], "flags": ["all-members-dropped"]})
            continue
        priority = ed.get("severity", u["severity"])
        ready[u["id"]] = (u, members, priority)
        if u["id"] in merged_into:
            manifest.append({"id": u["id"], "flags": [f"merged-into-{merged_into[u['id']]}"]})
            continue
        manifest.append(render(run, u["id"], u["issue"], u["type"], u["areas"], priority, ed.get("summary"), "editor" if ed else "none",
                               members, defer, out_dir))
    for gid, g in sorted(merges.items()):
        me = merge_edits.get(gid, {})
        if me and me["status"] != "ready":
            manifest.append({"id": gid, "flags": [me["status"]]})
            continue
        if gid in drop:
            manifest.append({"id": gid, "flags": ["dropped"], "reason": drop[gid]})
            continue
        parts = [ready[uid] for uid in g["units"] if uid in ready]
        if len(parts) < 2:
            raise SystemExit(f"merge {gid} has {len(parts)} ready units: {g['units']}")
        gone = set(me.get("deleted", []))
        members = sorted((dict(m, text=me.get("texts", {}).get(m["id"], m["text"])) for _, ms, _ in parts for m in ms if m["id"] not in gone),
                         key=lambda m: (m["path"], m["line"]))
        highest = min((p for _, _, p in parts), key=RANK.get)
        priority = max([g["severity"], highest] + ([me["severity"]] if me else []), key=RANK.get)
        u0 = parts[0][0]
        manifest.append(render(run, gid, u0["issue"], u0["type"], sorted({a for u, _, _ in parts for a in u["areas"]}), priority,
                               me.get("summary", g["summary"]), "merge", members, defer, out_dir))
    json.dump(manifest, open(f"{out_dir}/manifest.json", "w"), indent=1)
    return manifest


def main():
    d = run_dir()
    run = load_run(d)
    t = tickets_dir(d)
    units = read_jsonl(f"{t}/units.jsonl")
    manifest = assemble(run, units, load_json(f"{t}/edits.json", {}), load_json(f"{t}/merges.json", {}),
                        load_json(f"{t}/merge_edits.json", {}), load_json(f"{t}/decisions.json", {}), f"{t}/final")
    tickets = [m for m in manifest if "summary_source" in m]
    postable = sorted(m["id"] for m in tickets if "deferred" not in m["flags"])
    json.dump(postable, open(f"{t}/postable.json", "w"), indent=1)
    print(f"tickets {len(tickets)} ({sum(1 for m in tickets if m['summary_source'] == 'merge')} merged), "
          f"postable {len(postable)}, deferred {len(tickets) - len(postable)}")


if __name__ == "__main__":
    main()
