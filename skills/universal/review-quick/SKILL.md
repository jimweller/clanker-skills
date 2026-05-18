---
name: review-quick
description: "Use to review uncommitted changes and recent commits in the working tree. Dispatches 8 specialized review agents in parallel and returns a consolidated report"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = ⚡

# Quick Review

Review work-in-progress and recent commits across 8 focus areas in parallel. No arguments. Auto-detects deltas.

## Step 1: Detect Deltas

Compute what changed since the project root was last touched. Span committed, staged, unstaged, and untracked work.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
BASELINE=$(git log -1 --format=%H -- "$PROJECT_ROOT")
[ -z "$BASELINE" ] && BASELINE=$(git rev-list --max-parents=0 HEAD)

git log --oneline ${BASELINE}..HEAD
git diff ${BASELINE} --find-renames --stat
git diff ${BASELINE} --find-renames
git status --porcelain
git ls-files --others --exclude-standard
```

The diff has no `..HEAD` so it spans the baseline through the working tree, including staged and unstaged edits. `--find-renames` surfaces renames as `R<score>` entries with both old and new paths so a pure rename does not collapse into an empty diff. `git status --porcelain` is the authoritative list of every modified, added, deleted, renamed, copied, and untracked entry; use it to confirm rename detection. `ls-files --others` surfaces new untracked files. Files matching `.gitignore` are excluded.

Stop only if all four signals are empty: `git diff` empty, `git status --porcelain` empty, `ls-files --others` empty, and `git log ${BASELINE}..HEAD` empty. Then report "No deltas to review" and stop.

## Step 2: Read Untracked Files

For each file from `git ls-files --others --exclude-standard`, read the full file content. Untracked files have no diff representation.

## Step 3: Dispatch 8 Review Agents in Parallel

Dispatch 8 parallel reviews, one per focus area. Use subagents if available, otherwise run sequentially:

| Agent                 | Subagent type         |
| --------------------- | --------------------- |
| Architecture & Design | `review-architecture` |
| Correctness & Bugs    | `review-correctness`  |
| Operational Readiness | `review-ops`          |
| Performance           | `review-performance`  |
| Code Quality          | `review-quality`      |
| Security              | `review-security`     |
| SOLID Principles      | `review-solid`        |
| Testing               | `review-testing`      |

Each review prompt contains:

1. The full diff output from Step 1
2. The contents of any untracked files from Step 2
3. The instruction: "Review the following changes for your focus area. Return findings as your response."

Do not pack repomix. Each agent has all the context needed in the prompt.

## Step 4: Consolidate Findings

After all 8 agents return, produce a single consolidated report:

```markdown
# Quick Review Report

## Summary

- Total findings: <N>
- High: <count>
- Medium: <count>
- Low: <count>

## Findings by Severity

### High

[All High findings from all 8 agents, ordered by file:line]

### Medium

[All Medium findings from all 8 agents, ordered by file:line]

### Low

[All Low findings from all 8 agents, ordered by file:line]
```

## When to Use

This skill auto-loads when:

- A bug fix or feature implementation has just been completed
- Work is about to be committed or a PR is about to be opened
- A subagent-driven-development task has just passed spec compliance review

It is also slash-invokable for ad-hoc review of current work.
