"""Check that a quoted evidence entry is the code at the reviewed commit. No model calls.

in_code(entry, repo, commit): the location must be path:line or path:start-end. Every quoted
piece of 6 or more characters must appear somewhere in the file, and every shorter piece, such as
"try {" or "});", must appear between ANCHOR lines before the cited location and ANCHOR lines past
its end plus the quote's own line count. Whitespace is normalized, and a quote may elide with ...
or the ellipsis character. Models paraphrase code, drop type annotations, strip quote characters,
and rewrite punctuation inside quotes, and each of those fails here.
"""
import re
import subprocess

ANCHOR = 3
LOC = re.compile(r"^(?P<path>[^\s:]+):(?P<spans>\d[\d,\- ]*)$")
_files = {}


def lines_at(repo, commit, path):
    key = (repo, commit, path)
    if key not in _files:
        r = subprocess.run(["git", "-C", repo, "show", f"{commit}:{path}"], capture_output=True, text=True)
        _files[key] = r.stdout.split("\n") if r.returncode == 0 else None
    return _files[key]


def _norm(s):
    return " ".join(s.split())


def in_code(entry, repo, commit):
    m = LOC.match(str(entry.get("location", "")).strip())
    if not m:
        return False
    lines = lines_at(repo, commit, m.group("path"))
    if lines is None:
        return False
    whole = _norm("\n".join(lines))
    nums = [int(n) for n in re.findall(r"\d+", m.group("spans"))]
    quoted = len([l for l in str(entry.get("code", "")).split("\n") if l.strip()])
    lo, hi = max(1, min(nums) - ANCHOR), min(len(lines), max(nums) + quoted + ANCHOR)
    window = _norm("\n".join(lines[lo - 1:hi]))
    pieces = [_norm(p) for l in str(entry.get("code", "")).split("\n") for p in re.split(r"\.\.\.|…", l)]
    pieces = [p for p in pieces if p]
    return bool(pieces) and all((p in whole) if len(p) >= 6 else (p in window) for p in pieces)
