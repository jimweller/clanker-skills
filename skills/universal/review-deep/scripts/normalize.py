#!/usr/bin/env python3
"""Flatten a review into one list of findings with stable IDs. No model calls.

    python3 normalize.py RUN_DIR

Reads every merged <label>-<area>.md file and ocr-scan.json in run.json "state_dir" and writes
findings.jsonl to the run directory, one finding per line with id, component, src, area,
severity, path, line, symbol, text, and ocr's suggestion. A finding on a file outside the ledger
goes to the component whose files share the longest directory prefix. Exits 1 when any finding
bullet fails to parse, so nothing is dropped silently.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_run, run_dir, write_jsonl  # noqa: E402

SEV = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}
MERGED = re.compile(r"^([a-z0-9]+)-([a-z]+)\.md$")
FULL = re.compile(r"^- \*\*(Critical|High|Medium|Low)\*\* `([^`]+?):(\d+)(?:-\d+)?` `([^`]*)` (.+)$")
BARE = re.compile(r"^- \*\*(Critical|High|Medium|Low)\*\* `([^`]+?):(\d+)(?:-\d+)?` (.+)$")


def one_line(t):
    return " ".join((t or "").split())


def collect(state):
    rows, bad = [], []
    for f in sorted(glob.glob(f"{state}/*.md")):
        m = MERGED.match(os.path.basename(f))
        if not m:
            continue
        src, area = m.groups()
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line.startswith("- **"):
                continue
            full, bare = FULL.match(line), BARE.match(line)
            if full:
                sev, path, ln, sym, text = full.groups()
            elif bare:
                (sev, path, ln, text), sym = bare.groups(), ""
            else:
                bad.append(f"{os.path.basename(f)}: {line[:160]}")
                continue
            rows.append(dict(src=src, area=area, severity=SEV[sev.lower()], path=path, line=int(ln), symbol=sym, text=one_line(text)))
    if os.path.exists(f"{state}/ocr-scan.json"):
        for c in json.load(open(f"{state}/ocr-scan.json", encoding="utf-8")).get("comments", []):
            rows.append(dict(src="ocr", area=c.get("category") or "unknown", severity=SEV.get((c.get("severity") or "").lower(), "Low"),
                             path=c["path"], line=c.get("start_line") or 0, symbol="", text=one_line(c.get("content")),
                             suggestion=(c.get("suggestion_code") or "").strip()))
    comp = {}
    for f in sorted(glob.glob(f"{state}/components/c*.txt")):
        for p in open(f, encoding="utf-8").read().splitlines():
            if p.strip():
                comp[p.strip()] = os.path.basename(f)[:-4]

    def component(path):
        if path in comp:
            return comp[path]
        d = path.split("/")[:-1]
        best, score = None, -1
        for p, c in sorted(comp.items()):
            q = p.split("/")[:-1]
            n = 0
            while n < min(len(d), len(q)) and d[n] == q[n]:
                n += 1
            if n > score:
                best, score = c, n
        return best

    for r in rows:
        r["component"] = component(r["path"])
    rows.sort(key=lambda r: (r["component"] or "", r["path"], r["line"], r["src"], r["area"]))
    width = len(str(len(rows)))
    for i, r in enumerate(rows, 1):
        r["id"] = f"F{i:0{width}d}"
    return rows, bad


def main():
    d = run_dir()
    run = load_run(d)
    rows, bad = collect(run["state_dir"])
    if bad:
        print(f"UNPARSED {len(bad)} finding bullets:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        sys.exit(1)
    write_jsonl(f"{d}/findings.jsonl", [{k: r[k] for k in ("id", "component", "src", "area", "severity", "path", "line", "symbol", "text",
                                                            "suggestion") if k in r} for r in rows])
    print(f"findings {len(rows)}, by source {dict(Counter(r['src'] for r in rows))}, by severity {dict(Counter(r['severity'] for r in rows))}")
    print(f"components {len({r['component'] for r in rows})}")


if __name__ == "__main__":
    main()
