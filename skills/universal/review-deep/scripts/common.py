"""Shared paths and helpers for the review-deep Step 5 scripts.

Every script takes the run directory as its first argument. init_run.py creates it outside the
reviewed repository and writes run.json, which the later stages and the review-tickets skill read.
pool.py and evidence.py are kept identical to the copies in review-tickets/scripts.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(os.path.dirname(HERE), "prompts")
RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

DEFAULT_MODELS = {
    "collate": ["opus", "high"],
    "merge": ["opus", "high"],
    "verify": ["opus", "high"],
    "second": ["fable", "high"],
    "judge": ["opus", "xhigh"],
    "critical": ["fable", "high"],
    "sibling": ["opus", "xhigh"],
}
JUDGE_EXCLUDE = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".claude", ".cursor", ".cursorrules", ".windsurfrules",
                 ".github/copilot-instructions.md", ".mcp.json", ".serena", ".llmtmp"]


def run_dir(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) < 2:
        sys.exit(f"usage: {os.path.basename(argv[0])} RUN_DIR [...]")
    d = os.path.abspath(os.path.expanduser(argv[1]))
    if not os.path.exists(f"{d}/run.json"):
        sys.exit(f"{d}/run.json not found; run init_run.py first")
    return d


def load_run(d):
    run = json.load(open(f"{d}/run.json"))
    run.setdefault("models", {})
    for k, v in DEFAULT_MODELS.items():
        run["models"].setdefault(k, v)
    run.setdefault("concurrency", 50)
    run.setdefault("checkout", f"{d}/checkout")
    return run


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def lower(*severities):
    return max((s for s in severities if s), key=RANK.get)


def prompt(name, **values):
    from string import Template
    return Template(open(os.path.join(PROMPTS, name), encoding="utf-8").read()).substitute(values)
