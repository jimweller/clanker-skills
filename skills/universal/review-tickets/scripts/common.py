"""Shared paths and helpers for the review-tickets scripts.

Every script takes the run directory as its first argument. The run directory holds run.json,
written by review-deep, which names the repository, the reviewed commit, the judge checkout, the
models, and the concurrency. The ticket stages write under <run>/tickets/.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(os.path.dirname(HERE), "prompts")
RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
NON_BUG_AREAS = {"testing", "test", "documentation", "quality", "maintainability", "architecture", "solid"}
CATEGORY = {"bug": "correctness", "maintainability": "quality", "test": "testing", "documentation": "quality"}

DEFAULT_MODELS = {
    "judge": ["opus", "xhigh"],
    "critical": ["fable", "high"],
    "sibling": ["opus", "xhigh"],
}


def run_dir(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) < 2:
        sys.exit(f"usage: {os.path.basename(argv[0])} RUN_DIR [...]")
    d = os.path.abspath(os.path.expanduser(argv[1]))
    if not os.path.exists(f"{d}/run.json"):
        sys.exit(f"{d}/run.json not found; run review-deep first")
    return d


def load_run(d):
    run = json.load(open(f"{d}/run.json"))
    run.setdefault("models", {})
    for k, v in DEFAULT_MODELS.items():
        run["models"].setdefault(k, v)
    run.setdefault("concurrency", 50)
    run.setdefault("checkout", f"{d}/checkout")
    return run


def tickets_dir(d):
    t = f"{d}/tickets"
    os.makedirs(t, exist_ok=True)
    return t


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def load_json(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def lower(*severities):
    """The lower of the given ratings, ignoring empty ones."""
    return max((s for s in severities if s), key=RANK.get)


def prompt(name, **values):
    from string import Template
    return Template(open(os.path.join(PROMPTS, name), encoding="utf-8").read()).substitute(values)
