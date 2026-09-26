#!/usr/bin/env python3
"""Compare a posted ticket, read back from Jira as ADF, against its ticket file. No Jira calls.

    python3 readback.py TICKET_JSON FIELDS_JSON

TICKET_JSON is a tickets/final/<ID>.json file. FIELDS_JSON holds the issue's fields as Jira
returns them with the description in ADF: summary, issuetype.name, priority.name, labels, and
description. Any Jira client that can fetch an issue as ADF produces it. Prints each mismatch and
exits 1 when there is one.

Checks: summary, type, mapped priority, labels as a set, every {{...}} span present as an ADF
code mark, every {code} block present as a codeBlock, the block count, and no wiki markup left
unrendered in plain text. Jira drops the escaping backslash only before { } [ ] * | !, so the
expected span keeps any other backslash, such as the one in "a\\"b". A span whose content ends in a
backslash is invisible to expected(), because its closing braces look escaped; checks.py reports such
a span as unbalanced before posting.
"""
import json
import re
import sys

PRIORITY = {"Critical": "Highest", "High": "High", "Medium": "Medium", "Low": "Low"}


def expected(desc):
    blocks = re.findall(r"\{code:[a-z#]+\}\n(.*?)\n\{code\}", desc, re.S)
    prose = re.sub(r"\{code:[a-z#]+\}\n.*?\n\{code\}", "", desc, flags=re.S)
    spans = [re.sub(r"\\([{}\[\]*|!])", r"\1", s) for s in re.findall(r"(?<!\\)\{\{(.+?)(?<!\\)\}\}", prose)]
    return spans, blocks


def nodes(node, out):
    if isinstance(node, dict):
        if node.get("type") == "codeBlock":
            out["blocks"].append("".join(c.get("text", "") for c in node.get("content", []) or []))
            return out
        if node.get("type") == "text":
            marks = [m["type"] for m in node.get("marks", []) or []]
            out["code" if "code" in marks else "text"].append(node["text"])
        for v in node.values():
            nodes(v, out)
    elif isinstance(node, list):
        for v in node:
            nodes(v, out)
    return out


def compare(ticket, fields, priority=PRIORITY):
    problems = []
    if fields.get("summary") != ticket["summary"]:
        problems.append(f"summary {fields.get('summary')!r}")
    if (fields.get("issuetype") or {}).get("name") != ticket["type"]:
        problems.append(f"type {(fields.get('issuetype') or {}).get('name')}")
    if (fields.get("priority") or {}).get("name") != priority[ticket["priority"]]:
        problems.append(f"priority {(fields.get('priority') or {}).get('name')}")
    if sorted(fields.get("labels") or []) != sorted(ticket["labels"]):
        problems.append(f"labels {fields.get('labels')}")
    got = nodes(fields.get("description"), {"code": [], "text": [], "blocks": []})
    spans, blocks = expected(ticket["description"])
    pool = list(got["code"])
    for s in spans:
        if s in pool:
            pool.remove(s)
        else:
            problems.append(f"code span missing: {s[:60]!r}")
    for b in blocks:
        body = b.split("\n", 1)[1] if b.startswith("// ") else b
        if not any(body.strip() in nb for nb in got["blocks"]):
            problems.append(f"code block missing: {b.splitlines()[0][:60]!r}")
    if len(got["blocks"]) != len(blocks):
        problems.append(f"{len(got['blocks'])} code blocks, expected {len(blocks)}")
    if any("{{" in x or "{code" in x or "{panel" in x for x in got["text"]):
        problems.append("unrendered wiki markup in text")
    return problems


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    ticket = json.load(open(sys.argv[1]))
    data = json.load(open(sys.argv[2]))
    problems = compare(ticket, data.get("fields", data))
    for p in problems:
        print(p)
    print("ok" if not problems else f"{len(problems)} mismatches")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
