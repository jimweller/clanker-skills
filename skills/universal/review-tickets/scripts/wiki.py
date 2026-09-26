"""Markdown finding text to Jira wiki markup.

Rules found by posting tickets and reading them back as ADF:
- A code span is written {{...}} with { } [ ] * | ! escaped inside it. Jira drops the escaping
  backslash before those characters and keeps a backslash before anything else, such as a quote.
- A span holding only a backslash is written as the word "backslash". Jira reads {{\\}} as an
  escaped closing brace, and no encoding survives: {{\\\\}} shows two backslashes and &#92; is
  left undecoded.
- Jira closes {{...}} only next to certain characters. Two spans joined by an en dash became one
  span reading 0.0.0.0}}–{{0.0.0.0. A space separates a span from any neighbor outside the sets
  confirmed to render: space , / . ' - ; ) and newline after, space / ( and newline before.
- A backtick run pairs only with a run of the same length, and a run with no partner stays
  literal, so a mention of ```json never pairs with a later single backtick.
"""
import re

CODE_SPECIAL = re.compile(r"([{}\[\]*|!])")
PROSE_SPECIAL = re.compile(r"([{}\[\]|*])")
SAFE_AFTER = set(" ,/.'-;)\n")
SAFE_BEFORE = set(" /(\n")
SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


def prose(t):
    bold = []

    def keep(m):
        bold.append(m.group(1))
        return f"\x00{len(bold) - 1}\x00"

    t = PROSE_SPECIAL.sub(r"\\\1", re.sub(r"\*\*(.+?)\*\*", keep, t))
    return re.sub(r"\x00(\d+)\x00", lambda m: "*" + PROSE_SPECIAL.sub(r"\\\1", bold[int(m.group(1))]) + "*", t)


def code(t):
    return "{{" + CODE_SPECIAL.sub(r"\\\1", t) + "}}"


def to_wiki(text):
    out, pos = [], 0
    for m in SPAN.finditer(text):
        out.append(prose(text[pos:m.start()]))
        body = m.group(2).strip()
        if body == "\\":
            out.append("backslash")
        elif body:
            before = text[m.start() - 1] if m.start() else " "
            after = text[m.end()] if m.end() < len(text) else " "
            out.append(("" if before in SAFE_BEFORE else " ") + code(body) + ("" if after in SAFE_AFTER else " "))
        pos = m.end()
    out.append(prose(text[pos:]))
    return "".join(out)
