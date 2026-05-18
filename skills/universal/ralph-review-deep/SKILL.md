---
name: ralph-review-deep
description: Multi-model deep review of the Ralph bd graph and plan via three parallel opencode processes (claude opus, gemini, gpt). Use for high-stakes runs where cross-model consensus reduces single-model bias.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔬

# Ralph Review (Deep)

Validate the beads graph and launch three independent reviews of the ralph artifacts in parallel using different models via `opencode run`. Each model produces one review file evaluating goal clarity, task decomposition, sequencing, plan completeness, risk and gaps, and feasibility.

For a faster single-model review using an internal subagent, use the ralph-review skill (/ralph-review, $ralph-review) instead. This deep variant trades wall time and cost for cross-model consensus.

## Models

| Label  | Model ID                      |
| ------ | ----------------------------- |
| openai | openai/gpt-5.3-codex          |
| gemini | google/gemini-3.1-pro-preview |
| claude | az-anthropic/claude-opus-4-6  |

## Procedure

### Step 1: Validate Artifacts Exist

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
```

Verify all of these exist:

- `$PROJECT_ROOT/.llmtmp/ralph-plan.md`
- `$PROJECT_ROOT/.llmtmp/ralph-prompt-insession.md`
- `$PROJECT_ROOT/.llmtmp/ralph-prompt-external.md`
- `$PROJECT_ROOT/.beads/` (directory; bd-aware probe via `bd list >/dev/null 2>&1`)

Abort if any are missing.

### Step 2: Validate the bd Graph

Run these checks before launching opencode. Failures here are HIGH-severity findings and should abort or be flagged loudly.

The bd graph is organized under a per-run epic. The slug is derived from the current branch; the epic is found via the `ralph:<slug>` label. All scoped checks filter by `--parent ${EPIC}`.

```bash
cd "$PROJECT_ROOT"

SLUG=$(git branch --show-current | tr '/' '-')

# 1. Single open epic for this run
EPIC_COUNT=$(bd list -t epic -l "ralph:${SLUG}" --json 2>/dev/null | jq '[.[] | select(.status=="open")] | length')
if [[ "$EPIC_COUNT" -ne 1 ]]; then
  echo "HIGH: expected exactly one open epic with label ralph:${SLUG}, found ${EPIC_COUNT}"
fi
EPIC=$(bd list -t epic -l "ralph:${SLUG}" --json 2>/dev/null | jq -r '[.[] | select(.status=="open")] | .[0].id // empty')

# 2. Cycles
if ! bd dep cycles >/dev/null 2>&1; then
  echo "HIGH: bd graph has dependency cycles"
  bd dep cycles
fi

# 3. Minimum child count under the run epic
COUNT=$(bd list --parent "$EPIC" --json 2>/dev/null | jq 'length')
if [[ "$COUNT" -eq 0 ]]; then
  echo "HIGH: run epic ${EPIC} has no child tasks"
fi

# 4. At least one ready task under the run epic
READY_COUNT=$(bd ready --parent "$EPIC" --json 2>/dev/null | jq 'length')
if [[ "$READY_COUNT" -eq 0 && "$COUNT" -gt 0 ]]; then
  echo "HIGH: run epic ${EPIC} has tasks but no ready tasks (deadlock or all closed unexpectedly)"
fi

# 5. Isolated nodes within the run epic
if [[ "$COUNT" -gt 1 ]]; then
  bd list --parent "$EPIC" --json 2>/dev/null \
    | jq -r '.[] | select(.dependency_count == 0 and .dependent_count == 0) | "MEDIUM: isolated task " + .id + " " + .title'
fi

# 6. Description coverage: every child carries the worker's instructions
bd list --parent "$EPIC" --json 2>/dev/null \
  | jq -r '.[] | select(((.description // "") | length) == 0) | "HIGH: task " + .id + " has empty description: " + .title'

# 7. Parent set equals label set (defense-in-depth orphan detection)
PARENT_IDS=$(bd list --parent "$EPIC" --json 2>/dev/null | jq -r '.[].id' | sort)
LABEL_IDS=$(bd list --label "ralph:${SLUG}" --json 2>/dev/null | jq -r '.[] | select(.issue_type != "epic") | .id' | sort)
if [[ "$PARENT_IDS" != "$LABEL_IDS" ]]; then
  echo "HIGH: parent set (--parent ${EPIC}) and label set (--label ralph:${SLUG} excluding epic) differ"
  echo "Parent-only (label missing): $(comm -23 <(echo "$PARENT_IDS") <(echo "$LABEL_IDS"))"
  echo "Label-only (orphan, parent missing): $(comm -13 <(echo "$PARENT_IDS") <(echo "$LABEL_IDS"))"
fi
```

Persist these findings; the reviewers reference them in their final reports.

### Step 3: Clean Up Previous Reviews

```bash
rm -f "$PROJECT_ROOT"/.llmtmp/ralph-review-openai.md \
      "$PROJECT_ROOT"/.llmtmp/ralph-review-gemini.md \
      "$PROJECT_ROOT"/.llmtmp/ralph-review-claude.md
```

### Step 4: Read Files and Build Prompt Context

Concatenate the contents of these files into a single `CONTEXT` string:

1. `.llmtmp/ralph-plan.md`
2. `.llmtmp/ralph-prompt-insession.md`
3. `.llmtmp/ralph-prompt-external.md`
4. The slug and epic ID resolved in Step 2 (literal label `SLUG=...` and `EPIC=...`)
5. Output of `bd list --parent "$EPIC" --json`
6. Output of `bd ready --parent "$EPIC" --json`
7. Output of `bd list --label "ralph:${SLUG}" --json`
8. The bd graph validation findings from Step 2
9. Plan documents listed in the plan's `plan documents:` line. Parse the line, split on commas, trim whitespace, read each path. Wrap each as `=== plan-documents/<path> ===` so the reviewer can distinguish them from baseline. Empty value means no plan documents to load.
10. `CLAUDE.md` and `README.md` from project root (if they exist)
11. All `.md` files in `.llmdocs/`

Wrap each as:

```text
=== <relative-path or label> ===
<contents>
```

### Step 5: Construct the Review Prompt

Build the prompt that each opencode process executes. Replace `<PROJECT_ROOT>` and `<CONTEXT>`:

```text
PROMPT="You are a plan reviewer running headless in a non-interactive session. There is no user present. Do not ask questions. Do not prompt for confirmation. Do not stop to wait for input.

YOUR PRIMARY OBJECTIVE IS TO WRITE A FILE. Everything else is preparation. After completing your review, your VERY NEXT action must be a tool call that writes the output file. Do not summarize, do not reflect, do not plan — write the file immediately.

OUTPUT RULES: You are running headless. Nobody reads your text responses. ALL review content goes exclusively into the output file via tool calls. Any text you generate outside of a tool call is wasted tokens and risks hitting the output token limit before you can write the file. Keep text responses to one short sentence at most.

PROJECT_ROOT: <PROJECT_ROOT>

## Context

<CONTEXT>

## How Ralph Loops Work

A ralph loop is an autonomous, iterative execution mechanism. Two execution modes share the same artifacts:

- **In-session (ralph-loop plugin)**: a Stop hook re-feeds the prompt to the same Claude session. Cheap on short runs; expensive on long runs because context grows quadratically.
- **External (scripts/ralph.sh)**: a bash while-loop spawns a fresh `claude --print` per iteration. Higher fixed overhead per iteration; stays in the cheap part of the cost curve indefinitely.

Authority sources in CONTEXT:

The CONTEXT contains two distinct authority categories. Treat them differently.

- **Plan documents** (under `=== plan-documents/...` blocks): forward-looking intent the planner consulted, e.g., a PRD, a Jira ticket, a design note. The plan must faithfully render these. Flag the plan if it omits, contradicts, or stale-references a requirement from a plan document.
- **Baseline docs** (`CLAUDE.md`, `README.md`, `.llmdocs/*`): the system's current state. The plan's job is to change this state. Do NOT flag the plan for deviating from baseline. Flag only if the plan changes baseline without including a corresponding docs-update bead (typically delegated to the docs skill).

Mechanics that apply to both modes:

- The bd graph is the state machine. The graph is shared across worktrees of the same repo. Each ralph run is organized under a per-run epic so concurrent runs in different worktrees stay isolated by `--parent` filtering. `bd ready --parent <epic> --json` finds the next unblocked task within this run.
- The run epic carries the label `ralph:<slug>` where `<slug>` is derived from the current branch. Every child task carries both `--parent <epic>` and the same `ralph:<slug>` label. The two signals are independent so the reviewer can detect orphans.
- The plan's "Run Identity" section records the literal slug and epic ID. The agent reads them directly from the plan each iteration, no derivation.
- One task per iteration. The agent reads `bd ready --parent <epic> --json`, takes the first result, runs the per-task workflow, then closes the task.
- When the ready queue is empty, the agent closes the epic and emits the sentinel as the terminal action. The epic is not closed by `bd` automatically.
- Resumable. A partially-completed graph resumes cleanly. Partial completion is normal; iterations are cheap.
- Every action is a bd task, including ralph lifecycle scaffolding. The branch creation, BEGIN tag, code work, docs, and END tag are all first-class beads, all parented to the run epic.
- Each bead carries its full per-task instructions in its description: files to touch, expected behavior, verification command, commit message. The worker reads `bd show <id>` and executes the description exactly.
- Run-wide conventions (commit style, language, build command, test command) live in `ralph-plan.md`, not in every description.
- Environment is a precondition. Credentials, network, toolchain, and runtime dependencies are the operator's responsibility. Do not flag missing environment setup as a gap.

Do NOT recommend: collapsing tasks into bundles, adding environment preflight checks, treating partial completion as a risk, modifying the prompt body, replacing the bd graph with a markdown checklist, or reintroducing a workflow-label taxonomy. The `ralph:<slug>` label is run-identity for partition and orphan detection, not workflow dispatch; do not flag it as a label taxonomy.

Flag as HIGH severity if: zero or more than one open epic exists for `ralph:<slug>`; any open child has an empty description; the bd graph contains cycles; the run epic has no children; the run epic has children but no ready tasks; the parent set under the epic differs from the label set for `ralph:<slug>` (orphans or planning typos); the per-task workflow does not explicitly stop after `bd close` (the agent will do multiple beads in one context, defeating the Ralph design); the per-task workflow does not close the epic before emitting the sentinel; the plan lacks a "Run Identity" section recording the literal slug and epic ID; the plan lacks an "Inputs" section with a `plan documents:` line; the plan omits or contradicts a material requirement explicit in any plan document; the plan's Approach prose declares an ordering ("X first", "after Y") that the bd dependency edges do not enforce. Flag as MEDIUM if: a description omits the verification command or commit message; an isolated task exists in a multi-task graph; the plan duplicates information that already lives in bead descriptions; a bead that touches README.md/CLAUDE.md/.llmdocs/ authors edits inline instead of running the docs skill.

## Your Task

Review the Ralph artifacts:

- ralph-plan.md (mode-neutral execution plan)
- ralph-prompt-insession.md (slash-command wrapper for the in-session driver)
- ralph-prompt-external.md (body for scripts/ralph.sh)
- The bd graph (issues, dependencies, ready/closed state)

Evaluate across these areas:

### 1. Goal Clarity

- Is the objective well-defined and unambiguous?
- Would a fresh-context iteration understand what success looks like from the plan alone?

### 2. Task Decomposition

- Are tasks the right granularity (one focused deliverable each)?
- Is each task independently completable?
- Are there missing tasks needed to achieve the goal?
- Are there unnecessary or redundant tasks?
- Do titles name deliverables rather than techniques?
- Do descriptions carry enough detail (files, verification, commit message) for a cold-start worker?

### 3. Sequencing and Dependencies

- Are dependencies correct in the bd graph?
- Would executing in `bd ready --json` order produce correct results?
- Are there implicit dependencies that should be explicit edges?
- Are there cycles or isolated nodes?

### 4. Plan Completeness

- Do the instructions cover repo-specific conventions, tools, and commands?
- Are build, test, and lint commands accurate?
- Is the per-task workflow clear (read description, execute it, close)?
- Does the plan have a "Run Identity" section that records the literal branch slug, the literal epic ID, and the epic label `ralph:<slug>`?
- Does the Per-Task Workflow read the epic ID from the "Run Identity" section and scope `bd ready` with `--parent <epic-id>`?
- Does the Per-Task Workflow close the epic via `bd close <epic-id>` before emitting the sentinel when the ready queue is empty?
- Does the Per-Task Workflow explicitly say STOP after `bd close` so the agent does not loop within a single context?
- Does the Git Workflow section require a `ralph/` feature branch and BEGIN/END tags?
- Is the Per-Task Workflow explicit that `bd close` for the current task runs BEFORE the sentinel?
- Do beads that touch `README.md`, `CLAUDE.md`, or `.llmdocs/` invoke the docs skill (/docs, $docs) rather than authoring edits inline?

### 5. Risk and Gaps

- What could go wrong during autonomous execution?
- Are there tasks that require human judgment or external access?
- Could any task leave the repo in a broken state?

### 6. Feasibility

- Can a single iteration realistically complete each task?
- Are there tasks that exceed what a fresh context can do autonomously?

For each area, list specific findings with severity (high/medium/low) and actionable recommendations.

## Output

Your VERY NEXT action after the review must be a tool call that writes the file. No intermediate steps.

Determine your model label:

- Claude variants: claude
- GPT variants: openai
- Gemini variants: gemini

Write to `<PROJECT_ROOT>/.llmtmp/ralph-review-$MODEL_LABEL.md` using this template:

\`\`\`markdown
# Ralph Loop Review
**Model**: <MODEL_LABEL>

## Goal Clarity

- **[medium]** Short title. Explanation...

## Task Decomposition

- **[high]** Short title. Explanation...

## Sequencing and Dependencies

- **[medium]** Short title. Explanation...

## Plan Completeness

- **[low]** Short title. Explanation...

## Risk and Gaps

- **[high]** Short title. Explanation...

## Feasibility

- **[medium]** Short title. Explanation...

## Summary

<overall assessment and top 3 recommendations>
\`\`\`

Finding format: \`- **[severity]** Title. Description.\`

Every section must be present. If no findings for an area, write 'No findings.' under its heading.

Then verify: \`ls -la '<PROJECT_ROOT>/.llmtmp/ralph-review-<MODEL_LABEL>.md'\`

If the file does not exist, write it again. Do not exit without the file."
```

### Step 6: Write Prompt to File

Avoid shell interpolation issues with large prompts:

```bash
STATE_DIR="$PROJECT_ROOT/.llmtmp/ralph_review_state"
mkdir -p "$STATE_DIR"
OPENAI_DIR=$(mktemp -d)
GEMINI_DIR=$(mktemp -d)
CLAUDE_DIR=$(mktemp -d)
cat > /tmp/ralph-review-prompt.txt <<'PROMPT_EOF'
<the prompt from Step 5>
PROMPT_EOF
```

### Step 7: Launch 3 Separate Background Bash Tasks

Each opencode process must run as its own background Bash task. Do NOT chain them in a single shell with `&`; child processes get killed when the parent exits.

OpenAI:

```bash
STATE_DIR="<PROJECT_ROOT>/.llmtmp/ralph_review_state" && \
opencode run \
  -m openai/gpt-5.3-codex \
  --format json \
  --print-logs \
  --log-level INFO \
  --dir "<OPENAI_DIR>" \
  --title "Ralph Review - OpenAI" \
  "$(cat /tmp/ralph-review-prompt.txt)" \
  > "$STATE_DIR/openai.ndjson" 2>"$STATE_DIR/openai.log"
```

Gemini:

```bash
STATE_DIR="<PROJECT_ROOT>/.llmtmp/ralph_review_state" && \
opencode run \
  -m google/gemini-3.1-pro-preview \
  --format json \
  --print-logs \
  --log-level INFO \
  --dir "<GEMINI_DIR>" \
  --title "Ralph Review - Gemini" \
  "$(cat /tmp/ralph-review-prompt.txt)" \
  > "$STATE_DIR/gemini.ndjson" 2>"$STATE_DIR/gemini.log"
```

Claude:

```bash
STATE_DIR="<PROJECT_ROOT>/.llmtmp/ralph_review_state" && \
opencode run \
  -m az-anthropic/claude-opus-4-6 \
  --format json \
  --print-logs \
  --log-level INFO \
  --dir "<CLAUDE_DIR>" \
  --title "Ralph Review - Claude" \
  "$(cat /tmp/ralph-review-prompt.txt)" \
  > "$STATE_DIR/claude.ndjson" 2>"$STATE_DIR/claude.log"
```

All 3 launch as separate background tasks. Do NOT use `&` in a single shell.

#### Output Streams

Each opencode process produces two output files:

- **`<label>.ndjson`** (stdout): Structured NDJSON events from `--format json`. Use for programmatic progress tracking.
- **`<label>.log`** (stderr): Plain-text info-level logs. Use for diagnosing startup failures, permission issues, MCP server errors, plugin loading.

Log lines are structured text, one per line:

```text
INFO  2026-03-13T00:54:25 +4ms service=default directory=/private/tmp creating instance
```

### Step 8: Monitor and Wait

Poll each background task until all 3 complete.

NDJSON progress (replace `$NDJSON` with the actual path):

```bash
# Count completed steps
grep -c '"type":"step_finish"' "$NDJSON" 2>/dev/null || echo 0

# Check if done (last step_finish has reason "stop")
tail -1 "$NDJSON" 2>/dev/null | jq -r '.part.reason // empty'

# Check for errors
grep '"type":"error"' "$NDJSON" 2>/dev/null
```

Text logs (replace `$LOGFILE` with the actual path):

```bash
# Errors or warnings
grep -E "^(ERROR|WARN)" "$LOGFILE" 2>/dev/null

# Recent activity
tail -5 "$LOGFILE" 2>/dev/null
```

### Step 9: Report Results

For each model, check whether `.llmtmp/ralph-review-<label>.md` exists.

Report per model:

- Success or failure (file present or not)
- Total cost: sum of `cost` from all `step_finish` events
- Whether any errors occurred

Surface the bd graph validation findings from Step 2 separately at the top of the report.

### Step 10: Cleanup

The state directory is preserved for post-run inspection (per-model NDJSON event streams and text logs are useful for diagnosing review failures, calibration regressions, and cost trends).

```bash
rm -f /tmp/ralph-review-prompt.txt
```

`$STATE_DIR` (`.llmtmp/ralph_review_state/`) is intentionally NOT removed. Each subsequent reviewer run overwrites the per-model files in place; if historical retention is needed, archive the directory before re-running.

## Expected Output Files

3 files total, one per model:

- `.llmtmp/ralph-review-openai.md`
- `.llmtmp/ralph-review-gemini.md`
- `.llmtmp/ralph-review-claude.md`

## NDJSON Log Format Reference

Each opencode process writes NDJSON to `$STATE_DIR/<label>.ndjson`. One JSON object per line. Skip lines that fail to parse (partial writes).

Key event types:

- **step_start** - New LLM turn begins.
- **text** - Model emitted text: `{"type":"text","part":{"text":"..."}}`
- **tool_use** - Tool call: `{"type":"tool_use","part":{"tool":"bash","state":{"status":"completed","metadata":{"exit":0}}}}`
- **step_finish** - Turn completed: `{"type":"step_finish","part":{"reason":"stop","cost":0,"tokens":{"total":13494}}}`. `reason: "stop"` = done, `reason: "tool-calls"` = continuing.
- **error** - Session error: `{"type":"error","error":{"data":{"message":"..."}}}`

Useful jq queries (replace `$NDJSON` with the actual path):

```bash
NDJSON="<PROJECT_ROOT>/.llmtmp/ralph_review_state/openai.ndjson"
# Is done?
tail -1 "$NDJSON" | jq -r 'select(.type=="step_finish") | .part.reason'
# Total cost
jq -s '[.[] | select(.type=="step_finish") | .part.cost] | add' "$NDJSON"
# All errors
jq -r 'select(.type=="error") | .error.data.message' "$NDJSON"
```

Replace `$LOGFILE` with the text log path:

```bash
grep -E "^(ERROR|WARN)" "$LOGFILE"
```

## Rules

- The invoking agent is ONLY a launcher. All review work happens inside the opencode processes.
- Do NOT perform any review analysis directly. The opencode processes handle reviewing.
- Do NOT ask questions during execution. This is non-interactive.
- Launch all 3 processes in parallel. Do not wait for one to finish before starting another.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the c7 MCP server.
- Preserve the state directory after reporting results. NDJSON and log files stay for post-run inspection.
- If a model fails, still wait for and report the others.
- The bd graph validation in Step 2 runs in the invoking agent, not in opencode. Findings are passed to opencode reviewers as context.
