---
name: review-diff
description: "Review every change on this branch against main across 8 perspectives in parallel. Covers committed, staged, unstaged, and untracked work. Returns one consolidated report."
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = ⚡

# Diff Review

Review everything that differs from `main` across 8 perspectives in parallel. No arguments.

## Step 1: Resolve the Base

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)

BASE_REF=$(git rev-parse --verify --quiet origin/main || git rev-parse --verify --quiet main)
if [ -z "$BASE_REF" ]; then
  echo "No main branch found (tried origin/main and main)"
  exit 1
fi

BASE=$(git merge-base HEAD "$BASE_REF")

# On main itself the merge base is HEAD, which would hide committed work.
# Fall back to the previous commit so the branch tip is still under review.
if [ "$BASE" = "$(git rev-parse HEAD)" ]; then
  BASE=$(git rev-parse --verify --quiet HEAD~1 || echo "$BASE")
fi

echo "BASE=$BASE"
```

## Step 2: Collect the Delta

```bash
git log --oneline "${BASE}"..HEAD
git diff "${BASE}" --find-renames --stat
git diff "${BASE}" --find-renames
git status --porcelain
git ls-files --others --exclude-standard
```

`git diff "$BASE"` carries no `..HEAD`, so it spans the merge base through the working tree. Committed, staged, and unstaged changes all land in one diff. `--find-renames` surfaces renames as `R<score>` entries with both paths so a pure rename does not collapse into an empty diff. `git status --porcelain` is the authoritative list of every modified, added, deleted, renamed, copied, and untracked entry. `ls-files --others` surfaces untracked files, which have no diff representation. Files matching `.gitignore` are excluded.

Stop when all four signals are empty. Report `No changes against main` and stop.

## Step 3: Read Untracked Files

Read the full content of every file from `git ls-files --others --exclude-standard`.

## Step 4: Dispatch 8 Reviewers in Parallel

Issue all 8 Agent calls **in a single tool block** with `run_in_background: false`.

Subagents default to running in the background. A backgrounded fan-out delivers its results in later turns, so Step 5 would find nothing to consolidate. Synchronous dispatch in one block is what makes the fleet parallel and the report possible in this turn.

| Perspective           | Agent                   |
| --------------------- | ----------------------- |
| Architecture & Design | `reviewer-architecture` |
| Correctness & Bugs    | `reviewer-correctness`  |
| Operational Readiness | `reviewer-ops`          |
| Performance           | `reviewer-performance`  |
| Code Quality          | `reviewer-quality`      |
| Security              | `reviewer-security`     |
| SOLID Principles      | `reviewer-solid`        |
| Testing               | `reviewer-testing`      |

Dispatch all 8 every run. Do not skip a perspective based on which files changed.

Each prompt carries the full diff from Step 2, the untracked file contents from Step 3, and this brief:

```text
Audit the changes below through your perspective.

Report defects, flaws, risks, and recommendations only. Do not describe
what works. Do not praise. Do not modify files.

Rate each finding High, Medium, or Low. Cite file, line, and symbol.
A finding without a citation is not a finding.

Emit an H2 header naming your perspective, followed by your findings.
If you find nothing, or the change does not reach your domain, emit
exactly that H2 followed by "No findings." and stop.

Return your findings as your response message.
```

Do not pack repomix. Every agent has all the context it needs in the prompt.

## Step 5: Consolidate

Merge the 8 responses into one report. Where two perspectives report the same defect at the same location, keep the one whose domain owns it and drop the other.

```markdown
# Diff Review Report

Base: <BASE short sha> (merge-base with main)

## Summary

- Total findings: <N>
- High: <count>
- Medium: <count>
- Low: <count>

## Findings by Severity

### High

[All High findings, ordered by file:line]

### Medium

[All Medium findings, ordered by file:line]

### Low

[All Low findings, ordered by file:line]
```
