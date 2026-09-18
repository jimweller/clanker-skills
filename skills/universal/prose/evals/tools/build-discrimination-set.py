#!/usr/bin/env python3
"""Builds a balanced human-versus-generated classification set from the corpus.

Labels come from page creation date, which is the only ground truth available.
Chunks under corpus/chunks/raw came from pages created 2025-09 onward and dense
in em-dashes. Chunks under corpus/chunks/raw-human came from pages created
before 2023-06, which predates org-wide model use.

Two arms get written. The marked arm leaves punctuation alone, so a model can
answer by counting em-dashes. The stripped arm normalises em-dashes, semicolons
and colons out of both classes, so only rhythm, subject census, abstraction and
foil use remain. The stripped arm is the one that measures style recognition.

Output lands in corpus/, which is gitignored, because the chunks are real
internal prose.

Usage
    tools/build-discrimination-set.py [--n 40] [--min-words 90] [--max-words 320]
"""

import argparse
import csv
import pathlib
import random
import re
import statistics
import sys

EVAL_ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = EVAL_ROOT / "corpus"

# Marks the mechanical graders already cover. Removing them from both classes
# forces the classifier onto style.
EM = re.compile(r"\s*(?:—|–|(?<![\w-])--(?![\w-]))\s*")
SEMI = re.compile(r"\s*;\s*")
COLON = re.compile(r"(?<=[A-Za-z)\"])\s*:\s+")


def strip_marks(text: str) -> str:
    text = EM.sub(", ", text)
    text = SEMI.sub(". ", text)
    text = COLON.sub(". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # A substitution that leaves a lowercase word after a full stop is itself a
    # tell, and it lands more often on the class that used more semicolons, so
    # the artefact would correlate with the label. Repair the sentence starts.
    return re.sub(r"(?<=[.!?] )([a-z])", lambda m: m.group(1).upper(), text)


def load(source: str, lo: int, hi: int):
    out = []
    for path in sorted((CORPUS / "chunks" / source).glob("*.txt")):
        text = re.sub(r"\s+", " ", path.read_text()).strip()
        words = len(text.split())
        if lo <= words <= hi:
            out.append((path.stem, words, text))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40, help="chunks per class")
    parser.add_argument("--min-words", type=int, default=90)
    parser.add_argument("--max-words", type=int, default=320)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    gen = load("raw", args.min_words, args.max_words)
    hum = load("raw-human", args.min_words, args.max_words)
    if not gen or not hum:
        print("need both corpora chunked first, see tools/chunk-corpus.py", file=sys.stderr)
        return 1

    random.seed(args.seed)
    n = min(args.n, len(gen), len(hum))
    gen = random.sample(gen, n)
    hum = random.sample(hum, n)

    rows = []
    for label, items in (("generated", gen), ("human", hum)):
        for stem, words, text in items:
            rows.append({"stem": stem, "label": label, "words": words, "text": text})
    random.shuffle(rows)

    for arm, transform in (("marked", lambda t: t), ("stripped", strip_marks)):
        out = CORPUS / f"discriminate-{arm}.csv"
        with out.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["__description", "arm", "label", "words", "changed", "passage", "__expected1"])
            changed = 0
            for i, r in enumerate(rows):
                text = transform(r["text"])
                # A passage carrying none of the three marks comes through the
                # strip unchanged, so the two arms hand the model identical
                # input. Recording that lets the analysis drop those rows from
                # the marked-versus-stripped comparison instead of double
                # counting them.
                same = text == r["text"]
                changed += 0 if same else 1
                w.writerow([
                    f"disc-{arm}-{i:03d}",
                    arm,
                    r["label"],
                    r["words"],
                    "no" if same else "yes",
                    text,
                    f"icontains:{r['label']}",
                ])
        print(f"wrote {out.relative_to(EVAL_ROOT)}  {len(rows)} rows, "
              f"{changed} altered by the strip")

    gw = [r["words"] for r in rows if r["label"] == "generated"]
    hw = [r["words"] for r in rows if r["label"] == "human"]
    print(f"\n{n} per class, word counts {args.min_words} to {args.max_words}")
    print(f"  generated  median {statistics.median(gw):.0f}  mean {statistics.mean(gw):.0f}")
    print(f"  human      median {statistics.median(hw):.0f}  mean {statistics.mean(hw):.0f}")
    print("\nLength is matched by the sampling band above. Topic is not, because the")
    print("two date ranges cover different work, so read a high score as style plus")
    print("topic era rather than style alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
