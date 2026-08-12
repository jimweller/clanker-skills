---
name: relay
description: Print a paste-ready prompt that makes a fresh session execute the current plan
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📡

# Relay: Hand the Current Plan to a Fresh Session

Print one line, in a code block so it is easy to copy:

    Read ~/.claude/plans/<slug>.md and execute it.

The plan's path is already in context. Do not go looking for it. Print only.
Write nothing. Add nothing else.
