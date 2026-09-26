#!/usr/bin/env python3
"""Screen ticket candidates against the project's existing issues for duplicates. No model calls.

    uv run --with scikit-learn --with numpy python dupscreen.py RUN_DIR EXISTING_JSON [THRESHOLD]

EXISTING_JSON is an export of the target project's issues from any Jira client: a JSON list, or
an object with an "issues" list, where each issue has "key" and either "summary" and "description"
at the top level or under "fields". The description may be plain text or ADF. Jira search leaves
archived issues out, so an issue archived on purpose never shows up here.

TF-IDF cosine similarity compares each candidate's summary and Context with each existing issue's
summary and description. Pairs at or above THRESHOLD (0.20 by default) are written to
tickets/dup_pairs.json and printed for a human to read. A high score means shared vocabulary,
often only a shared topic; nothing here decides that two tickets are duplicates.
"""
import json
import os
import re
import sys

from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_dir, tickets_dir  # noqa: E402


def adf_text(node):
    if isinstance(node, list):
        return " ".join(adf_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    return (node.get("text", "") + " " + adf_text(node.get("content", []) or [])).strip()


def main():
    d = run_dir()
    if len(sys.argv) < 3:
        sys.exit("usage: dupscreen.py RUN_DIR EXISTING_JSON [THRESHOLD]")
    thresh = float(sys.argv[3]) if len(sys.argv) > 3 else 0.20
    t = tickets_dir(d)
    ours = []
    for m in json.load(open(f"{t}/final/manifest.json")):
        if "summary_source" not in m:
            continue
        tk = json.load(open(f"{t}/final/{m['id']}.json"))
        context = tk["description"].split("h3. Details")[0]
        ours.append((tk["id"], tk["summary"], tk["summary"] + " " + re.sub(r"[{}\\]", " ", context)))
    existing = json.load(open(sys.argv[2]))
    rows = existing if isinstance(existing, list) else existing.get("issues", [])
    theirs = []
    for r in rows:
        f = r.get("fields") or r
        desc = f.get("description")
        text = adf_text(desc) if isinstance(desc, (dict, list)) else (desc or "")
        theirs.append((r["key"], f.get("summary") or "", (f.get("summary") or "") + " " + text))
    X = TfidfVectorizer(token_pattern=r"[A-Za-z_][A-Za-z0-9_]{2,}", sublinear_tf=True, max_df=0.5,
                        stop_words="english").fit_transform([o[2] for o in ours] + [x[2] for x in theirs])
    S = (X[:len(ours)] @ X[len(ours):].T).toarray()
    pairs = sorted(((float(S[i, j]), ours[i][0], ours[i][1], theirs[j][0], theirs[j][1])
                    for i in range(len(ours)) for j in range(len(theirs)) if S[i, j] >= thresh), reverse=True)
    json.dump(pairs, open(f"{t}/dup_pairs.json", "w"), indent=1)
    print(f"candidates {len(ours)}, existing {len(theirs)}, pairs at or above {thresh}: {len(pairs)}")
    for score, oid, osum, key, tsum in pairs:
        print(f"  {score:.2f}  {oid:10s} {osum[:70]:70s} <-> {key} {tsum[:60]}")


if __name__ == "__main__":
    main()
