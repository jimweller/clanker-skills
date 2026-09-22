---
name: review-deep
description: Whole-codebase deep audit running 27 parallel reviewers across OpenAI, Gemini, and Claude via opencode run, navigating the live tree with Serena.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🕵️‍♂️

# Code Review Command

Review a codebase from 9 perspectives against 3 models at once. Every reviewer is its own `opencode run` process, so all 27 run concurrently. Each one navigates the live working tree with Serena and writes its own findings file.

Nothing is packed. There is no orchestrator process and no `task` fan-out. A reviewer reads the code as it sits on disk, so a citation points at a real line in a real file.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise review the whole repo.

## Models

| Label  | Model ID                   |
| ------ | -------------------------- |
| openai | openai/gpt-5.6-sol         |
| gemini | google/gemini-pro-latest   |
| claude | az-anthropic/claude-opus-5 |

Every ID must exist in `configs/opencode/opencode.json` under the matching provider and in that provider's `whitelist`. An ID missing from either fails that arm with `Model not found`, which surfaces only as an `error` event in the NDJSON.

```bash
jq -r '.provider | to_entries[] | .key as $p | .value.models | keys[] | "\($p)/\(.)"' ~/.config/opencode/opencode.json
```

`gemini-pro-latest` is an alias. On 2026-09-22 it resolved to `gemini-3.1-pro-preview`, confirmed by the `modelVersion` field in the API response. Google re-points it when a newer pro ships, so the arm can change behavior without a commit here.

## Two rules that cost a day to learn

Never wrap `opencode run` in `timeout`. It hangs before creating a session and writes zero bytes, and `timeout --foreground` does not help. Measured with coreutils 9.11 across two alternating rounds, unwrapped returned 1053 bytes both times and wrapped returned 0 both times. A `timeout` wrapper in a diagnostic harness once produced a 44 percent apparent failure rate across 69 runs that had nothing to do with opencode.

Background the processes and `wait`, as Step 2 does. Impose no timeout, no poll interval, no token cap, and no turn cap on a reviewer. A review of a large repo takes as long as it takes, and every ceiling tried so far killed work that was about to finish.

Serena must be enabled in `~/.config/opencode/opencode.json` and started with `--project-from-cwd`. It is the only navigation the reviewers have. `--dir` points at the target so Serena's walk finds the project.

### Why researcher is disabled

`configs/opencode/opencode.json` sets `"enabled": false` on the `researcher` MCP server, and the reviewer agents disable its tools again. Google rejects its schemas.

`researcher` declares optional arrays as the union type `["null","array"]`, which is valid JSON Schema. Anthropic and OpenAI accept it. Google converts JSON Schema into its own OpenAPI-subset proto, turns the union into `any_of`, drops `items` from the array branch, then rejects its own output with `any_of[0].items: missing field`. The gemini arm fails in 5 seconds with one `error` event and 5712 bytes of NDJSON.

Any MCP server using that pattern breaks a Google arm the same way. If a gemini arm starts failing with `field predicate failed: $type == Type.ARRAY`, find the server owning the named properties and disable it.

## Procedure

### Step 1: Resolve Target and Prepare

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_ROOT=$(cd -P "$PROJECT_ROOT" && pwd -P)
TARGET_PATH="<user-provided path or empty>"
[ -z "$TARGET_PATH" ] && TARGET_PATH="$PROJECT_ROOT"

TARGET_PATH=$(cd -P "$TARGET_PATH" 2>/dev/null && pwd -P) || { echo "TARGET_PATH does not exist"; exit 1; }
case "$TARGET_PATH" in
  "$PROJECT_ROOT"|"$PROJECT_ROOT"/*) ;;
  *) echo "TARGET_PATH escapes PROJECT_ROOT"; exit 1 ;;
esac

TARGET_NAME=$(basename "$TARGET_PATH")
[ "$TARGET_PATH" = "$PROJECT_ROOT" ] && TARGET_NAME="repo"

STATE_DIR="$PROJECT_ROOT/.llmtmp/review-deep"
mkdir -p "$STATE_DIR"

find "$STATE_DIR" -maxdepth 1 -name '*.md' -delete
find "$STATE_DIR" -maxdepth 1 -name 'raw-*.ndjson' -delete

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "TARGET_PATH=$TARGET_PATH"
echo "TARGET_NAME=$TARGET_NAME"
echo "STATE_DIR=$STATE_DIR"
```

`find -delete` rather than `rm -f`. A `safe-rm` shim on `PATH` moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

### Step 2: Dispatch 27 Reviewers

One bash block launches all 27 and waits. Substitute the values Step 1 printed.

```bash
AREAS="security architecture solid correctness testing ops performance quality data"
MODELS="openai:openai/gpt-5.6-sol gemini:google/gemini-pro-latest claude:az-anthropic/claude-opus-5"
PIDS=""

for entry in $MODELS; do
  label="${entry%%:*}"
  model="${entry#*:}"
  for area in $AREAS; do
    out="$STATE_DIR/$label-$area.md"
    prompt="Review every file under $TARGET_PATH.

Navigate with serena symbolic tools: get_symbols_overview to map a file,
find_symbol to read a definition, find_referencing_symbols to find callers,
find_declaration and find_implementations to resolve a usage. Read a whole
file only when symbolic navigation cannot answer the question.

Cite path:line from the live file and name the enclosing function, method,
or type. Confirm the line by opening it before citing it. A finding without
a verified path:line citation is not a finding. Drop it.

OUTPUT_PATH: $out

Write your findings to OUTPUT_PATH. Writing that file is mandatory and is
how your work is delivered. Do not return findings as your response."

    opencode run \
      --agent "reviewer-$area" \
      -m "$model" \
      --format json \
      --dir "$TARGET_PATH" \
      --title "Review $label $area" \
      "$prompt" \
      > "$STATE_DIR/raw-$label-$area.ndjson" 2>"$STATE_DIR/$label-$area.log" &
    PIDS="$PIDS $!"
  done
done

echo "launched $(echo $PIDS | wc -w | tr -d ' ') reviewers"

wait

echo "done, $(ls "$STATE_DIR"/*-*.md 2>/dev/null | wc -l | tr -d ' ') files written"
```

Expect wall time close to the slowest single reviewer rather than the sum. Measured on a 22-file TypeScript repo, one reviewer took 148 seconds.

A reviewer writes its own file with `apply_patch`. opencode has no tool named `write`, so a `write: true` in an agent definition matches nothing. The reviewer agents grant `apply_patch` and deny `bash`, `webfetch`, `context7_*`, `repomix_*`, `researcher_*`, and Serena's four write families. They run as `mode: primary`, because opencode ignores a subagent's `tools` block when the agent is selected with `--agent`.

Provider limits are not the constraint. OpenAI reports 40,000,000 tokens per minute and Azure Foundry 15,000,000.

### Step 3: Verify

```bash
for label in openai gemini claude; do
  echo "== $label =="
  for area in security architecture solid correctness testing ops performance quality data; do
    f="$STATE_DIR/$label-$area.md"
    if [ ! -s "$f" ]; then
      echo "  $area MISSING errors=$(grep -c '\"type\":\"error\"' "$STATE_DIR/raw-$label-$area.ndjson" 2>/dev/null)"
    else
      n=$(grep -c '^- \*\*' "$f")
      cited=$(grep -oE '^- \*\*(High|Medium|Low)\*\* `[^`]+`' "$f" | grep -c ':[0-9]')
      echo "  $area ok findings=$n cited=$cited"
    fi
  done
done
```

Treat an area as unreviewed when its file is missing, is empty, has no H2, or has an H2 with neither a finding line nor exactly `No findings.` Never record any of those as `No findings.`

Re-dispatch that one reviewer, which is a single `opencode run`. An area still uncovered after one retry is reported as `Not reviewed` in Step 4, naming the model and the reason.

A reviewer sometimes writes a transitional sentence before its H2. Strip everything before the first `##` rather than re-dispatching for it. Prompt tuning does not fix that; stripping always does.

Compare `cited` against `findings`. A finding whose first backticked field carries no `:line` is unusable, because nobody can confirm it without re-reading the whole file. Measured on 2026-09-21, openai cited 16 of 16 findings and claude 5 of 28. Re-dispatch any area with a gap.

### Step 4: Scan and Synthesize

Scan each file before reading it. A reviewer that quotes a secret produces a file a sensitive-data hook will block, and there is no way to ask for a bypass mid-read.

```bash
SCAN="$HOME/.config/dotfiles/scripts/canary-scan.sh"
if [ -x "$SCAN" ]; then
  for f in "$STATE_DIR"/*-*.md; do
    [ -s "$f" ] && { echo "== $(basename "$f") =="; "$SCAN" "$f" || true; }
  done
fi
```

`canary-scan.sh` exits 0 with no output when the file is clean or the plugin is absent, and exits 2 printing one `<ruleId> x<count>` line per rule when it hits. The `|| true` keeps a non-zero exit from ending the step. On a hit, name what fired and tell the operator that re-invoking with `[allow-pii]` on their own prompt clears the block.

Then read the 27 files and compare across models:

1. Quorum findings, 3 of 3. Issues flagged by all three models, each with area, severity, and finding.
2. Quorum findings, 2 of 3. Name which two agreed and which did not.
3. Single-model findings. List all of them and note which model raised each.
4. Conflicting assessments. Areas where models disagree, such as one flagging a risk another calls fine.
5. Coverage gaps. Every area Step 3 marked `Not reviewed`, with the model and the reason. A quorum count is only meaningful against the models that covered that area.

Include every finding. Do not skip or summarize away any items.

## Expected Output Files

`.llmtmp/review-deep/` holds the whole run and is wiped at the start of the next one:

- `<label>-<area>.md`, 27 per-area findings files
- `raw-<label>-<area>.ndjson`, the full event stream per reviewer
- `<label>-<area>.log`, stderr per reviewer

## NDJSON Reference

One JSON object per line. Skip lines that fail to parse.

| Type | Meaning | Key fields |
| ---- | ------- | ---------- |
| `step_start` | An LLM turn begins | |
| `text` | Model emitted text | `part.text` |
| `tool_use` | Model called a tool | `part.tool`, `part.state.status`, `part.state.input` |
| `step_finish` | A turn completed | `part.reason`, `part.cost`, `part.tokens` |
| `error` | Session-level error | `error.data.message` |

A `step_finish` reason of `stop` means done and `tool-calls` means continuing.

```bash
jq -s '[.[] | select(.type=="step_finish") | .part.cost] | add' "$NDJSON"
tac "$NDJSON" | jq -s 'first(.[] | select(.type=="step_finish")) | .part.tokens.total'
jq -r 'select(.type=="tool_use") | .part.tool' "$NDJSON" | sort | uniq -c | sort -rn
jq -r 'select(.type=="error") | .error.data.message' "$NDJSON"
```

Serena carried 119 of 181 tool calls on a TypeScript repo and 2 of 28 on a repo of HTML, CSS, and a Dockerfile. Symbolic navigation is worth little where no language server backs the files.

## Rules

- The invoking agent is a launcher and a synthesizer. It performs no review analysis of its own. Only Step 4 analyzes.
- NEVER wrap `opencode run` in `timeout`. Background the processes and `wait`.
- Impose no timeout, no poll loop, no token cap, and no turn cap on a reviewer. Let it finish.
- Run the Step 2 block as a background Bash call. `wait` blocks until all 27 exit, and backgrounding keeps that out of the main session.
- Launch all 27 in one bash block. They are independent processes.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the context7 MCP server.
- Do NOT clean up per-area files, NDJSON, or logs during a run. Step 1 wipes them at the start of the next one.
- If a reviewer fails, still wait for and report the others.
- Reviewer agents live in `configs/opencode/agents/` and are glob-linked by `./install`. A machine that has not run install since they changed fails with an unknown agent.
