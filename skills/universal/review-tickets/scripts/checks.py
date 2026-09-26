#!/usr/bin/env python3
"""Scripted checks on the assembled ticket files. No model calls. Exits 1 when any check fails.

    python3 checks.py RUN_DIR

Checks every ticket in tickets/final/, deferred ones included: summary present, at most 80
characters, and unique; panel and code markup balanced; every code block byte-identical to git at
the reviewed commit; no unconverted markdown code span; monospace braces balanced; no {{...}} span
next to a character Jira was not seen to render; no unescaped brace in prose; every location in
bounds and shown in the Context; labels from the category set; priority and type valid.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_run, run_dir, tickets_dir  # noqa: E402
from evidence import lines_at  # noqa: E402
from wiki import SAFE_AFTER, SAFE_BEFORE  # noqa: E402

CATEGORIES = {"correctness", "quality", "testing", "security", "architecture", "data", "ops", "performance", "solid"}
CODE = re.compile(r"\{code:[a-z#]+\}\n// (?P<path>[^\s:]+):(?P<start>\d+)-(?P<end>\d+)\n(?P<body>.*?)\n\{code\}", re.S)


def check(ticket, source):
    i, s, d = ticket["id"], ticket["summary"], ticket["description"]
    problems = []
    if not s:
        problems.append(f"{i}: no summary")
    elif len(s) > 80:
        problems.append(f"{i}: summary {len(s)} chars")
    if d.count("{panel:bgColor=#deebff}") != 1 or d.count("{panel}") != 1:
        problems.append(f"{i}: panel markup unbalanced")
    blocks = CODE.findall(d)
    if not blocks or len(blocks) != d.count("{code:") or d.count("{code}") != len(blocks):
        problems.append(f"{i}: code blocks malformed")
    for m in CODE.finditer(d):
        lines = source(m.group("path"))
        a, b = int(m.group("start")), int(m.group("end"))
        if lines is None or "\n".join(lines[a - 1:b]) != m.group("body"):
            problems.append(f"{i}: code block differs from {m.group('path')}:{a}-{b}")
    prose = CODE.sub("", d)
    if re.search(r"`[^`\n]+`", re.sub(r"\{\{.*?(?<!\\)\}\}", "", prose)):
        problems.append(f"{i}: unconverted code span left in prose")
    for mm in re.finditer(r"(?<!\\)\{\{(.+?)(?<!\\)\}\}", prose):
        after, before = prose[mm.end():mm.end() + 1] or " ", prose[mm.start() - 1:mm.start()] or " "
        if after not in SAFE_AFTER or before not in SAFE_BEFORE | {"*"}:
            problems.append(f"{i}: monospace span touches {before!r} or {after!r}, which Jira may not render")
    if len(re.findall(r"(?<!\\)\{\{", prose)) != len(re.findall(r"(?<!\\)\}\}", prose)):
        problems.append(f"{i}: monospace unbalanced")
    if re.search(r"(?<![\\{])\{(?!\{|panel|code)", prose.replace("{{", "").replace("}}", "")):
        problems.append(f"{i}: unescaped brace in prose")
    for loc in ticket["locations"]:
        path, _, line = loc.rpartition(":")
        lines = source(path)
        if lines is None or not line.isdigit() or not 1 <= int(line) <= len(lines):
            problems.append(f"{i}: location missing or out of bounds: {loc}")
        elif f"{{{{{loc}}}}}" not in d:
            problems.append(f"{i}: location not shown in Context: {loc}")
    if ticket["labels"][:1] != ["review-deep"] or len(ticket["labels"]) < 2 or not set(ticket["labels"][1:]) <= CATEGORIES:
        problems.append(f"{i}: labels {ticket['labels']}")
    if ticket["priority"] not in {"Critical", "High", "Medium", "Low"} or ticket["type"] not in {"Bug", "Task"}:
        problems.append(f"{i}: priority/type {ticket['priority']}/{ticket['type']}")
    return problems


def main():
    d = run_dir()
    run = load_run(d)
    t = tickets_dir(d)
    manifest = json.load(open(f"{t}/final/manifest.json"))
    tickets = [json.load(open(f"{t}/final/{m['id']}.json")) for m in manifest if "summary_source" in m]
    problems = [p for tk in tickets for p in check(tk, lambda p: lines_at(run["repo"], run["commit"], p))]
    dupes = [s for s, n in Counter(tk["summary"] for tk in tickets).items() if s and n > 1]
    problems += [f"duplicate summary: {s!r}" for s in dupes]
    print(f"tickets checked {len(tickets)}, problems {len(problems)}")
    for p in problems:
        print(" -", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
