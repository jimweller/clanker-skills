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

Every fact in the result comes from the source. Invent no number, no name, no date. A number you computed from the source is still invented, so "24 of 64 weeks" never becomes "more than a third".

Re-read every sentence you restructured, because a move 3 fix routinely leaves a move 4 target standing. Watch for one failure above all others. A dash holding a contrast turns into "rather than", "instead of", or "but", and every one of those is a phantom-foil marker, so the sentence still carries the foil and now hides it better. When a dash holds a contrast, stop and ask whether the rejected option appears anywhere else in the document. Delete the foil when it does not. Renaming it is never the answer.

Removing a dash means naming the relation it hid. Use "so", "because", "and", or move the phrase to where it belongs. A bare full stop is the last resort, not the default, because it drops the logic the dash was carrying. Before using one, say out loud what the dash meant. "Velocity measured human effort under uncertainty, so it is noise now" keeps the argument; two flat sentences leave the reader to rebuild it.

An intensifier goes only when it changes nothing. "Quietly re-anchors" claims the harm is invisible, which is the point of the sentence, so it stays.

Read the edited text once more for mechanical damage: a space stranded where punctuation was removed, doubled commas, a sentence that now starts lowercase.

When done, report the count of edits and nothing else.

## Out of scope

This is not an evidence audit. A missing citation, an unlinked reference, an unsourced claim, or a number the author never gathered is not a prose defect. Leave it alone.

The one exception is a rewrite that would otherwise need a fact the source lacks. Mark that inline as `[GAP: what is missing]` and move on. A quantifier no reader would query is not a gap.

## Judgment

A hit is a question about a sentence, not a verdict. Every bullet carries an exemption and the exemptions are where the judgment is.

Applied as a checklist this catalog lengthens tight prose. Check that each rewrite is shorter than its source. Revert the ones that are not.
