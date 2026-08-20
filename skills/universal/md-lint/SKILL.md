---
name: md-lint
description: What the markdown formatter rewrites and which lint rules it cannot fix. Use before writing markdown intended for a human reader, so the file comes out conforming instead of being reformatted afterward.
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔏

# Markdown Formatter Contract

A PostToolUse hook runs `markdownlint-cli2 --fix` and then `prettier --write` on every markdown file written or edited, excluding `.llmtmp/`, `.llmdocs/`, `SKILL.md`, and plan files. Writing to this contract avoids a rewrite, and a rewrite invalidates the in-context copy of the file.

## What prettier rewrites

| Input | Output |
| --- | --- |
| `* item`, `+ item` | `- item` |
| `1)` ordered marker | `1.` |
| `*emphasis*` | `_emphasis_` |
| `__strong__` | `**strong**` |
| `***` thematic break | `---` |
| Two or more blank lines | One blank line |
| Runs of spaces inside a line | Single space |
| Unpadded table cells | Cells padded to column width |
| No trailing newline | Trailing newline added |

Prose is not rewrapped. Long lines stay as written.

## What markdownlint fixes

Missing space after `#`, missing blank lines around headings and fenced blocks, trailing whitespace, and bare URLs.

Four rules are off: MD013 (line length), MD024 (duplicate headings), MD029 (ordered list prefix), MD033 (inline HTML).

## What neither can fix

These reach the model as hook feedback and need a manual edit:

- MD003, heading style. Setext headings underlined with `===` or `---` are errors. Use ATX (`#`, `##`).
- MD025, one H1 per document.
- MD045, images need alt text.
- MD042, links need a destination.
- MD040, fenced code blocks need a language.

## Writing conforming markdown

Start with a single `# Title`. Use ATX headings, `-` bullets, `_emphasis_`, `**strong**`, one blank line between blocks, a language on every fence, alt text on every image, and a trailing newline.
