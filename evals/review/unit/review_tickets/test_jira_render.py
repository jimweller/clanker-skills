"""The read-back rules against what Jira actually stored for synthetic wiki samples (DEVX-4503)."""
import json
import os

from readback import expected, nodes
from wiki import to_wiki

DATA = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "jira_render", "devx4503.json")))


def items(round_):
    bullets = [l[2:] for l in round_["wiki"].split("\n") if l.startswith("* ")]
    lis = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "listItem":
                lis.append(n)
                return
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(round_["adf"])
    assert len(bullets) == len(lis)
    return list(zip(bullets, lis))


def test_expected_spans_match_what_jira_stored_whenever_jira_rendered_monospace():
    checked = 0
    for r in DATA["rounds"]:
        for wiki, li in items(r):
            got = nodes(li, {"code": [], "text": [], "blocks": []})
            # A span ending in a backslash reads as an escaped closer to expected(); checks.py flags it instead.
            if got["code"] and not any("&#" in c for c in got["code"]) and "\\}}" not in wiki:
                assert expected(wiki)[0] == got["code"], wiki
                checked += 1
    assert checked == 7


def test_every_encoding_of_a_lone_backslash_failed_and_the_assembler_avoids_them():
    broken = [w for r in DATA["rounds"] for w, li in items(r)
              if not nodes(li, {"code": [], "text": [], "blocks": []})["code"] or "&#92;" in json.dumps(li) or "\\\\\\\\" in json.dumps(li)]
    assert any("{{\\}}" in w for w in broken)
    assert to_wiki("Escape `\\` first") == "Escape backslash first"
