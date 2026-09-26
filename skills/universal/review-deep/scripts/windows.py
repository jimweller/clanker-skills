#!/usr/bin/env python3
"""Order every component issue by text similarity and cut the order into overlapping windows.

    uv run --with scikit-learn --with scipy --with numpy python windows.py RUN_DIR [SIZE] [OVERLAP]

Average-linkage clustering on TF-IDF cosine distance puts similar issues next to each other,
whatever component they came from, so one merge window can see a defect reported in two
components. Writes windows.json: for each window, its issue keys and the text block the merge
prompt shows, one issue per line. SIZE defaults to 150 and OVERLAP to 25.
"""
import json
import os
import sys

import numpy as np
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_jsonl, run_dir  # noqa: E402

SNIPPET = 240


def main():
    d = run_dir()
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    overlap = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    findings = {f["id"]: f for f in read_jsonl(f"{d}/findings.jsonl")}
    issues = read_jsonl(f"{d}/issues-by-component.jsonl")
    if len(issues) < 2:
        order = np.arange(len(issues))
    else:
        docs = [i["title"] + " " + i["title"] + " " + " ".join(findings[m]["text"] + " " + findings[m].get("symbol", "") for m in i["members"])
                for i in issues]
        X = TfidfVectorizer(token_pattern=r"[A-Za-z_][A-Za-z0-9_]{2,}", sublinear_tf=True, min_df=min(2, len(issues)), max_df=0.2 if len(issues) > 20 else 1.0,
                            stop_words="english").fit_transform(docs)
        D = np.clip(1.0 - (X @ X.T).toarray(), 0.0, 2.0)
        np.fill_diagonal(D, 0.0)
        order = leaves_list(linkage(squareform(D, checks=False), method="average"))

    def line(i):
        best = max((findings[m] for m in i["members"]), key=lambda f: len(f["text"]))
        text = best["text"] if len(best["text"]) <= SNIPPET else best["text"][:SNIPPET] + "..."
        return f"{i['key']} | {i['severity']} | {len(i['members'])} findings | {i['location']} | {i['title']} -- {text}"

    windows, step, n = {}, size - overlap, len(order)
    for w, s in enumerate(range(0, max(n - overlap, 1), step), 1):
        idx = order[s:s + size]
        windows[f"g-{w:02d}"] = {"keys": [issues[k]["key"] for k in idx], "text": "\n".join(line(issues[k]) for k in idx)}
    json.dump(windows, open(f"{d}/windows.json", "w"), indent=1)
    covered = {k for v in windows.values() for k in v["keys"]}
    print(f"issues {n}, windows {len(windows)}, size {size}, overlap {overlap}, covered {len(covered)}")


if __name__ == "__main__":
    main()
