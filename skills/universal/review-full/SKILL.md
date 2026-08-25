---
name: review-full
description: Whole-codebase review using 9 specialized reviewer agents in parallel against a repomix-packed snapshot.
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔎

# Full Review

Review the entire codebase across 9 focus areas in parallel. Each agent reads from a single repomix-packed snapshot via MCP. Output goes to per-area files in `.llmtmp/review-full/`.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise pack the whole repo.

## Step 1: Resolve Target

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_ROOT=$(cd -P "$PROJECT_ROOT" && pwd -P)
TARGET_PATH="<user-provided path or empty>"
[ -z "$TARGET_PATH" ] && TARGET_PATH="$PROJECT_ROOT"

# Resolve to physical absolute path and verify it stays inside the repo (no traversal, no symlink escape).
TARGET_PATH=$(cd -P "$TARGET_PATH" 2>/dev/null && pwd -P) || { echo "TARGET_PATH does not exist"; exit 1; }
case "$TARGET_PATH" in
  "$PROJECT_ROOT"|"$PROJECT_ROOT"/*) ;;
  *) echo "TARGET_PATH escapes PROJECT_ROOT"; exit 1 ;;
esac

TARGET_NAME=$(basename "$TARGET_PATH")
[ "$TARGET_PATH" = "$PROJECT_ROOT" ] && TARGET_NAME="repo"
```

## Step 2: Clean and Prepare Output

```bash
OUTPUT_DIR="$PROJECT_ROOT/.llmtmp/review-full"
mkdir -p "$OUTPUT_DIR"
find "$OUTPUT_DIR" -mindepth 1 -delete
```

`mkdir -p` then `find -delete` rather than `rm -rf`. A `safe-rm` shim on `PATH` (as in some dotfiles setups) moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

## Step 3: Pack Codebase

```bash
REPOMIX_FILE="$OUTPUT_DIR/repomix.xml"
npx repomix -o "$REPOMIX_FILE" --quiet --output-show-line-numbers "$TARGET_PATH"
```

The repomix file lives inside `OUTPUT_DIR` (`.llmtmp/review-full/`), which is gitignored and wiped at the start of every run by Step 2. No `/tmp` leakage and no `trap` needed. A `trap` does not work here because each bash code block in this skill runs in a separate shell process; an `EXIT` trap registered in Step 3 would fire as soon as Step 3's bash block ends, deleting the file before Step 4 (`attach_packed_output`) can read it.

Repomix reads `.repomixignore` from the project root automatically.

Verify the file was created. Confirm `REPOMIX_FILE` before proceeding.

## Step 4: Attach Packed Output

Call `attach_packed_output` with `filePath=REPOMIX_FILE`. Record the returned `outputId` string. This is the codebase access handle the agents will use.

Do not delegate this step to a subagent. The orchestrator must own the `outputId`.

## Step 5: Dispatch 9 Review Agents in Parallel

Issue all 9 Agent calls **in a single tool block** with `run_in_background: false`. Subagents default to running in the background, and a backgrounded fan-out delivers its results in later turns, so Step 6 would verify files that no agent has written yet.

| Agent                           | Subagent type           | Output file       |
| ------------------------------- | ----------------------- | ----------------- |
| Architecture & Design           | `reviewer-architecture` | `architecture.md` |
| Correctness & Bugs              | `reviewer-correctness`  | `correctness.md`  |
| Data & Information Architecture | `reviewer-data`         | `data.md`         |
| Operational Readiness           | `reviewer-ops`          | `ops.md`          |
| Performance                     | `reviewer-performance`  | `performance.md`  |
| Code Quality                    | `reviewer-quality`      | `quality.md`      |
| Security                        | `reviewer-security`     | `security.md`     |
| SOLID Principles                | `reviewer-solid`        | `solid.md`        |
| Testing                         | `reviewer-testing`      | `testing.md`      |

Each review prompt contains:

1. The `outputId` from Step 4
2. Instruction to use `read_repomix_output` and `grep_repomix_output` for navigation
3. Instruction: "Read AGENTS.md (or CLAUDE.md) and .llmdocs/architecture.md (if present) via the repomix output for project context."
4. Instruction: "Write findings to `<OUTPUT_DIR>/<area>.md`. Use H2 header followed by findings or 'No findings.'"

## Step 6: Wait and Verify

After all 9 agents complete, verify each file in `<OUTPUT_DIR>`:

1. File exists and is non-empty
2. First non-blank line is an H2 header (`## <Area>`)
3. Body contains at least one finding OR exactly the literal `No findings.`

If a file fails any of those checks, treat the agent as having silently failed and re-dispatch that one agent. Do NOT accept a stub like `## Testing\n` with no body or content that omits the H2 header.

## Step 7: Summarize

Produce a summary in the conversation:

```markdown
# Full Review Summary

Target: <TARGET_NAME>
Files reviewed: <count from repomix>

## Findings Counts

| Area                  | High | Medium | Low |
| --------------------- | ---- | ------ | --- |
| Architecture & Design | <N>  | <N>    | <N> |
| Correctness & Bugs    | <N>  | <N>    | <N> |
| Operational Readiness | <N>  | <N>    | <N> |
| Performance           | <N>  | <N>    | <N> |
| Code Quality          | <N>  | <N>    | <N> |
| Security              | <N>  | <N>    | <N> |
| SOLID Principles      | <N>  | <N>    | <N> |
| Testing               | <N>  | <N>    | <N> |

## Output Files

- `.llmtmp/review-full/architecture.md`
- `.llmtmp/review-full/correctness.md`
- `.llmtmp/review-full/ops.md`
- `.llmtmp/review-full/performance.md`
- `.llmtmp/review-full/quality.md`
- `.llmtmp/review-full/security.md`
- `.llmtmp/review-full/solid.md`
- `.llmtmp/review-full/testing.md`

Read individual files for detailed findings.
```

Do not load the file contents into the conversation. The summary is the artifact; files are persistent for follow-up.
