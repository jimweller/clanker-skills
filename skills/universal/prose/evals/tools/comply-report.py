#!/usr/bin/env python3
"""Triages a compliance run by diffing the editor's notes against the judge's findings.

The two enumerations disagree in four distinct ways, and each one points at a
different repair in the contract. That is the whole reason both sides enumerate.

    fired-then-over-applied   The editor applied style-rule R and the judge says
                              an exemption covered the span. The exemption is
                              too weak, or its markers read as an unconditional
                              ban.

    held-then-violation       The editor declined to apply R on an exemption and
                              the judge says the exemption did not reach. The
                              exemption is too broad.

    unseen-violation          The judge cites R and R appears nowhere in the
                              trace. The editor never noticed, so R's markers
                              are incomplete or the rule is not reaching it.

    self-inflicted            The violating span is absent from the original, so
                              the rewrite created it. The highest-value class,
                              because the contract caused the defect it bans.

Cases where the judge reported nothing need no reading and are counted only.

Usage
    tools/comply-report.py RESULT_JSON [--show N] [--rule NAME]
"""

import argparse
import collections
import json
import pathlib
import re
import sys

SECTION = re.compile(r"<<<(NOTES|REWRITE|FINDINGS)>>>")
VERDICT = re.compile(r"VERDICT\s+violations=(\d+)\s+over-applied=(\d+)", re.I)
EVAL_ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCK = re.compile(r"<prose-contract>(.*?)</prose-contract>", re.DOTALL)


def known_ids() -> set:
    """Every PC- id the contract defines, so an invented one is visible in the report.

    A rule named in free text could be wrong in a way nothing detected. An id either
    exists or it does not, so a judge citing PC-something-plausible now surfaces as an
    unknown rather than as a finding against a rule that was never written.
    """
    contract = EVAL_ROOT.parents[5] / "configs" / "claude-code" / "claude_md.md"
    blocks = BLOCK.findall(contract.read_text())
    if len(blocks) != 1:
        raise LookupError(f"expected 1 <prose-contract> block, found {len(blocks)}")
    return set(re.findall(r"^- `(PC-[a-z0-9-]+)`", blocks[0], re.MULTILINE))


def norm(rule: str) -> str:
    """Rules are named by PC- id now, so matching is exact rather than fuzzy.

    Before ids this stripped case and punctuation to reconcile two sessions naming one
    rule differently, and it still could not merge a short name with a long one. One run
    scored `trailing supplements` and `trailing supplements that hang a second beat on a
    finished clause` as two rules at 3 each instead of one at 6, and did that to three
    rules. Case folding is all that remains, because an id is already canonical.
    """
    return rule.strip().lower()


def split_artifact(text: str) -> dict:
    parts, last, pos = {}, None, 0
    for m in SECTION.finditer(text):
        if last:
            parts[last] = text[pos:m.start()].strip()
        last, pos = m.group(1), m.end()
    if last:
        parts[last] = text[pos:].strip()
    return parts


def parse_trace(block: str):
    """Reads the editor's notes, which it writes to a file rather than to stdout.

    Keeping notes out of stdout matters twice. The judge grades only the rewrite, and
    the rewrite is what a real `/prose` run prints, so the measured artifact is the
    real one. An earlier version had the editor print its reasoning inline, which the
    judge then graded as prose.
    """
    fired, held, malformed = {}, {}, "NO NOTES FILE" in block
    for line in block.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].upper() == "FIRED":
            fired[norm(cells[1])] = cells[1]
        elif cells[0].upper() == "HELD":
            held[norm(cells[1])] = cells[1]
    return fired, held, malformed


def parse_findings(block: str):
    out = []
    for line in block.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4 or cells[0].upper() != "FINDING":
            continue
        kind = cells[1].lower()
        if kind not in ("violation", "over-applied"):
            continue
        out.append({"kind": kind, "rule": cells[2], "span": cells[3].strip('"'),
                    "why": cells[4] if len(cells) > 4 else ""})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json")
    ap.add_argument("--show", type=int, default=3, help="examples per bucket")
    ap.add_argument("--rule", help="only this style-rule")
    args = ap.parse_args()

    rows = (json.loads(pathlib.Path(args.result_json).read_text())
            .get("results") or {}).get("results") or []
    if not rows:
        print("no results", file=sys.stderr)
        return 1

    ids = known_ids()
    buckets = collections.defaultdict(list)
    per_rule = collections.defaultdict(collections.Counter)
    unknown = collections.Counter()
    n = clean = malformed_n = unparsed = 0
    viol_total = over_total = 0

    for r in rows:
        out = ((r.get("response") or {}).get("output") or "")
        if not isinstance(out, str) or "<<<FINDINGS>>>" not in out:
            unparsed += 1
            continue
        n += 1
        case = ((r.get("testCase") or {}).get("vars") or {}).get("__description") \
            or (r.get("testCase") or {}).get("description") or "?"
        parts = split_artifact(out)
        source = ((r.get("testCase") or {}).get("vars") or {}).get("passage", "")
        fired, held, malformed = parse_trace(parts.get("NOTES", ""))
        malformed_n += malformed
        findings = parse_findings(parts.get("FINDINGS", ""))

        if not findings:
            clean += 1
            continue

        for f in findings:
            key = norm(f["rule"])
            if args.rule and args.rule.lower() not in f["rule"].lower():
                continue
            if f["kind"] == "over-applied":
                over_total += 1
                bucket = "fired-then-over-applied" if key in fired else "over-applied-untraced"
            else:
                viol_total += 1
                span = f["span"].strip()
                if span and span not in source:
                    bucket = "self-inflicted"
                elif key in held:
                    bucket = "held-then-violation"
                elif key in fired:
                    bucket = "fired-then-violation"
                else:
                    bucket = "unseen-violation"
            if f["rule"] not in ids:
                unknown[f["rule"]] += 1
            per_rule[f["rule"]][bucket] += 1
            buckets[bucket].append((case, f))

    print(f"cases parsed {n}, clean {clean}, missing notes {malformed_n}, "
          f"unparsed responses {unparsed}")
    print(f"violations {viol_total}, over-applications {over_total}")
    if unknown:
        print(f"\n{sum(unknown.values())} findings cite an id the contract does not define:")
        for rid, k in unknown.most_common(10):
            print(f"  {k:>3}  {rid!r}")
    print()

    order = ["self-inflicted", "fired-then-over-applied", "held-then-violation",
             "unseen-violation", "fired-then-violation", "over-applied-untraced"]
    print("bucket                     n")
    for b in order:
        if buckets[b]:
            print(f"{b:<26} {len(buckets[b])}")

    print("\nstyle-rules by total findings")
    ranked = sorted(per_rule.items(), key=lambda kv: -sum(kv[1].values()))
    for rule, counts in ranked[:15]:
        detail = " ".join(f"{k}={v}" for k, v in counts.most_common())
        print(f"{sum(counts.values()):>3}  {rule}  [{detail}]")

    for b in order:
        if not buckets[b]:
            continue
        print(f"\n--- {b} ---")
        for case, f in buckets[b][:args.show]:
            print(f"[{case}] {f['rule']}")
            print(f"    span  {f['span'][:160]}")
            print(f"    why   {f['why'][:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
