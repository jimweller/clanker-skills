---
name: verify-claims
description: "Use when about to claim work is complete or passing, when receiving subagent results, or when writing a regression test for a bug fix"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🧾

# Verify Claims

Three procedures for proving claims with evidence. Each procedure runs before the claim is made, not after.

## Verification Commands by Claim Type

Map the claim to the command that proves it. Run the command in this turn. Use the actual output, not memory of prior runs.

| Claim                 | Command                                        | Insufficient                   |
| --------------------- | ---------------------------------------------- | ------------------------------ |
| Tests pass            | Project test command, full suite or named test | Prior run, "should pass"       |
| Linter clean          | Project linter command                         | Partial check, extrapolation   |
| Build succeeds        | Project build command, exit 0                  | Linter passing, logs look fine |
| Bug fixed             | Test that reproduces the original symptom      | Code changed, "looks fixed"    |
| Regression test works | Red-green-revert-restore (see below)           | Test passes once               |
| Subagent completed    | VCS diff plus targeted re-check                | Subagent self-report           |
| Requirements met      | Re-read spec, line-by-line checklist           | Tests passing                  |

## Subagent Result Verification

Subagents report success in their final message. The report is not evidence. The diff is.

When a subagent returns:

1. Read the subagent summary
2. Run `git status` and `git diff` to see what actually changed
3. If the subagent claimed tests pass, run the test command in the current turn
4. If the subagent claimed a bug is fixed, run the reproduction case in the current turn
5. Only then accept the result and move on

Subagents fabricate success reports under pressure. Treat the report as a hypothesis to verify, not a fact to accept.

## Red-Green-Revert-Restore for Regression Tests

A test written after the fix passes immediately. Passing immediately proves nothing. To prove the test catches the bug:

1. Write the regression test
2. Run it with the fix in place. Expect: pass.
3. Revert the fix only.
4. Run the test. Must fail.
5. Restore the fix.
6. Run the test. Expect: pass.

If step 4 passes, the test does not exercise the bug. Throw it out and write a new one.

This procedure is unnecessary when test-driven-development order is followed (test first, then fix). It is the recovery procedure for the inverted order.
