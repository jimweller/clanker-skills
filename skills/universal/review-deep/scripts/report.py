#!/usr/bin/env python3
"""Write the review report from the verified issues. No model calls.

    python3 report.py RUN_DIR

Writes report.md to the run directory: the finding and issue counts, every verified issue with
the verifier's verdict and the final severity (the lower of the verifier's and the second
check's ratings), the refuted and unverifiable issues with the verifier's reason, the files no
arm reviewed, and ocr's skipped ledger. Category counts are label counts: an issue carries every
area that raised one of its findings, so category rows add up to more than the issues.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RANK, load_run, lower, read_jsonl, run_dir  # noqa: E402


def esc(s):
    return " ".join(str(s or "").split()).replace("|", "\\|")


def main():
    d = run_dir()
    run = load_run(d)
    findings = read_jsonl(f"{d}/findings.jsonl")
    issues = {i["id"]: i for i in read_jsonl(f"{d}/issues.jsonl")}
    verify = {v["id"]: v for v in read_jsonl(f"{d}/verify/results.jsonl")} if os.path.exists(f"{d}/verify/results.jsonl") else {}
    second = {v["id"]: v for v in read_jsonl(f"{d}/verify/second.jsonl")} if os.path.exists(f"{d}/verify/second.jsonl") else {}
    confirmed = sorted((k for k, v in verify.items() if v["verdict"] == "true"),
                       key=lambda k: (RANK[lower(verify[k]["severity"], (second.get(k) or {}).get("severity"))], k))
    rejected = sorted(k for k, v in verify.items() if v["verdict"] != "true")
    out = [f"# Review of {os.path.basename(run['repo'])} at {run['commit'][:12]}", "",
           f"Reviewers produced {len(findings)} findings, grouped into {len(issues)} issues. "
           f"{len(verify)} issues were verified against the code, and {len(confirmed)} were confirmed.", "",
           "| Severity | Issues | Verified | Confirmed |", "| -- | --: | --: | --: |"]
    for s in RANK:
        ids = [k for k, i in issues.items() if i["severity"] == s]
        out.append(f"| {s} | {len(ids)} | {sum(1 for k in ids if k in verify)} | {sum(1 for k in ids if k in confirmed)} |")
    category = {"bug": "correctness", "maintainability": "quality", "test": "testing", "documentation": "quality"}
    labels = Counter(c for k in confirmed for c in {category.get(a, a) for a in issues[k]["areas"]})
    out += ["", "Confirmed issues carrying each category label, where one issue can carry several:", "",
            "| Category | Confirmed issues |", "| -- | --: |"] + [f"| {a} | {n} |" for a, n in labels.most_common()]
    out += ["", "## Confirmed", "", "| ID | Severity | Second check | Location | Title |", "| -- | -- | -- | -- | -- |"]
    for k in confirmed:
        v, s2 = verify[k], second.get(k)
        out.append(f"| {k} | {lower(v['severity'], (s2 or {}).get('severity'))} | {(s2 or {}).get('severity', '')} | "
                   f"`{issues[k]['location']}` | {esc(issues[k]['title'])} |")
    out += ["", "## Refuted or unverifiable", "", "| ID | Basis | Reason |", "| -- | -- | -- |"]
    out += [f"| {k} | {verify[k]['basis']} | {esc(verify[k]['reason'])[:300]} |" for k in rejected]
    state = run.get("state_dir", "")
    ledger = {l.strip() for l in open(f"{state}/ledger.txt")} if os.path.exists(f"{state}/ledger.txt") else set()
    reviewed = {l.strip() for l in open(f"{state}/reviewed.txt")} if os.path.exists(f"{state}/reviewed.txt") else set()
    never = sorted(ledger - reviewed) if reviewed else []
    skipped = [l.rstrip("\n") for l in open(f"{state}/skipped.txt")] if os.path.exists(f"{state}/skipped.txt") else []
    out += ["", "## Coverage", "", f"{len(ledger)} reviewable files, {len(never)} never marked reviewed by any arm, "
            f"{len(skipped)} files left out by ocr."] + [f"- never reviewed `{p}`" for p in never]
    open(f"{d}/report.md", "w").write("\n".join(out) + "\n")
    print(f"wrote {d}/report.md: {len(confirmed)} confirmed, {len(rejected)} refuted or unverifiable")


if __name__ == "__main__":
    main()
