---
name: review-deep
description: Whole-codebase deep audit launching parallel code reviews across OpenAI, Gemini, and Claude via opencode run, with reviewers navigating the live tree through Serena.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🕵️‍♂️

# Code Review Command

Launch 3 independent code reviews in parallel using different models via `opencode run`. Each model spawns 9 reviewer-* subagents that navigate the live working tree through Serena's symbolic tools. Each model produces one combined review file.

Nothing is packed. Reviewers read the code as it sits on disk, so a citation points at a real line in a real file and can be confirmed by opening it.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise review the whole repo.

## Models

| Label  | Model ID                      |
| ------ | ----------------------------- |
| openai | openai/gpt-5.6-sol            |
| gemini | google/gemini-pro-latest      |
| claude | az-anthropic/claude-opus-5    |

`gemini-pro-latest` is an alias. On 2026-09-22 it resolved to `gemini-3.1-pro-preview`, confirmed by the `modelVersion` field in the API response. Google re-points it when a newer pro ships, so the arm can change behavior without a commit here. Check `modelVersion` in the NDJSON when a run's findings shift for no other reason.

OpenAI ships the 5.6 line as three codenamed variants, `sol`, `luna`, and `terra`, with no plain `gpt-5.6` and no date suffix. The provider exposes no metadata distinguishing them.

Every ID must exist in `configs/opencode/opencode.json` under the matching provider. An absent ID fails that whole arm with `Model not found`, which surfaces only as an `error` event in the model's NDJSON. After any model upgrade, confirm the list first.

```bash
jq -r '.provider | to_entries[] | .key as $p | .value.models | keys[] | "\($p)/\(.)"' ~/.config/opencode/opencode.json
```

### MCP surface

Serena must be enabled in `~/.config/opencode/opencode.json` and started with `--project-from-cwd`. Without it the reviewers have no navigation at all, because this skill packs nothing.

Every MCP server enabled there has its tool schemas sent to every model. Gemini validates those schemas more strictly than OpenAI or Anthropic and rejects an array-typed parameter whose `items` carries no explicit type.

Measured on 2026-09-21, `google/gemini-3.1-pro-preview` failed with `AI_APICallError ... field predicate failed: $type == Type.ARRAY`, naming 8 declarations from the `researcher` server. It reproduces byte for byte: exit 1, one `error` event, 5712 bytes of NDJSON, zero `step_finish`.

This is not a startup failure. The log records it at `agent=build mode=primary` during a `stream` call, so the session was created and the loop was running. Tool schemas are assembled per agent at stream time, which is what makes a per-agent exclusion the right lever. It has nothing to do with serena, and every rejected property belongs to a `researcher` tool.

Two things address this, and only the first is active.

`researcher` is disabled outright in `configs/opencode/opencode.json` (`"enabled": false`). With it off, all three models run clean and no agent is needed. Verified on 2026-09-22: gemini went from a 5707-byte rejection to `PONG` with zero errors, on the same model ID, with only that one key changed.

`configs/opencode/agents/review-orchestrator.md` is a `primary` agent carrying `tools: { researcher_*: false }`, and Step 5 passes `--agent review-orchestrator` on every arm. It is redundant while researcher is globally disabled. It stays because the global setting is temporary and because it keeps the review path independent of whatever the global MCP config happens to be. Re-enabling researcher for interactive use costs the review arms nothing.

Verified on 2026-09-22, before researcher was disabled:

| Run | Bytes | Errors | Reply |
| --- | ----- | ------ | ----- |
| gemini, no agent | 5712 | 1 | none, schema rejection |
| gemini, `--agent review-orchestrator` | 939 | 0 | `PONG` |
| openai, `--agent review-orchestrator` | 1055 | 0 | `PONG` |

The glob is `researcher_*`, not `researcher*`. MCP tools register as `<server>_<tool>`, so the underscore form is the documented one.

The agent file is glob-linked by `configs/opencode/agents/*`, so `./install` links it. A machine that has not run install since it was added has no such agent, and `opencode run --agent review-orchestrator` fails there.

The root cause is not researcher being broken. It declares optional arrays as a union type, `"type": ["null","array"]`, which is valid JSON Schema. Anthropic and OpenAI accept it. Google converts JSON Schema to its own OpenAPI-subset proto, turns the union into `any_of`, drops `items` from the array branch, and then rejects its own output with `any_of[0].items: missing field`. Any MCP server using that pattern will break a Google arm the same way.

### Never wrap `opencode run` in `timeout`

`opencode run` under GNU `timeout` hangs before it creates a session. It writes the `init` log line and nothing after: zero NDJSON bytes, zero `error` events, no session, no API call. `timeout --foreground` does not help.

Measured on 2026-09-22 with coreutils 9.11, alternating launch modes against the same model and prompt across two rounds:

| Launch | Result |
| ------ | ------ |
| `opencode run ...` unwrapped | 1053 bytes, both rounds |
| `timeout 60 opencode run ...` | 0 bytes, both rounds |
| `timeout --foreground 60 opencode run ...` | 0 bytes, both rounds |

To bound a run, background it and poll the PID instead.

```bash
opencode run ... > "$OUT" 2>"$LOG" &
pid=$!
i=0; while kill -0 "$pid" 2>/dev/null && [ "$i" -lt 900 ]; do sleep 5; i=$((i+5)); done
kill -9 "$pid" 2>/dev/null
```

This cost a full debugging session. A `timeout` wrapper added to a diagnostic harness produced a 44 percent apparent failure rate across 69 runs, which was then explained by six different theories about opencode, its config, its database, and its MCP servers. Every one of them was wrong. opencode was working the whole time. The Step 5 subagent template invokes `opencode run` directly and is unaffected.

## Procedure

### Step 1: Resolve Target and Clean Up

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

STATE_DIR="$PROJECT_ROOT/.llmtmp/review-deep"
mkdir -p "$PROJECT_ROOT/.llmtmp" "$STATE_DIR"

# Delete the previous final review files for this target only.
find "$PROJECT_ROOT/.llmtmp" -maxdepth 1 -name "review-$TARGET_NAME-*.md" -delete

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "TARGET_PATH=$TARGET_PATH"
echo "TARGET_NAME=$TARGET_NAME"
echo "STATE_DIR=$STATE_DIR"
```

`find -delete` rather than `rm -f`. A `safe-rm` shim on `PATH` (as in some dotfiles setups) moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

Per-area files, NDJSON, and text logs under `STATE_DIR` survive the wipe on purpose. They are the debugging and eval record.

### Step 2: Prepare Per-Model Directories

Each opencode process runs with `--dir` pointed at its own directory under `STATE_DIR`.

```bash
PROMPT_FILE="$STATE_DIR/review-prompt.txt"
OPENAI_DIR="$STATE_DIR/dir-openai"
GEMINI_DIR="$STATE_DIR/dir-gemini"
CLAUDE_DIR="$STATE_DIR/dir-claude"
mkdir -p "$OPENAI_DIR" "$GEMINI_DIR" "$CLAUDE_DIR"

# Serena resolves the project by walking up from the run directory. Confirm the walk lands on the repo.
(cd "$OPENAI_DIR" && git rev-parse --show-toplevel)

echo "PROMPT_FILE=$PROMPT_FILE"
echo "OPENAI_DIR=$OPENAI_DIR"
echo "GEMINI_DIR=$GEMINI_DIR"
echo "CLAUDE_DIR=$CLAUDE_DIR"
```

The directories sit inside the repo on purpose. Serena is configured with `--project-from-cwd`, which walks up from the run directory looking for `.serena/project.yml` or `.git`. `STATE_DIR` is under `PROJECT_ROOT`, so the walk reaches the repo and activates the target project. A `mktemp -d` directory under `/var/folders` has no such ancestor, so serena would activate nothing and every symbolic tool would return empty. That is why this skill no longer uses temp directories.

The three directories are separate so the opencode processes do not contend on session state.

Nothing is packed, so there is no `repomix.xml`, no `attach_packed_output`, and no `outputId` to thread through the prompts.

### Step 3: Construct the Orchestrator Prompt

Build the prompt that each opencode process will execute. Replace `<TARGET_PATH>`, `<TARGET_NAME>`, `<PROJECT_ROOT>`, and `<STATE_DIR>` with the resolved values.

````text
PROMPT="You are a code review orchestrator running headless in a non-interactive session. There is no user present. Do not ask questions. Do not prompt for confirmation.

You have 3 steps. You are NOT done until the file is written and verified in Step 3.
Stopping before Step 3 is a failure. Do not print any completion markers until Step 3.

OUTPUT RULES: Keep interactive text responses to one short sentence. Your primary job is making tool calls and writing to files.

TARGET_PATH: <TARGET_PATH>
TARGET_NAME: <TARGET_NAME>
PROJECT_ROOT: <PROJECT_ROOT>
STATE_DIR: <STATE_DIR>

CRITICAL: Do NOT call pack_codebase, repomix, or attach_packed_output. There is no packed snapshot. The reviewers read the live working tree.

MODEL_LABEL: Derive from your model identity (claude, openai, or gemini).
OUTPUT_FILE: <PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-\$MODEL_LABEL.md

# Step 1: Spawn review agents

Spawn ALL 9 review agents. Note: opencode executes task calls sequentially (known issue #14195), so agents will run one at a time regardless of how they are requested.

Use the agent name \`reviewer-<area>\` for each. Each agent prompt MUST include, verbatim:

  Review every file under <TARGET_PATH>. Serena has the project activated already.

  Navigate with serena's symbolic tools: get_symbols_overview to map a file,
  find_symbol to read a definition, find_referencing_symbols to find callers,
  find_declaration and find_implementations to resolve a usage, and
  search_for_pattern for anything symbols cannot reach. Read a whole file only
  when symbolic navigation cannot answer the question.

  Cite path:line from the live file on disk and name the enclosing function,
  method, or type. Confirm the line by opening it before you cite it. A finding
  without a verified path:line citation is not a finding. Drop it.

  Write your findings to OUTPUT_PATH.

- reviewer-security -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-security.md
- reviewer-architecture -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-architecture.md
- reviewer-solid -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-solid.md
- reviewer-correctness -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-correctness.md
- reviewer-testing -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-testing.md
- reviewer-ops -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-ops.md
- reviewer-performance -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-performance.md
- reviewer-quality -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-quality.md
- reviewer-data -> OUTPUT_PATH: <STATE_DIR>/\$MODEL_LABEL-data.md

Each agent writes its own per-area file. The agent definitions handle the review logic.

# Step 2: Assemble the review file

After all 9 agents return, assemble the per-area files into the final review file using bash:

\`\`\`bash
echo \"# Code Review: <TARGET_NAME>\" > OUTPUT_FILE
echo \"**Model**: MODEL_LABEL\" >> OUTPUT_FILE
echo \"\" >> OUTPUT_FILE
for area in security architecture solid correctness testing ops performance quality data; do
  cat \"<STATE_DIR>/\$MODEL_LABEL-\$area.md\" >> OUTPUT_FILE
  echo \"\" >> OUTPUT_FILE
done
\`\`\`

# Step 3: Verify

Run: ls -la 'OUTPUT_FILE'
Run: head -5 'OUTPUT_FILE'

Both commands must succeed. If the file does not exist or is empty, re-run the assembly step.
Do not exit without the file on disk.

Print exactly: REVIEW_COMPLETE"

````

### Step 4: Write Prompt to File

Write the prompt string to a file under `STATE_DIR`. This avoids shell interpolation issues with large prompts, and keeps the exact prompt on disk beside the run it produced.

```bash
cat > "$PROMPT_FILE" <<'PROMPT_EOF'
<the prompt from step 3>
PROMPT_EOF
wc -c "$PROMPT_FILE"
```

Step 2 already created the three run directories and printed their paths. Step 5 substitutes each one into a subagent prompt as a literal absolute path. A subagent runs in a fresh shell and inherits no variable from this one, so a template that passes `$PROMPT_FILE` through unexpanded hands `opencode run` an empty prompt and the model reviews nothing.

### Step 5: Launch 3 Agents in Parallel

Issue all 3 Agent calls **in a single tool block**.

The `Agent` tool carries no `run_in_background` parameter. Every subagent runs in the background and the harness notifies the orchestrator when one completes. Issuing the 3 calls in one block is what makes the model runs concurrent; issuing them in separate blocks serializes the dispatch.

The orchestrator does not poll. It ends its turn after dispatching and is re-invoked on each completion notification. Step 6 runs once all 3 have reported.

A subagent that launches a background Bash task behaves the same way. It returns an interim result as soon as the launch succeeds, then resumes when the task exits and reports again under the same task id. Expect two notifications per model, and treat the first as "launched" rather than "finished". The signal that a model is done is its second report, or a `review-<TARGET_NAME>-<label>.md` on disk.

Each subagent receives the same instruction template with its model-specific values substituted. The subagent's job is:

1. Launch the opencode process as a background Bash task (`run_in_background: true`)
2. Wait for that task to exit, then check the NDJSON for the terminal state
3. Report success/failure, cost, token count, and whether the output file exists

Poll only as a fallback, at `POLL_INTERVAL` seconds. `POLL_INTERVAL` defaults to 60. A nine-reviewer opencode run takes minutes, so a shorter interval only burns turns.

**Subagent prompt template**. Substitute `<LABEL>`, `<MODEL_ID>`, `<RUN_DIR>`, `<STATE_DIR>`, `<TARGET_NAME>`, `<PROJECT_ROOT>`, and `<PROMPT_FILE>`. `<RUN_DIR>` is that model's directory from Step 2, being `dir-openai`, `dir-gemini`, or `dir-claude`. Every one is a literal absolute path or string. Leave no `$VARIABLE` for the subagent's shell to expand.

```text
Launch and monitor an opencode code review process. Do not ask questions.

Run this command in the background:

STATE_DIR="<STATE_DIR>" && \
opencode run \
  --agent review-orchestrator \
  -m <MODEL_ID> \
  --format json \
  --print-logs \
  --log-level INFO \
  --dir "<RUN_DIR>" \
  --title "Review - <LABEL>" \
  "$(cat '<PROMPT_FILE>')" \
  > "$STATE_DIR/<LABEL>.ndjson" 2>"$STATE_DIR/<LABEL>.log"

Wait for that background task to exit. Check progress only as a fallback, no more often than every 60 seconds:
  grep -c '"type":"step_finish"' "$STATE_DIR/<LABEL>.ndjson"
  tail -1 "$STATE_DIR/<LABEL>.ndjson" | jq -r '.part.reason // empty'
  grep -c '"type":"error"' "$STATE_DIR/<LABEL>.ndjson"

The run is done when the background task exits, or when the last step_finish reason is "stop".

When done:

1. Check if <PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md exists.
2. If NOT, check for per-area files: ls "$STATE_DIR/<LABEL>-*.md"
3. If per-area files exist, assemble the final review file:
   echo "# Code Review: <TARGET_NAME>" > "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   echo "**Model**: <LABEL>" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   echo "" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   for area in security architecture solid correctness testing ops performance quality data; do
     cat "$STATE_DIR/<LABEL>-$area.md" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md" 2>/dev/null
     echo "" >> "<PROJECT_ROOT>/.llmtmp/review-<TARGET_NAME>-<LABEL>.md"
   done

Report:
- Whether the final review file exists (and whether fallback assembly was used)
- How many per-area files were found: ls "$STATE_DIR/<LABEL>-*.md" 2>/dev/null | wc -l
- Total cost: jq -s '[.[] | select(.type=="step_finish") | .part.cost] | add' "$STATE_DIR/<LABEL>.ndjson"
- Total tokens: grep '"type":"step_finish"' "$STATE_DIR/<LABEL>.ndjson" | tail -1 | jq '.part.tokens.total'
- Any errors from: grep '"type":"error"' "$STATE_DIR/<LABEL>.ndjson"
```

Launch all 3 subagent calls in a single parallel batch (openai, gemini, claude).

#### Output Streams

Each opencode process produces two output files:

- **`<label>.ndjson`** (stdout): Structured NDJSON events from `--format json`. Use for programmatic progress tracking (step counts, cost, tool calls, completion detection).
- **`<label>.log`** (stderr): Plain-text info-level logs from `--print-logs --log-level INFO`. Use for diagnosing startup failures, permission issues, MCP server errors, and plugin loading problems.

Log lines are structured text, one per line:

```text
INFO  2026-03-13T00:54:25 +4ms service=default directory=/private/tmp creating instance
```

### Step 6: Wait and Verify

The 3 subagents from Step 5 handle monitoring. Wait for all 3 to return. Each reports its model's success/failure, cost, tokens, and errors.

Then check what landed on disk. A subagent reporting success proves the opencode process exited, not that nine reviewers wrote anything.

```bash
for label in openai gemini claude; do
  f="$PROJECT_ROOT/.llmtmp/review-$TARGET_NAME-$label.md"
  echo "== $label =="
  if [ -s "$f" ]; then wc -c "$f"; else echo "MISSING OR EMPTY: $f"; fi
  echo "per-area files: $(ls "$STATE_DIR/$label-"*.md 2>/dev/null | wc -l)"
  echo "H2 headings:    $(grep -c '^## ' "$f" 2>/dev/null || echo 0)"
  echo "errors:         $(grep -c '"type":"error"' "$STATE_DIR/$label.ndjson" 2>/dev/null || echo 0)"
done
```

Each model should show 9 per-area files and 9 H2 headings. Treat an area as unreviewed for that model when its per-area file is missing, is empty, carries no H2, or carries an H2 with neither a finding line nor exactly `No findings.` Never record any of those as `No findings.`

Re-dispatch the affected model's subagent once. An area still uncovered after one re-dispatch is reported as `Not reviewed` in Step 8, naming the model and the reason.

Then check citation compliance. A finding whose first backticked field carries no `:line` is unusable, because nobody can confirm it without re-reading the whole file.

```bash
for label in openai gemini claude; do
  tot=$(cat "$STATE_DIR/$label-"*.md 2>/dev/null | grep -c '^- \*\*' || echo 0)
  cited=$(cat "$STATE_DIR/$label-"*.md 2>/dev/null | grep -oE '^- \*\*(High|Medium|Low)\*\* `[^`]+`' | grep -c ':[0-9]' || echo 0)
  echo "$label citations with path:line: $cited/$tot"
done
```

This is not hypothetical. Measured on 2026-09-21 against a repomix-packed input, openai cited `path:line` on 16 of 16 findings and claude on 5 of 28, emitting `` `index.html` `index.html` `` for the rest with the path duplicated into the symbol slot. The line numbers were available in the input. Re-dispatch any area whose ratio falls below 1, quoting the Citations rule back to the reviewer.

A reviewer that finished a verification step often writes a transitional sentence before its H2. Strip everything before the first `##` in a per-area file rather than re-dispatching for it. Measured on the sibling `review-diff` skill, that happened in 2, 2, and 5 of 8 responses across three identical runs, and the swing between identical runs is wider than the swing between wordings of the instruction telling reviewers not to. Prompt tuning does not fix it; stripping always does.

### Step 7: Report Results

Collect the reports from each subagent. Summarize per model:

- Success/failure (output file present or not)
- Total cost
- Total tokens
- Any errors

### Step 8: Synthesize Reviews

Scan each review file before reading it. A reviewer that quotes a secret produces a file a sensitive-data hook will block, and the orchestrator holds no way to ask for a bypass mid-read.

```bash
SCAN="$HOME/.config/dotfiles/scripts/canary-scan.sh"
if [ -x "$SCAN" ]; then
  for label in openai gemini claude; do
    f="$PROJECT_ROOT/.llmtmp/review-$TARGET_NAME-$label.md"
    [ -s "$f" ] && { echo "== $label =="; "$SCAN" "$f" || true; }
  done
fi
```

`canary-scan.sh` exits 0 with no output when the file is clean or the plugin is not installed, and exits 2 printing one `<ruleId> x<count>` line per rule when it hits. The `|| true` keeps a non-zero exit from ending the step; the output is the signal, not the status. On a hit, name what fired and tell the operator that re-invoking with `[allow-pii]` on their own prompt clears the block.

Read all successfully produced review files (`.llmtmp/review-<TARGET_NAME>-*.md`). Compare findings across models and report:

1. **Quorum findings (3/3)** — issues flagged by all three models. List each with the area, severity, and finding.
2. **Quorum findings (2/3)** — issues flagged by two models. List each with the area, severity, which models agreed, and which did not.
3. **Single-model findings** — issues flagged by only one model. List all of them. Note which model raised each.
4. **Conflicting assessments** — areas where models disagree (e.g., one flags a risk, another says it's fine).

5. **Coverage gaps**. List every area Step 6 marked `Not reviewed`, with the model and the reason. A quorum count is only meaningful against the models that actually covered that area, so say which ones did.

Include every finding. Do not skip or summarize away any items.

## Expected Output Files

3 files total, one per model:

- `.llmtmp/review-<TARGET_NAME>-openai.md`
- `.llmtmp/review-<TARGET_NAME>-gemini.md`
- `.llmtmp/review-<TARGET_NAME>-claude.md`

Where `<TARGET_NAME>` is derived from the path's last segment (or `repo` for root).

`.llmtmp/review-deep/` holds the run record and is never wiped:

- `dir-openai/`, `dir-gemini/`, `dir-claude/`, the per-model opencode run directories
- `review-prompt.txt`, the exact orchestrator prompt the three models received
- `<label>-<area>.md`, 27 per-area reviewer files (3 models by 9 areas)
- `<label>.ndjson` and `<label>.log`, one pair per model

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
```

**text** - Model emitted text output.

```json
{
  "type": "text",
  "timestamp": 1773360682061,
  "sessionID": "ses_...",
  "part": { "type": "text", "text": "some output" }
}
```

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
```

For subagent spawns, `tool` is "task" and `state.output` contains the agent's result text:

```json
{"type":"tool_use","timestamp":...,"part":{"tool":"task","state":{"status":"completed","input":{"description":"...","prompt":"..."},"output":"<task_result>...</task_result>"}}}
```

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
```

The final `step_finish` with `"reason":"stop"` means the model is done.

**error** - An error occurred at the session level.

```json
{"type":"error","timestamp":...,"sessionID":"ses_...","error":{"name":"UnknownError","data":{"message":"Model not found: ..."}}}
```

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
```

Replace `$LOGFILE` with the text log path (e.g., `<PROJECT_ROOT>/.llmtmp/review-deep/openai.log`):

```bash
# All errors and warnings from text logs
grep -E "^(ERROR|WARN)" "$LOGFILE"
```

## Rules

- The invoking agent is a launcher and synthesizer. All review work happens inside the opencode processes. The invoking agent reads the finished review files and synthesizes a cross-model comparison.
- Do NOT perform any review analysis during Steps 1-7. Only analyze review outputs in Step 8.
- Do NOT ask questions during execution. This is non-interactive.
- Launch all 3 subagents in a single parallel batch. NEVER launch sequentially. The `Agent` tool has no `run_in_background` parameter; subagents always background and the harness notifies on completion.
- Point `--dir` at a directory inside the repo. Serena resolves the project by walking up from it, so a temp directory outside the repo leaves the reviewers with no navigation.
- Substitute every `<PLACEHOLDER>` in the Step 5 template with a literal value before dispatching. A subagent shell inherits no variable from the orchestrator's shell, so an unexpanded `$VAR` arrives empty.
- Verify per-area files in Step 6. A subagent reporting success proves only that the opencode process exited.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the context7 MCP server.
- NEVER wrap `opencode run` in `timeout`. It hangs before creating a session and writes zero bytes. Background it and poll the PID instead.
- Pass `--agent review-orchestrator` on every arm. Without it the gemini arm fails on the `researcher` tool schemas.
- Do NOT clean up per-area files, NDJSON logs, or text logs. All intermediate artifacts persist for debugging and evals.
- If a model fails, still wait for and report the others.
