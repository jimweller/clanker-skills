#!/usr/bin/env python3
"""Builds the launder set, in two passes, with the judge doing the selecting.

The first version of this ranked paragraphs by marker density and counted
label-colon among the markers, so it preferentially picked paragraphs opening
"Finding:" or "New Customer Access (3):". Those are scorecards and rubrics
wearing paragraph clothing, and a prose contract has no business being scored on
them. The set it produced was 20 percent that shape.

So the heuristic is gone. Pass one writes every prose paragraph in the word band
to a pool. Judge the pool, then pass two keeps only the paragraphs the judge said needed
rewriting on every run. The selector reasons before it decides and judges the
writing rather than guessing at provenance, so a padded or templated paragraph
qualifies whoever wrote it.

Paragraphs come from <p> elements only. List items, table cells and headings are
structured content and never enter the pool.

Usage
    tools/build-launder-set.py --pool
    npx promptfoo@latest eval -c promptfooconfig.pool.yaml -o /tmp/pool.json
    tools/build-launder-set.py --select /tmp/pool.json --n 60
"""

import argparse
import collections
import csv
import html
import json
import pathlib
import re
import statistics
import sys

EVAL_ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = EVAL_ROOT / "corpus"

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
PARA = re.compile(r"</p>")
STRUCT = re.compile(r"<(?:table|ac:structured-macro|pre|code)\b", re.I)


def paragraphs(lo: int, hi: int, max_per_page: int = 3):
    # Cap per page. Without one, five pages supplied 31 percent of the in-band
    # paragraphs and a single status update supplied 23 of them, so the pool
    # measured a handful of authors rather than the corpus.
    seen = set()
    for path in sorted((CORPUS / "raw").glob("*.json")):
        taken = 0
        try:
            page = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        body = page.get("body", {}).get("storage", {}).get("value", "")
        if not body:
            continue
        for index, raw in enumerate(PARA.split(body)):
            if STRUCT.search(raw):
                continue
            text = WS.sub(" ", html.unescape(TAG.sub(" ", raw))).strip()
            words = len(text.split())
            if not (lo <= words <= hi):
                continue
            if not re.search(r"[.!?]\s|[.!?]$", text):
                continue
            if text in seen:
                continue
            seen.add(text)
            taken += 1
            yield f"{path.stem}-p{index:03d}", words, text
            if taken >= max_per_page:
                break


def write_pool(args) -> int:
    rows = list(paragraphs(args.min_words, args.max_words, args.max_per_page))
    if args.pool_size and len(rows) > args.pool_size:
        step = len(rows) / args.pool_size
        rows = [rows[int(i * step)] for i in range(args.pool_size)]
    out = CORPUS / "launder-pool.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["__description", "words", "passage", "__expected1"])
        for desc, words, text in rows:
            w.writerow([desc, words, text, "icontains:VERDICT rewrite"])
    print(f"wrote {out.relative_to(EVAL_ROOT)}  {len(rows)} prose paragraphs")
    print(f"  from <p> elements only, {args.min_words} to {args.max_words} words")
    print(f"  median {statistics.median(r[1] for r in rows):.0f} words")
    print("\nJudge it, then rerun with --select.")
    return 0


def select(args) -> int:
    rows = (json.loads(pathlib.Path(args.select).read_text())
            .get("results") or {}).get("results") or []
    if not rows:
        print("no results in that file", file=sys.stderr)
        return 1

    tally = collections.defaultdict(lambda: {"n": 0, "rewrite": 0, "text": ""})
    for r in rows:
        v = (r.get("testCase") or {}).get("vars") or {}
        key = str(v.get("passage", ""))
        out = str((r.get("response") or {}).get("output", "")).lower()
        tally[key]["n"] += 1
        tally[key]["text"] = key
        if "verdict rewrite" in out:
            tally[key]["rewrite"] += 1

    # Unanimous picks only. A paragraph the selector was unsure about cannot
    # measure a rewrite, because the baseline arm would be noise.
    generated = [t["text"] for t in tally.values() if t["n"] and t["rewrite"] == t["n"]]
    generated.sort(key=len, reverse=True)
    picked = generated[: args.n]

    out = CORPUS / "launder.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["__description", "words", "passage", "__expected1"])
        for i, text in enumerate(picked):
            w.writerow([f"launder-{i:03d}", len(text.split()), text, "icontains:VERDICT human"])

    judged = len(tally)
    print(f"pool {judged} paragraphs, {len(generated)} judged needing a rewrite every time "
          f"({100*len(generated)/judged:.0f}%)")
    print(f"wrote {out.relative_to(EVAL_ROOT)}  {len(picked)} paragraphs")
    if picked:
        print(f"  median {statistics.median(len(p.split()) for p in picked):.0f} words")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", action="store_true")
    parser.add_argument("--pool-size", type=int, default=200)
    parser.add_argument("--max-per-page", type=int, default=3)
    parser.add_argument("--select", default=None, help="judged pool result json")
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--min-words", type=int, default=60)
    parser.add_argument("--max-words", type=int, default=260)
    args = parser.parse_args()

    if not (CORPUS / "raw").exists():
        print("no corpus, run tools/mine-confluence.sh first", file=sys.stderr)
        return 1
    if args.select:
        return select(args)
    if args.pool:
        return write_pool(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
