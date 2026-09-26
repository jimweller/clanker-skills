"""Jira wiki conversion rules, each one found by reading tickets back from Jira."""
from wiki import to_wiki


def test_plain_code_span():
    assert to_wiki("calls `fetchUserList` twice") == "calls {{fetchUserList}} twice"


def test_code_span_escapes_wiki_specials():
    assert to_wiki("returns `{ ...task }`") == "returns {{\\{ ...task \\}}}"
    assert to_wiki("uses `a|b` and `a*b`") == "uses {{a\\|b}} and {{a\\*b}}"


def test_prose_escapes_braces_brackets_pipes_stars():
    assert to_wiki("a {brace} and [1] and a|b") == "a \\{brace\\} and \\[1\\] and a\\|b"


def test_bold_survives():
    assert to_wiki("**Note** this") == "*Note* this"


def test_lone_backslash_span_becomes_a_word():
    # Jira reads {{\}} as an escaped closing brace and drops the monospace.
    assert to_wiki("Escape `\\` and `\"` first") == 'Escape backslash and {{"}} first'


def test_backslash_inside_a_span_is_kept():
    assert to_wiki('a string such as `"a\\"b"` here') == 'a string such as {{"a\\"b"}} here'


def test_double_backtick_span_holds_a_backtick():
    assert to_wiki("contains `` $` `` or `$$`") == "contains {{$`}} or {{$$}}"


def test_unmatched_backtick_run_stays_literal():
    # A ```json with no closing triple run must not pair with a later single backtick.
    out = to_wiki("not a ```json block), caller `collect` (and more")
    assert out == "not a ```json block), caller {{collect}} (and more"


def test_span_next_to_unsafe_character_gets_a_space():
    # Jira kept {{0.0.0.0}}–{{0.0.0.0}} as one span reading 0.0.0.0}}–{{0.0.0.0.
    assert to_wiki("the `0.0.0.0`–`0.0.0.0` rule") == "the {{0.0.0.0}} – {{0.0.0.0}} rule"
    assert to_wiki("`onRename`→`patchItem`") == "{{onRename}} → {{patchItem}}"
    assert to_wiki("see `x`: then") == "see {{x}} : then"


def test_span_next_to_safe_character_is_left_alone():
    assert to_wiki("(`a`), `b`. `c`/`d`'s `e`-f `g`;") == "({{a}}), {{b}}. {{c}}/{{d}}'s {{e}}-f {{g}};"
