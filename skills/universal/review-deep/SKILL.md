---
name: review-deep
description: Whole-codebase deep audit running 27 parallel reviewers across OpenAI, Gemini, and Claude via opencode run, navigating the live tree with Serena, plus one ocr scan coverage pass.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🕵️‍♂️

# Code Review Command

Review a codebase from 9 perspectives against 3 models at once. Every reviewer is its own `opencode run` process, so all 27 run concurrently. Each one navigates the live working tree with Serena and writes its own findings file.

Nothing is packed. There is no orchestrator process and no `task` fan-out. A reviewer reads the code as it sits on disk, so a citation points at a real line in a real file.

One `ocr scan` runs alongside them. It reviews every reviewable file in its own conversation, so it covers the whole repo and sees nothing that spans two files. The reviewers see across files and choose what to read. Each covers the other's blind spot.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise review the whole repo.

## Models

| Label  | Model ID                   |
| ------ | -------------------------- |
| openai | openai/gpt-6-sol           |
| gemini | google/gemini-3.8-flash    |
| claude | az-anthropic/claude-opus-5-5 |

The ocr coverage pass uses the provider and model in `~/.opencodereview/config.json`.

Every ID must exist in `configs/opencode/opencode.json` under the matching provider and in that provider's `whitelist`. An ID missing from either fails that arm with `Model not found`, which surfaces only as an `error` event in the NDJSON.

```bash
jq -r '.provider | to_entries[] | .key as $p | .value.models | keys[] | "\($p)/\(.)"' ~/.config/opencode/opencode.json
```

The gemini arm runs a Flash model on purpose. Google publishes no pro above `gemini-3.1-pro-preview`, so the newest Google model available is `gemini-3.8-flash`, seven minor versions ahead of the newest pro. Measured on one security review of a 1070-file repo, flash returned 11 findings against pro's 6 on the same agent and prompt, at roughly twice the tokens. That is a single comparison, not a benchmark.

## The rule that cost two days to learn

Redirect stdin from `/dev/null` on every `opencode run`. Without it the process blocks before creating a session, writes zero bytes, logs nothing past `message=init`, and exits only when something kills it. `opencode run` reads stdin to EOF before it does anything else, so any launcher that leaves stdin open hangs it, and a background job, a CI step, and an agent harness all do. This is anomalyco/opencode issue #38723, open against 1.18.25 and reproduced here on 1.18.20.

The hang looks intermittent and is not. Whether the launcher closes stdin decides it. Three reporters measured it deterministically across macOS arm64, Linux aarch64, and Windows, 5 of 5 hangs without the redirect against 5 to 10 of 10 successes with it.

An earlier version of this file banned wrapping `opencode run` in `timeout` and blamed a 44 percent failure rate on the wrapper. That was wrong. The stall reproduces with no `timeout` anywhere, and upstream's own reproduction script uses `timeout 120`. Removing every bound is what turned a one-line stdin bug into a multi-day investigation, so Step 2b now checks each reviewer for a session row.

Impose no token cap and no turn cap on a reviewer. A review of a large repo takes as long as it takes.

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
find "$STATE_DIR" -maxdepth 1 \( -name 'ocr-scan.*' -o -name 'ledger.txt' -o -name 'opened.txt' \) -delete

SCOPE=""
[ "$TARGET_PATH" != "$PROJECT_ROOT" ] && SCOPE="--path ${TARGET_PATH#"$PROJECT_ROOT"/}"
ocr scan --preview --format json --repo "$PROJECT_ROOT" $SCOPE 2>/dev/null \
  | jq -r '.files[] | select(.will_review) | .path' > "$STATE_DIR/ledger.txt"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "TARGET_PATH=$TARGET_PATH"
echo "TARGET_NAME=$TARGET_NAME"
echo "STATE_DIR=$STATE_DIR"
echo "LEDGER=$(wc -l < "$STATE_DIR/ledger.txt" | tr -d ' ') files"
```

`ocr scan --preview` lists every reviewable file without calling a model. `ledger.txt` is the list each reviewer must cover and the denominator for coverage in Step 3.

`find -delete` rather than `rm -f`. A `safe-rm` shim on `PATH` moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

### Step 2: Dispatch 27 Reviewers and the Coverage Pass

One bash block launches all 27 reviewers and the ocr scan, then waits. Substitute the values Step 1 printed.

```bash
AREAS="security architecture solid correctness testing ops performance quality data"
MODELS="openai:openai/gpt-6-sol gemini:google/gemini-3.8-flash claude:az-anthropic/claude-opus-5-5"
SCOPE=""
[ "$TARGET_PATH" != "$PROJECT_ROOT" ] && SCOPE="--path ${TARGET_PATH#"$PROJECT_ROOT"/}"
PIDS=""

ocr scan --audience agent --repo "$PROJECT_ROOT" $SCOPE --max-tokens 1000000 \
  --format json --output "$STATE_DIR/ocr-scan.json" \
  < /dev/null > /dev/null 2> "$STATE_DIR/ocr-scan.log" &
PIDS="$PIDS $!"

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
or type. A line you saw counts as verified, and find_symbol returns a symbol's
line range. When you cannot verify the exact line, cite the nearest line you
saw and end the finding with `line unconfirmed`. Never drop a real defect
because its line number is uncertain.

LEDGER_PATH: $STATE_DIR/ledger.txt

LEDGER_PATH lists the reviewable source files, one path per line. Read it
first and cover every file it lists.

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
      < /dev/null \
      > "$STATE_DIR/raw-$label-$area.ndjson" 2>"$STATE_DIR/$label-$area.log" &
    PIDS="$PIDS $!"
  done
done

echo "launched $(echo $PIDS | wc -w | tr -d ' ') processes, 27 reviewers and 1 ocr scan"

wait

echo "done, $(ls "$STATE_DIR"/*-*.md 2>/dev/null | wc -l | tr -d ' ') files written"
```

Expect wall time close to the slowest single reviewer rather than the sum. Measured on a 22-file TypeScript repo, one reviewer took 148 seconds.

A reviewer writes its own file with `apply_patch`. The reviewer agents grant it and deny `bash`, `webfetch`, `context7_*`, `repomix_*`, `researcher_*`, and Serena's four write families. They run as `mode: primary`, because opencode ignores a subagent's `tools` block when the agent is selected with `--agent`.

A reviewer must not call `task`. Two of 27 reviewers on a 1070-file repo spawned a subagent that never returned, and `TaskTool` runs a foreground subagent with a blocking `yield`, so the parent hung and Step 2's `wait` hung with it. The agents set `tools.task: false` and `permission.task: {"*": deny}`. After the fix both reviewers completed with zero `task` calls.

Nothing guards against two runs at once. Step 2 writes to fixed paths with no lock, so a second invocation against the same repo interleaves into the same NDJSON and overwrites the same output file. That corrupted two attempts on 2026-09-22. Check for an in-flight run before dispatching.

Provider limits are not the constraint. OpenAI reports 40,000,000 tokens per minute and Azure Foundry 15,000,000.

### Step 2b: Confirm Every Reviewer Started

Run this as a separate foreground call while Step 2 is still waiting. A reviewer that never created a session produced nothing and never will.

```bash
sleep 30
DB="$HOME/.local/share/opencode/opencode.db"
for label in openai gemini claude; do
  for area in security architecture solid correctness testing ops performance quality data; do
    n=$(sqlite3 -readonly "$DB" "SELECT count(*) FROM session WHERE title='Review $label $area';")
    [ "$n" -eq 0 ] && echo "NO SESSION $label $area"
  done
done
echo "checked 27"
```

A healthy reviewer writes its session row within about 3 seconds of launch. Kill and relaunch any reviewer named here rather than letting it sit. One stalled run held for 55 minutes at zero bytes on 2026-09-22 before anyone looked.

### Step 3: Verify

An arm sometimes returns its findings as its response instead of writing OUTPUT_PATH. `gpt-6-sol` does this. The findings are in the NDJSON, so copy them out before verifying.

```bash
for f in "$STATE_DIR"/raw-*.ndjson; do
  b=$(basename "$f" .ndjson); out="$STATE_DIR/${b#raw-}.md"
  [ -s "$out" ] && continue
  jq -r 'select(.type=="text") | .part.text' "$f" | awk '/^## /{p=1} p' > "$out"
done
```

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
      unconf=$(grep -c 'line unconfirmed' "$f")
      echo "  $area ok findings=$n cited=$cited unconfirmed=$unconf"
    fi
  done
done
```

Then measure coverage as files opened, not files cited. A file opened and not cited was read and found clean.

```bash
jq -r 'select(.type=="tool_use") | .part.state.input | (.filePath // .relative_path // .path // empty)' \
  "$STATE_DIR"/raw-*.ndjson 2>/dev/null | sed "s|^$PROJECT_ROOT/||" | sort -u > "$STATE_DIR/opened.txt"
echo "ledger files opened=$(comm -12 <(sort "$STATE_DIR/ledger.txt") "$STATE_DIR/opened.txt" | wc -l | tr -d ' ') of $(wc -l < "$STATE_DIR/ledger.txt" | tr -d ' ')"
comm -23 <(sort "$STATE_DIR/ledger.txt") "$STATE_DIR/opened.txt" | sed 's/^/  never opened: /'
jq -r '"ocr status=\(.status) files=\(.summary.files_reviewed) findings=\(.comments|length)"' "$STATE_DIR/ocr-scan.json"
```

Treat an area as unreviewed when its file is missing, is empty, has no H2, or has an H2 with neither a finding line nor exactly `No findings.` Never record any of those as `No findings.`

Re-dispatch that one reviewer, which is a single `opencode run`. An area still uncovered after one retry is reported as `Not reviewed` in Step 4, naming the model and the reason.

A reviewer sometimes writes a transitional sentence before its H2. Strip everything before the first `##` rather than re-dispatching for it. Prompt tuning does not fix that; stripping always does.

Compare `cited` against `findings`. A finding whose first backticked field carries no `:line` is unusable, because nobody can confirm it without re-reading the whole file. Measured on 2026-09-21, openai cited 16 of 16 findings and claude 5 of 28.

`cited` counts a finding carrying a `path:line` whether or not the reviewer ended it with `line unconfirmed`. The citation sits at the front of the line and the marker sits at the end, so the two never exclude each other. Subtract `unconfirmed` from `cited` for the count the reviewer stands behind. Measured on the gemini security probe of 2026-09-22, 38 findings were cited and 0 carried the marker.

A gap is not automatically a defect now that a reviewer may mark a finding `line unconfirmed` rather than discard it. Read the uncited findings before re-dispatching. Re-dispatch when they carry no symbol either.

The instruction to drop an unverified finding was removed on 2026-09-22. Measured on gemini against one area, it cost 6 findings to keep: 1 with the clause, 6 without, including six path-traversal defects the suppressed run investigated and never reported. Removing the Ownership table instead recovered only 1, so that table stays.

### Step 4: Scan and Synthesize

Scan each file before reading it. A reviewer that quotes a secret produces a file a sensitive-data hook will block, and there is no way to ask for a bypass mid-read.

```bash
SCAN="$HOME/.config/dotfiles/scripts/canary-scan.sh"
if [ -x "$SCAN" ]; then
  for f in "$STATE_DIR"/*-*.md "$STATE_DIR/ocr-scan.json"; do
    [ -s "$f" ] && { echo "== $(basename "$f") =="; "$SCAN" "$f" || true; }
  done
fi
```

`canary-scan.sh` exits 0 with no output when the file is clean or the plugin is absent, and exits 2 printing one `<ruleId> x<count>` line per rule when it hits. The `|| true` keeps a non-zero exit from ending the step. On a hit, name what fired and tell the operator that re-invoking with `[allow-pii]` on their own prompt clears the block.

Then read the 27 files and `ocr-scan.json` and compare across models. ocr's comments carry `path`, `start_line`, `severity`, and `category`, and count as a fourth source when two sightings agree.

1. Quorum findings, 3 of 3. Issues flagged by all three models, each with area, severity, and finding.
2. Quorum findings, 2 of 3. Name which two agreed and which did not.
3. Single-model findings. List all of them and note which model raised each.
4. Conflicting assessments. Areas where models disagree, such as one flagging a risk another calls fine.
5. Coverage gaps. Every area Step 3 marked `Not reviewed`, with the model and the reason. A quorum count is only meaningful against the models that covered that area. Name every ledger file no reviewer opened. ocr's findings are the only review those files got.

Include every finding. Do not skip or summarize away any items.

## Expected Output Files

`.llmtmp/review-deep/` holds the whole run and is wiped at the start of the next one:

- `<label>-<area>.md`, 27 per-area findings files
- `ocr-scan.json` and `ocr-scan.log`, the coverage pass
- `ledger.txt`, the reviewable files, and `opened.txt`, the files reviewers opened
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
- ALWAYS redirect stdin from `/dev/null` on `opencode run`. Omitting it hangs the process before session creation with no output and no error, which is anomalyco/opencode issue #38723.
- Impose no token cap and no turn cap on a reviewer. Let it finish.
- Run Step 2b about 30 seconds after dispatch. A reviewer with no session row is dead and needs relaunching, and wall time cannot tell that apart from a slow review.
- Run the Step 2 block as a background Bash call. `wait` blocks until all 27 exit, and backgrounding keeps that out of the main session.
- Launch all 27 reviewers and the ocr scan in one bash block. They are independent processes.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the context7 MCP server.
- Do NOT clean up per-area files, NDJSON, or logs during a run. Step 1 wipes them at the start of the next one.
- If a reviewer fails, still wait for and report the others.
- Reviewer agents live in `configs/opencode/agents/` and are glob-linked by `./install`. A machine that has not run install since they changed fails with an unknown agent.
