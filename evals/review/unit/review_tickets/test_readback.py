"""Comparing a posted ticket, read back as ADF, against the ticket file."""
from readback import compare, expected

DESC = "\n".join([
    "{panel:bgColor=#deebff}", "h3. Context",
    '* {{src/a.ts:3}} {{run}} Parses {{"a\\"b"}} and {{\\{ x \\}}} and {{0.0.0.0}} – {{0.0.0.0}}.',
    "{panel}", "", "h3. Details", "Commit.", "", "{code:javascript}", "// src/a.ts:1-2", "one()", "two()", "{code}",
])
TICKET = {"summary": "S", "type": "Bug", "priority": "High", "labels": ["review-deep", "security"], "description": DESC}


def adf(code_texts, blocks, texts=("Parses ",)):
    content = [{"type": "text", "text": t, "marks": [{"type": "code"}]} for t in code_texts]
    content += [{"type": "text", "text": t} for t in texts]
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": content}]}
    doc["content"] += [{"type": "codeBlock", "content": [{"type": "text", "text": b}]} for b in blocks]
    return doc


def fields(doc, **over):
    f = {"summary": "S", "issuetype": {"name": "Bug"}, "priority": {"name": "High"},
         "labels": ["security", "review-deep"], "description": doc}
    f.update(over)
    return f


def test_expected_unescapes_only_wiki_specials():
    spans, blocks = expected(DESC)
    assert '"a\\"b"' in spans          # Jira keeps a backslash before a quote
    assert "{ x }" in spans            # and consumes it before a brace
    assert len(blocks) == 1


def test_matching_ticket_passes():
    doc = adf(["src/a.ts:3", "run", '"a\\"b"', "{ x }", "0.0.0.0", "0.0.0.0"], ["// src/a.ts:1-2\none()\ntwo()"])
    assert compare(TICKET, fields(doc)) == []


def test_merged_span_is_caught():
    doc = adf(["src/a.ts:3", "run", '"a\\"b"', "{ x }", "0.0.0.0}}–{{0.0.0.0"], ["// src/a.ts:1-2\none()\ntwo()"])
    assert any("code span missing" in p for p in compare(TICKET, fields(doc)))


def test_field_mismatches_are_caught():
    doc = adf(["src/a.ts:3", "run", '"a\\"b"', "{ x }", "0.0.0.0", "0.0.0.0"], ["// src/a.ts:1-2\none()\ntwo()"])
    problems = compare(TICKET, fields(doc, priority={"name": "Medium"}, labels=["review-deep"]))
    assert any(p.startswith("priority") for p in problems) and any(p.startswith("labels") for p in problems)


def test_unrendered_markup_is_caught():
    doc = adf(["src/a.ts:3", "run", '"a\\"b"', "{ x }", "0.0.0.0", "0.0.0.0"], ["// src/a.ts:1-2\none()\ntwo()"],
              texts=("{{broken}} text",))
    assert "unrendered wiki markup in text" in compare(TICKET, fields(doc))
