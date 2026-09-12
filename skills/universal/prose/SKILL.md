---
name: prose
description: Edit writing against the house prose contract. Use when asked to edit, fix, tighten, or review prose, a draft, a page, a commit message, a PR body, or any writing meant for a human reader.
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🖋️

# Prose

Edit the target. This skill rewrites text; it does not produce a report unless the user asks for one.

The contract is three sections of the global instructions: `How to Write`, `Banned Patterns in All Writing`, and `Ghostwriting for Other Humans`. They are already loaded. Do not restate them. `Chat Register` is not in scope, because it governs the assistant turn rather than an artifact.

## Process

Edit prose only. Headings, table cells, list items, code, and quoted speech are exempt.

Apply move 2, then 3, then 4. Fix the sentences first. Typography last, and only where it misleads.

Every fact in the result comes from the source. Invent no number, no name, no date.

When done, report the count of edits and nothing else.

## Out of scope

This is not an evidence audit. A missing citation, an unlinked reference, an unsourced claim, or a number the author never gathered is not a prose defect. Leave it alone.

The one exception is a rewrite that would otherwise need a fact the source lacks. Mark that inline as `[GAP: what is missing]` and move on. A quantifier no reader would query is not a gap.

## Judgment

A hit is a question about a sentence, not a verdict. Every bullet carries an exemption and the exemptions are where the judgment is.

Applied as a checklist this catalog lengthens tight prose. Check that each rewrite is shorter than its source. Revert the ones that are not.
