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

## Step 3: Materialize the Input

Write the whole change set to one file. Reviewers hold `Read` but no `Bash`, so they cannot run git themselves. Passing the diff through eight prompts costs eight copies of it in orchestrator output; writing it once and having each reviewer read it costs one.

```bash
OUTPUT_DIR="$PROJECT_ROOT/.llmtmp/review-diff"
mkdir -p "$OUTPUT_DIR"
find "$OUTPUT_DIR" -mindepth 1 -delete
INPUT="$OUTPUT_DIR/input.md"

{
  echo "# Change set vs merge-base ${BASE}"
  echo; echo "## Commits"; git log --oneline "${BASE}"..HEAD
  echo; echo "## Status"; git status --porcelain
  echo; echo "## Diffstat"; git diff "${BASE}" --find-renames --stat
  echo; echo "## Diff"; git diff "${BASE}" --find-renames
} > "$INPUT"

for f in $(git ls-files --others --exclude-standard); do
  { echo; echo "## Untracked file: $f"; cat -n "$f"; } >> "$INPUT"
done

wc -c "$INPUT"
```

Untracked files carry no diff representation, so their full contents are appended with line numbers.

`mkdir -p` then `find -delete` rather than `rm -rf`. A `safe-rm` shim on `PATH` (as in some dotfiles setups) moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

## Step 3.5: Pre-flight Scan

A sensitive-data hook that guards `Read` will block a reviewer mid-run, and a reviewer holds no `AskUserQuestion` tool, so it cannot ask for a bypass. Scan the input before the fan-out so the operator learns about it from one cheap step rather than from a partial report.

```bash
SCAN="$HOME/.config/dotfiles/scripts/canary-scan.sh"
if [ -x "$SCAN" ]; then
  "$SCAN" "$INPUT" || true
fi
```

`canary-scan.sh` exits 0 with no output when the input is clean or the hook is not installed, and exits 2 printing one `<ruleId> x<count>` line per rule when it hits. The `|| true` keeps a non-zero exit from ending the step; the output is the signal, not the status.

On a hit, tell the operator what fired and continue to Step 4 anyway. State that the reviewers may be blocked on their read, and that re-invoking with `[allow-pii]` on their own prompt clears it. An allow tag on the operator's prompt propagates to the subagents spawned in that turn; the tag does not need to appear in the dispatch prompt.

Blocking is per-read and can be partial. Some reviewers get through while others do not, so Step 5 still has to check every response.

## Step 4: Dispatch 8 Reviewers in Parallel

Issue all 8 Agent calls **in a single tool block** with `run_in_background: false`.

Subagents default to running in the background. A backgrounded fan-out delivers its results in later turns, so Step 6 would find nothing to consolidate. Synchronous dispatch in one block is what makes the fleet parallel and the report possible in this turn.

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

Every prompt is identical apart from nothing. Send this, with `<INPUT>` and `<PROJECT_ROOT>` substituted:

```text
Read <INPUT>. It holds the commit log, porcelain status, diffstat, full diff
against the merge-base with main, and the full contents of every untracked
file. That is the complete change set under review.

The project root is <PROJECT_ROOT>. Every path in the diff is relative to it.
Open any file you need in that tree to confirm a finding and to confirm the
line number you cite.

Audit this change set. Apply the Ownership table in your instructions: report
only defect classes you own, and stay silent on the rest.

Return your findings as your response message.
```

The brief stays short on purpose. Severity, citation format, output shape, and lane discipline all live in the agent definitions, so one edit there changes every caller.

Do not pack repomix. The input file holds everything.

## Step 5: Verify Every Response

Check each of the 8 responses before consolidating. A response is valid only when its first non-blank line is the H2 naming that area, and its body holds either at least one finding line or exactly `No findings.`

Re-dispatch any agent whose response fails that check. Three failure modes produce a response that is not findings:

- The agent died on a transient API error and returned nothing.
- A sensitive-data filter blocked its read of the input file and it returned a refusal. An ordinary bind address such as `0.0.0.0` in the diff is enough to trip one. Re-dispatch with the operator's PII bypass token when the refusal names one.
- The agent narrated a partial read before the H2, meaning it reviewed less than the full change set.

Never record any of these as `No findings.` An area that cannot be covered after a re-dispatch is reported as `Not reviewed` in the summary, naming the reason.

Editing an agent definition does not affect a session already running. Claude Code detects agent files being added or removed, but a session keeps the body it loaded at startup, and a definition reached through a symlink (as dotbot installs them) is not re-read on edit. Restart the session after changing a reviewer.

## Step 6: Consolidate

Merge the 8 responses into one report. Every finding arrives as a single line already carrying severity, citation, and symbol, so merging is a sort rather than a rewrite. Preserve each line as written.

Where two perspectives report the same defect at the same location, keep the one whose domain owns it and drop the other. Count the collisions and report the number. A collision count above 2 means the Ownership table in the agent definitions needs a row for that defect class.

```markdown
# Diff Review Report

Base: <BASE short sha> (merge-base with main)

## Summary

- Total findings: <N>
- High: <count>
- Medium: <count>
- Low: <count>
- Cross-lane collisions dropped: <count>
- Areas not reviewed: <none, or area and reason>

## Findings by Severity

### High

[All High findings, ordered by file:line]

### Medium

[All Medium findings, ordered by file:line]

### Low

[All Low findings, ordered by file:line]
```
