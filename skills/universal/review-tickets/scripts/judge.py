#!/usr/bin/env python3
"""Judge and edit tickets against the code, one isolated model process per ticket.

    python3 judge.py RUN_DIR [--ids FILE] [--merged] [--critical] [--model M --effort E]

Default: every unit in tickets/units.jsonl goes to the judge model (run.json models.judge, Opus
at xhigh by default). --ids limits the run to a JSON list of IDs. --merged judges the merged
tickets in tickets/merges.json instead, as whole tickets. --critical runs the second model
(models.critical, Fable at high by default) on every ticket whose judged severity is still
Critical, and records its verdict and severity next to the first answer.

The judge reads the clean checkout at run.json "checkout", never the live tree, so review state,
editor caches, and agent-instruction files stay out of reach. Every answer passes content_errors
before it is accepted. Results merge into tickets/judge/results.json (or merged.json), keyed by
ID, so a partial rerun keeps earlier answers for the IDs it did not touch.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool  # noqa: E402
from common import load_json, load_run, lower, prompt, read_jsonl, tickets_dir  # noqa: E402
from evidence import in_code  # noqa: E402

PLACEHOLDER = re.compile(r"^(test|todo|tbd|x|a|b|n/a|na|none|placeholder|example|\.+)$", re.I)
META = re.compile(r"\b(reviewer|reviewers|verifier|this ticket|the ticket|this finding|the finding|original text|was edited|been edited)\b", re.I)
LOCATION = re.compile(r"^[^\s:]+:\d+(-\d+)?$")
EVIDENCE = {"type": "array", "items": {"type": "object", "properties": {"location": {"type": "string"}, "code": {"type": "string"}},
                                       "required": ["location", "code"]}}
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["true", "false"]},
        "basis": {"type": "string", "enum": ["confirmed", "refuted", "insufficient_evidence"]},
        "reason": {"type": "string"},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "action": {"type": "string", "enum": ["keep", "edit", "delete"]},
            "text": {"type": "string"}, "reason": {"type": "string"}, "evidence": EVIDENCE},
            "required": ["id", "action", "text", "reason", "evidence"]}},
        "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
        "severity_reason": {"type": "string"},
    },
    "required": ["verdict", "basis", "reason", "summary", "findings", "severity", "severity_reason"],
}


def norm(s):
    return " ".join(str(s).split())


def content_errors(r, unit, in_code_check):
    errs = []
    ok_basis = ["confirmed"] if r["verdict"] == "true" else ["refuted", "insufficient_evidence"]
    if r["basis"] not in ok_basis:
        errs.append(f'basis "{r["basis"]}" does not match verdict "{r["verdict"]}"')
    if len(str(r["reason"]).strip()) < 80 or PLACEHOLDER.match(str(r["reason"]).strip()):
        errs.append("reason is a placeholder or too short to name the code read")
    if len(str(r["severity_reason"]).strip()) < 30:
        errs.append("severity_reason is too short")
    ids = [f["id"] for f in r["findings"]]
    want = [m["id"] for m in unit["members"]]
    missing = [i for i in want if i not in ids]
    extra = [i for i in ids if i not in want]
    if missing:
        errs.append(f"findings is missing {', '.join(missing)}")
    if extra:
        errs.append(f"findings has unknown ids {', '.join(extra)}")
    if len(set(ids)) != len(ids):
        errs.append("findings lists an id more than once")
    for f in r["findings"]:
        m = next((x for x in unit["members"] if x["id"] == f["id"]), None)
        if not m:
            continue
        if f["action"] == "keep":
            claims = len(re.findall(r"[.!?](\s|$)", norm(m["text"])))
            if len(str(f["reason"]).strip()) < max(40, 30 * claims) or PLACEHOLDER.match(str(f["reason"]).strip()):
                errs.append(f"{f['id']} is keep with a reason too short to account for each of its claims")
        if f["action"] == "edit":
            if not norm(f["text"]):
                errs.append(f"{f['id']} is edit with empty text, so use delete")
            elif norm(f["text"]) == norm(m["text"]):
                errs.append(f"{f['id']} is edit but its text is unchanged, so use keep")
            if len(norm(f["text"])) > len(norm(m["text"])) * 1.3 + 80:
                errs.append(f"{f['id']} edit is far longer than the original, so change only what the code settles")
            if META.search(f["text"]) and not META.search(m["text"]):
                errs.append(f"{f['id']} edit mentions the review or the editing")
        if f["action"] != "keep":
            if len(str(f["reason"]).strip()) < 20 or PLACEHOLDER.match(str(f["reason"]).strip()):
                errs.append(f"{f['id']} reason is a placeholder or too short")
            if not f["evidence"]:
                errs.append(f"{f['id']} is {f['action']} with no evidence")
            for e in f["evidence"]:
                if not LOCATION.match(str(e["location"]).strip()):
                    errs.append(f"{f['id']} evidence location \"{str(e['location'])[:80]}\" is not path:line")
                elif PLACEHOLDER.match(str(e["code"]).strip()) or not in_code_check(e):
                    errs.append(f"{f['id']} evidence at {str(e['location'])[:80]} is not the code at that location, so copy the lines exactly")
    live = sum(1 for f in r["findings"] if f["action"] != "delete")
    if r["verdict"] == "true" and not live:
        errs.append("verdict is true but every finding is deleted")
    if r["verdict"] == "false" and live:
        errs.append("verdict is false but some findings are kept or edited")
    s = str(r["summary"]).strip()
    if r["verdict"] == "true":
        if not 15 <= len(s) <= 80:
            errs.append(f"summary is {len(s)} characters, it must be 15 to 80")
        if s.endswith(".") or "\n" in s:
            errs.append("summary ends with a trailing period or spans lines")
        if META.search(s):
            errs.append("summary mentions the review or the editing")
    return errs


def payload(item, run):
    paths = sorted({m.get("path", item.get("path")) for m in item["members"]})
    where = paths[0] if len(paths) == 1 else "one of " + ", ".join(paths)
    findings = "\n\n".join(f"[{m['id']}] {m.get('path', item.get('path'))}:{m['line']}{' ' + m['symbol'] if m.get('symbol') else ''}\n{m['text']}"
                           for m in item["members"])
    return prompt("judge.txt", checkout=run["checkout"], commit=run["commit"], where=where,
                  summary=item.get("summary") or "(none yet)", findings=findings)


def unit_items(t, ids):
    units = read_jsonl(f"{t}/units.jsonl")
    out = []
    for u in units:
        if ids and u["id"] not in ids:
            continue
        summary = u["issue_title"] if not u["split"] and len(u["issue_title"]) <= 80 else ""
        out.append({"id": u["id"], "path": u["path"], "severity": u["severity"], "summary": summary,
                    "members": [dict(m, path=u["path"]) for m in u["members"]]})
    return out


def merged_items(t, ids):
    units = {u["id"]: u for u in read_jsonl(f"{t}/units.jsonl")}
    edits = load_json(f"{t}/edits.json", {})
    merges = load_json(f"{t}/merges.json", {})
    out = []
    for gid, g in sorted(merges.items()):
        if ids and gid not in ids:
            continue
        members = []
        for uid in g["units"]:
            e = edits.get(uid, {})
            for m in units[uid]["members"]:
                if m["id"] not in set(e.get("deleted", [])):
                    members.append(dict(m, path=units[uid]["path"], text=e.get("texts", {}).get(m["id"], m["text"])))
        members.sort(key=lambda m: (m["path"], m["line"]))
        severity = g.get("priority") or g["severity"]
        out.append({"id": gid, "severity": severity, "summary": g["summary"], "members": members})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--ids")
    ap.add_argument("--merged", action="store_true")
    ap.add_argument("--critical", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    a = ap.parse_args()
    d = os.path.abspath(os.path.expanduser(a.run_dir))
    run = load_run(d)
    t = tickets_dir(d)
    ids = set(json.load(open(a.ids))) if a.ids else None
    items = merged_items(t, ids) if a.merged else unit_items(t, ids)
    out_path = f"{t}/judge/{'merged' if a.merged else 'results'}.json"
    os.makedirs(f"{t}/judge", exist_ok=True)
    results = {r["id"]: r for r in load_json(out_path, [])}
    by_id = {i["id"]: i for i in items}

    def check(r, task):
        return content_errors(r, by_id[task["id"]], lambda e: in_code(e, run["repo"], run["commit"]))

    if a.critical:
        todo = [i for i in items if i["id"] in results and results[i["id"]]["editor"]["ok"]
                and results[i["id"]]["editor"]["result"]["verdict"] == "true"
                and lower(i["severity"], results[i["id"]]["editor"]["result"]["severity"]) == "Critical"]
        model, effort = a.model or run["models"]["critical"][0], a.effort or run["models"]["critical"][1]
    else:
        todo = items
        model, effort = a.model or run["models"]["judge"][0], a.effort or run["models"]["judge"][1]
    if not todo:
        print("nothing to judge")
        return
    tasks = [{"id": i["id"], "prompt": payload(i, run)} for i in todo]
    out = pool.run(tasks, model=model, effort=effort, schema=SCHEMA, check=check, out_dir=f"{t}/judge",
                   cwd=run["checkout"], concurrency=run["concurrency"])
    for iid, o in out.items():
        if a.critical:
            results[iid]["critical"] = o
        else:
            results[iid] = {"id": iid, "editor": o, "critical": results.get(iid, {}).get("critical")}
    json.dump(sorted(results.values(), key=lambda r: r["id"]), open(out_path, "w"), indent=1)
    print(f"{'critical' if a.critical else 'judged'} {len(out)}, ok {sum(o['ok'] for o in out.values())}, "
          f"list cost ${pool.cost(out)}, wrote {out_path}")


if __name__ == "__main__":
    main()
