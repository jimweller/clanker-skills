---
name: review-deep
description: Whole-codebase deep audit launching parallel code reviews across OpenAI, Gemini, and Claude via opencode run.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🕵️‍♂️

# Code Review Command

Launch 3 independent code reviews in parallel using different models via `opencode run`. The invoking agent packs repomix once, then each model spawns 8 reviewer-* subagents that navigate the packed output via MCP. Each model produces one combined review file.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise review the whole repo.

## Models

| Label  | Model ID                      |
| ------ | ----------------------------- |
| openai | openai/gpt-5.5                |
| gemini | google/gemini-3.1-pro-preview |
| claude | az-anthropic/claude-opus-4-6  |

## Procedure

### Step 1: Resolve Target and Clean Up

`````text
TARGET_PATH = <user-provided path or empty>

If TARGET_PATH is empty or not provided: use git repo root.
Otherwise: resolve as relative path from repo root.

Derive TARGET_NAME from last path segment, or "repo" if root.
```text

Validate the target directory exists. Abort if not.

Delete previous final review files and ensure output directories. Do NOT delete per-area files, NDJSON, or logs.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
rm -f "$PROJECT_ROOT"/.llmtmp/review-"$TARGET_NAME"-openai.md \
      "$PROJECT_ROOT"/.llmtmp/review-"$TARGET_NAME"-gemini.md \
      "$PROJECT_ROOT"/.llmtmp/review-"$TARGET_NAME"-claude.md
mkdir -p "$PROJECT_ROOT/.llmtmp" "$PROJECT_ROOT/.llmtmp/review-deep"
```text

### Step 2: Pack Repomix

Pack the target using the repomix CLI. This avoids the MCP tool's large result payload which
triggers a confusing truncation error in some agent UIs on large repos.

```bash
REVIEW_TMPDIR=$(mktemp -d "/tmp/code-review-XXXXXX")
REPOMIX_FILE="$REVIEW_TMPDIR/repomix.xml"
npx repomix -o "$REPOMIX_FILE" --quiet --output-show-line-numbers "$PROJECT_ROOT/$TARGET_PATH"
```text

`REVIEW_TMPDIR` is unique per run and used for all temp files in this session.

Repomix reads `.repomixignore` from the project root automatically.

Verify the file was created, then confirm `REPOMIX_FILE` to the user before proceeding.

### Step 3: Construct the Orchestrator Prompt

Build the prompt that each opencode process will execute. Replace `<TARGET_PATH>`, `<TARGET_NAME>`, `<PROJECT_ROOT>`, and `<REPOMIX_FILE>` with the resolved values.

````text
PROMPT="You are a code review orchestrator running headless in a non-interactive session. There is no user present. Do not ask questions. Do not prompt for confirmation.

You have 4 steps. You are NOT done until the file is written and verified in Step 4.
Stopping before Step 4 is a failure. Do not print any completion markers until Step 4.

OUTPUT RULES: Keep interactive text responses to one short sentence. Your primary job is making tool calls and writing to files.

TARGET_PATH: <TARGET_PATH>
TARGET_NAME: <TARGET_NAME>
REPOMIX_FILE: <REPOMIX_FILE>

CRITICAL: The repository is ALREADY packed. Do NOT call pack_codebase or repomix yourself.

MODEL_LABEL: Derive from your model identity (claude, openai, or gemini).
OUTPUT_FILE: <PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-$MODEL_LABEL.md

# Step 1: Attach the packed output

YOU (the orchestrator) must call the attach_packed_output MCP tool DIRECTLY with filePath=REPOMIX_FILE.
Do NOT delegate this to a subagent. Do NOT use the task tool for this step.
Record the returned outputId string. This is the ONLY way to access the codebase.
Do NOT read REPOMIX_FILE directly.

# Step 2: Spawn review agents

Spawn ALL 8 review agents. Note: opencode executes task calls sequentially (known issue #14195), so agents will run one at a time regardless of how they are requested.
Use the agent name `reviewer-<area>` for each. Each agent prompt MUST include:
- outputId=<the outputId from Step 1>
- OUTPUT_PATH=<STATE_DIR>/<MODEL_LABEL>-<area>.md

STATE_DIR: <PROJECT_ROOT>/.llmtmp/review-deep

Areas and agent names:
- reviewer-security -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-security.md
- reviewer-architecture -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-architecture.md
- reviewer-solid -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-solid.md
- reviewer-correctness -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-correctness.md
- reviewer-testing -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-testing.md
- reviewer-ops -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-ops.md
- reviewer-performance -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-performance.md
- reviewer-quality -> OUTPUT_PATH: <STATE_DIR>/<MODEL_LABEL>-quality.md

Each agent writes its own per-area file. The agent definitions handle the review logic.

# Step 3: Assemble the review file

After all 8 agents return, assemble the per-area files into the final review file using bash:

```bash
echo "# Code Review: <TARGET_NAME>" > OUTPUT_FILE
echo "**Model**: MODEL_LABEL" >> OUTPUT_FILE
echo "" >> OUTPUT_FILE
for area in security architecture solid correctness testing ops performance quality; do
  cat "<STATE_DIR>/<MODEL_LABEL>-$area.md" >> OUTPUT_FILE
  echo "" >> OUTPUT_FILE
done
````text

# Step 4: Verify

Run: ls -la 'OUTPUT_FILE'
Run: head -5 'OUTPUT_FILE'

Both commands must succeed. If the file does not exist or is empty, re-run the assembly step.
Do not exit without the file on disk.

Print exactly: REVIEW_COMPLETE"

````text

### Step 4: Write Prompt to File

Write the prompt string to a temp file. This avoids shell interpolation issues with large prompts.

```bash
STATE_DIR="$PROJECT_ROOT/.llmtmp/review-deep"
mkdir -p "$STATE_DIR"
OPENAI_DIR=$(mktemp -d)
GEMINI_DIR=$(mktemp -d)
CLAUDE_DIR=$(mktemp -d)
PROMPT_FILE="$REVIEW_TMPDIR/review-prompt.txt"
cat > "$PROMPT_FILE" <<'PROMPT_EOF'
<the prompt from step 3>
PROMPT_EOF
````text

### Step 5: Launch 3 Agents in Parallel

Spawn 3 subagents simultaneously. Each subagent launches one opencode process, monitors it to completion, and reports the result. This ensures true parallel execution.

Each subagent receives the same instruction template with its model-specific values substituted. The subagent's job is:

1. Launch the opencode process as a background Bash task (`run_in_background`)
2. Poll NDJSON progress every `POLL_INTERVAL` seconds until the process finishes (reason: "stop") or errors out
3. Report success/failure, cost, token count, and whether the output file exists

`POLL_INTERVAL` defaults to 30 seconds. Adjust if the model is faster or slower than typical opencode runs.

**Subagent prompt template** (substitute `<LABEL>`, `<MODEL_ID>`, `<TEMP_DIR>`, `<STATE_DIR>`, `<TARGET_NAME>`, `<PROJECT_ROOT>`):

```text
Launch and monitor an opencode code review process. Do not ask questions.

Run this command in the background:

STATE_DIR="<STATE_DIR>" && \
opencode run \
  -m <MODEL_ID> \
  --format json \
  --print-logs \
  --log-level INFO \
  --dir "<TEMP_DIR>" \
  --title "Review - <LABEL>" \
  "$(cat "$PROMPT_FILE")" \
  > "$STATE_DIR/<LABEL>.ndjson" 2>"$STATE_DIR/<LABEL>.log"

Then poll every POLL_INTERVAL seconds using:
  grep -c '"type":"step_finish"' "$STATE_DIR/<LABEL>.ndjson"
  tail -1 "$STATE_DIR/<LABEL>.ndjson" | jq -r '.part.reason // empty'
  grep -c '"type":"error"' "$STATE_DIR/<LABEL>.ndjson"

Stop polling when the last step_finish reason is "stop" or the background task exits.

When done:

1. Check if <PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md exists.
2. If NOT, check for per-area files: ls "$STATE_DIR/<LABEL>-*.md"
3. If per-area files exist, assemble the final review file:
   echo "# Code Review: <TARGET_NAME>" > "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   echo "**Model**: <LABEL>" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   echo "" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   for area in security architecture solid correctness testing ops performance quality; do
     cat "$STATE_DIR/<LABEL>-$area.md" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md" 2>/dev/null
     echo "" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   done

Report:
- Whether the final review file exists (and whether fallback assembly was used)
- How many per-area files were found: ls "$STATE_DIR/<LABEL>-*.md" 2>/dev/null | wc -l
- Total cost: jq -s '[.[] | select(.type=="step_finish") | .part.cost] | add' "$STATE_DIR/<LABEL>.ndjson"
- Total tokens: grep '"type":"step_finish"' "$STATE_DIR/<LABEL>.ndjson" | tail -1 | jq '.part.tokens.total'
- Any errors from: grep '"type":"error"' "$STATE_DIR/<LABEL>.ndjson"
```text

Launch all 3 subagent calls in a single parallel batch (openai, gemini, claude).

#### Output Streams

Each opencode process produces two output files:

- **`<label>.ndjson`** (stdout): Structured NDJSON events from `--format json`. Use for programmatic progress tracking (step counts, cost, tool calls, completion detection).
- **`<label>.log`** (stderr): Plain-text info-level logs from `--print-logs --log-level INFO`. Use for diagnosing startup failures, permission issues, MCP server errors, and plugin loading problems.

Log lines are structured text, one per line:

```text
INFO  2026-03-13T00:54:25 +4ms service=default directory=/private/tmp creating instance
```text

### Step 6: Wait for Agents

The 3 subagents from Step 5 handle monitoring. Wait for all 3 to return. Each reports its model's success/failure, cost, tokens, and errors.

### Step 7: Report Results

Collect the reports from each subagent. Summarize per model:

- Success/failure (output file present or not)
- Total cost
- Total tokens
- Any errors

### Step 8: Synthesize Reviews

Read all successfully produced review files (`.llmtmp/review-<TARGET_NAME>-*.md`). Compare findings across models and report:

1. **Quorum findings (3/3)** — issues flagged by all three models. List each with the area, severity, and finding.
2. **Quorum findings (2/3)** — issues flagged by two models. List each with the area, severity, which models agreed, and which did not.
3. **Single-model findings** — issues flagged by only one model. List all of them. Note which model raised each.
4. **Conflicting assessments** — areas where models disagree (e.g., one flags a risk, another says it's fine).

Include every finding. Do not skip or summarize away any items.

## Expected Output Files

3 files total, one per model:

- `.llmtmp/review-<TARGET_NAME>-openai.md`
- `.llmtmp/review-<TARGET_NAME>-gemini.md`
- `.llmtmp/review-<TARGET_NAME>-claude.md`

Where `<TARGET_NAME>` is derived from the path's last segment (or `repo` for root).

## NDJSON Log Format Reference

Each opencode process writes NDJSON to `$STATE_DIR/<label>.ndjson`. One JSON object per line. Skip lines that fail to parse (partial writes).

### Event Types

**step_start** - A new LLM turn begins.

```json
{
  "type": "step_start",
  "timestamp": 1773360681884,
  "sessionID": "ses_...",
  "part": { "type": "step-start", "snapshot": "..." }
}
```text

**text** - Model emitted text output.

```json
{
  "type": "text",
  "timestamp": 1773360682061,
  "sessionID": "ses_...",
  "part": { "type": "text", "text": "some output" }
}
```text

**tool_use** - Model called a tool. Key fields: `tool` (tool name), `state.status` ("completed" or "error"), `state.input`, `state.output`, `state.metadata.exit` (for bash).

```json
{
  "type": "tool_use",
  "timestamp": 1773360682369,
  "sessionID": "ses_...",
  "part": {
    "tool": "bash",
    "state": {
      "status": "completed",
      "input": { "command": "echo hello" },
      "output": "hello\n",
      "metadata": { "exit": 0 }
    }
  }
}
```text

For subagent spawns, `tool` is "task" and `state.output` contains the agent's result text:

```json
{"type":"tool_use","timestamp":...,"part":{"tool":"task","state":{"status":"completed","input":{"description":"...","prompt":"..."},"output":"<task_result>...</task_result>"}}}
```text

**step_finish** - An LLM turn completed. Key fields: `reason` ("stop" = done, "tool-calls" = continuing), `cost`, `tokens`.

```json
{
  "type": "step_finish",
  "timestamp": 1773360682446,
  "sessionID": "ses_...",
  "part": {
    "reason": "tool-calls",
    "cost": 0,
    "tokens": {
      "total": 13494,
      "input": 2,
      "output": 77,
      "reasoning": 0,
      "cache": { "read": 0, "write": 13415 }
    }
  }
}
```text

The final `step_finish` with `"reason":"stop"` means the model is done.

**error** - An error occurred at the session level.

```json
{"type":"error","timestamp":...,"sessionID":"ses_...","error":{"name":"UnknownError","data":{"message":"Model not found: ..."}}}
```text

### Useful jq Queries

Replace `$NDJSON` with the actual NDJSON file path (e.g., `<PROJECT_ROOT>/.llmtmp/review-deep/openai.ndjson`).

```bash
# Is the process done? (last step_finish reason is "stop")
tail -1 "$NDJSON" | jq -r 'select(.type=="step_finish") | .part.reason'

# Total cost
jq -s '[.[] | select(.type=="step_finish") | .part.cost] | add' "$NDJSON"

# Total tokens from final step
tac "$NDJSON" | jq -s 'first(.[] | select(.type=="step_finish")) | .part.tokens.total'

# All tool calls and their status
jq -r 'select(.type=="tool_use") | "\(.part.tool): \(.part.state.status)"' "$NDJSON"

# All errors from NDJSON events
jq -r 'select(.type=="error") | .error.data.message' "$NDJSON"

# Count subagent spawns
jq -r 'select(.type=="tool_use" and .part.tool=="task") | .part.state.status' "$NDJSON" | wc -l
```text

Replace `$LOGFILE` with the text log path (e.g., `<PROJECT_ROOT>/.llmtmp/review-deep/openai.log`):

```bash
# All errors and warnings from text logs
grep -E "^(ERROR|WARN)" "$LOGFILE"
```text

## Rules

- The invoking agent is a launcher and synthesizer. All review work happens inside the opencode processes. The invoking agent reads the finished review files and synthesizes a cross-model comparison.
- Do NOT perform any review analysis during Steps 1-7. Only analyze review outputs in Step 8.
- Do NOT ask questions during execution. This is non-interactive.
- Launch all 3 subagents in a single parallel batch. NEVER launch sequentially.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the context7 MCP server.
- Do NOT clean up per-area files, NDJSON logs, or text logs. All intermediate artifacts persist for debugging and evals.
- If a model fails, still wait for and report the others.
`````
