---
name: review-deep
description: Whole-codebase deep audit. Partitions the repo into 25-file components, runs 9 perspectives by 3 models (OpenAI, Gemini, Claude) on every component via opencode run with Serena navigation, sweeps for gaps, and runs one ocr scan coverage pass. Then collates and deduplicates the findings and verifies every Critical and High issue against a clean export of the reviewed commit with isolated claude -p judges. The run directory feeds the review-tickets skill.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🕵️‍♂️

# Code Review Command

Review a codebase from 9 perspectives against 3 models. The repo is cut into components of at most 25 files, and each of the 27 perspective and model pairs reviews every component, so every file gets all 27 reviews. Each arm is its own `opencode run` process that navigates the whole live tree with Serena and writes its own findings. A sweep per pair then looks for defects the component boundaries hid.

Nothing is packed. There is no orchestrator process and no `task` fan-out. A reviewer reads the code as it sits on disk, so a citation points at a real line in a real file.

One `ocr scan` runs alongside them. It reviews every reviewable file in its own conversation with a generic checklist, which makes it an independent fourth source.

## Arguments

If the user provided a path with the invocation, treat it as the target directory relative to the repo root. Otherwise review the whole repo.

## Models

| Label  | Model ID                     | Variant |
| ------ | ---------------------------- | ------- |
| openai | openai/gpt-6-sol             |         |
| gemini | google/gemini-3.8-flash      |         |
| claude | az-anthropic/claude-opus-5-5 | xhigh   |

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
find "$STATE_DIR" -mindepth 1 -delete
mkdir -p "$STATE_DIR/components" "$STATE_DIR/coverage" "$STATE_DIR/parts"

SCOPE=""
[ "$TARGET_PATH" != "$PROJECT_ROOT" ] && SCOPE="--path ${TARGET_PATH#"$PROJECT_ROOT"/}"
ocr scan --preview --format json --repo "$PROJECT_ROOT" $SCOPE 2>/dev/null > "$STATE_DIR/ocr-preview.json"
jq -r '.files[] | select(.will_review) | .path' "$STATE_DIR/ocr-preview.json" > "$STATE_DIR/ledger.txt"
jq -r '.files[] | select(.will_review | not) | "\(.path)\t\(.exclude_reason)"' "$STATE_DIR/ocr-preview.json" > "$STATE_DIR/skipped.txt"

python3 - "$STATE_DIR" <<'PY'
import os, sys
from collections import OrderedDict
d, SIZE = sys.argv[1], 25
paths = sorted(l.strip() for l in open(f"{d}/ledger.txt") if l.strip())
def split(ps, depth):
    if len(ps) <= SIZE:
        return [ps]
    groups = OrderedDict()
    for p in ps:
        parts = p.split("/")
        groups.setdefault(parts[depth] if depth < len(parts) - 1 else p, []).append(p)
    out, cur = [], []
    for g in groups.values():
        if len(g) > SIZE:
            if cur:
                out.append(cur); cur = []
            out.extend(split(g, depth + 1))
        elif len(cur) + len(g) <= SIZE:
            cur += g
        else:
            out.append(cur); cur = g
    if cur:
        out.append(cur)
    return out
comps = []
for c in split(paths, 0):
    if comps and len(comps[-1]) + len(c) <= SIZE:
        comps[-1] += c
    else:
        comps.append(c)
for i, c in enumerate(comps, 1):
    open(f"{d}/components/c{i:02d}.txt", "w").write("\n".join(c) + "\n")
print(f"COMPONENTS={len(comps)}")
PY

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "TARGET_PATH=$TARGET_PATH"
echo "TARGET_NAME=$TARGET_NAME"
echo "STATE_DIR=$STATE_DIR"
echo "LEDGER=$(wc -l < "$STATE_DIR/ledger.txt" | tr -d ' ') reviewable, $(wc -l < "$STATE_DIR/skipped.txt" | tr -d ' ') skipped"

S=<this skill's directory>/scripts
python3 "$S/init_run.py" "$PROJECT_ROOT" "$TARGET_PATH" "$STATE_DIR"
```

`init_run.py` records the reviewed commit, HEAD at this moment, and creates the run directory at `${XDG_CACHE_HOME:-~/.cache}/review-deep/<repo>-<commit12>`, outside the repository. It prints `RUN_DIR`, and Step 5 uses it. It warns when the working tree has uncommitted changes, because reviewers read the live tree while the Step 5 judges read the commit. Commit or stash first when the warning lists source files. `run.json` in the run directory holds the models, the concurrency, the files a judge must not see, and the commit sentence tickets carry. Edit it before Step 5 to change any of them.

`ocr scan --preview` lists every file without calling a model. `ledger.txt` holds the reviewable ones. `skipped.txt` holds the rest with ocr's reason, such as `binary` or `unsupported_ext`, and Step 5 reports it as the skipped ledger.

The partition cuts the ledger into components of at most 25 files along directory lines, the size Anthropic's Claude Security scanner uses. A reviewer given the whole repo stops after 40 to 50 files by its own choice. Given a component, it reviews every file. A 41-file repo yields 1 component and a 414-file repo yields 22.

`find -delete` rather than `rm -f`. A `safe-rm` shim on `PATH` moves paths to Trash and exits non-zero on a missing path even under `-f`, which breaks the wipe on a first run.

### Step 2: Dispatch Component Reviewers and the Coverage Pass

Each of the 27 area and model pairs reviews every component, so a run has 27 arms per component. A worker pool runs them `CONCURRENCY` at a time, beside one ocr scan. Substitute the values Step 1 printed.

```bash
export PROJECT_ROOT TARGET_PATH STATE_DIR
AREAS="security architecture solid correctness testing ops performance quality data"
MODELS="openai:openai/gpt-6-sol gemini:google/gemini-3.8-flash claude:az-anthropic/claude-opus-5-5"
CONCURRENCY=27

cat > "$STATE_DIR/arm.sh" <<'ARM'
#!/bin/bash
label=$1 model=$2 area=$3 comp=$4
VARIANT=""
[ "$label" = claude ] && VARIANT="--variant xhigh"
base="$label-$area-$comp"
if [ "$comp" = sweep ]; then
  scope="LEDGER_PATH: $STATE_DIR/ledger.txt
FINDINGS_PATH: $STATE_DIR/$label-$area.md

LEDGER_PATH lists every reviewable source file. A component-by-component
review already covered them, and its findings are in FINDINGS_PATH. Look only
for defects that are not already listed there, especially defects that span
components. Do not repeat a listed finding."
else
  scope="LEDGER_PATH: $STATE_DIR/components/$comp.txt
COVERAGE_PATH: $STATE_DIR/coverage/$base.txt

LEDGER_PATH lists the source files assigned to you, one path per line. Read it
first and review every file it lists. The rest of the repository is context:
follow calls into it, and report defects in the listed files.

For every path in LEDGER_PATH, write one line to COVERAGE_PATH: the path, then
reviewed or skipped, then a short reason. Every listed path must appear
exactly once before you finish."
fi
prompt="Review the source files under $TARGET_PATH that your ledger assigns.

Navigate with serena symbolic tools: get_symbols_overview to map a file,
find_symbol to read a definition, find_referencing_symbols to find callers,
find_declaration and find_implementations to resolve a usage. Read a whole
file only when symbolic navigation cannot answer the question.

Cite path:line from the live file and name the enclosing function, method,
or type. A line you saw counts as verified, and find_symbol returns a symbol's
line range. When you cannot verify the exact line, cite the nearest line you
saw and end the finding with \`line unconfirmed\`. Never drop a real defect
because its line number is uncertain.

$scope

OUTPUT_PATH: $STATE_DIR/parts/$base.md

Write your findings to OUTPUT_PATH. Writing that file is mandatory and is
how your work is delivered. Do not return findings as your response."
OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1 \
OPENCODE_CONFIG="$HOME/.config/opencode/reviewer.json" \
opencode run \
  --agent "reviewer-$area" \
  -m "$model" $VARIANT \
  --format json \
  --dir "$TARGET_PATH" \
  --title "Review $label $area $comp" \
  "$prompt" \
  < /dev/null \
  > "$STATE_DIR/parts/raw-$base.ndjson" 2> "$STATE_DIR/parts/$base.log"
ARM

: > "$STATE_DIR/tasks.txt"
for comp in $(ls "$STATE_DIR/components" | sed 's/\.txt$//'); do
  for entry in $MODELS; do
    for area in $AREAS; do
      echo "${entry%%:*} ${entry#*:} $area $comp" >> "$STATE_DIR/tasks.txt"
    done
  done
done

SCOPE=""
[ "$TARGET_PATH" != "$PROJECT_ROOT" ] && SCOPE="--path ${TARGET_PATH#"$PROJECT_ROOT"/}"
ocr scan --audience agent --repo "$PROJECT_ROOT" $SCOPE --max-tokens 1000000 \
  --format json --output "$STATE_DIR/ocr-scan.json" \
  < /dev/null > /dev/null 2> "$STATE_DIR/ocr-scan.log" &

echo "dispatching $(wc -l < "$STATE_DIR/tasks.txt" | tr -d ' ') arms, $CONCURRENCY at a time, plus 1 ocr scan"
xargs -P "$CONCURRENCY" -L 1 bash "$STATE_DIR/arm.sh" < "$STATE_DIR/tasks.txt"
wait
echo "done, $(ls "$STATE_DIR"/parts/*.md 2>/dev/null | wc -l | tr -d ' ') part files written"
```

Expect wall time near the number of components times the slowest arm, since the pool runs one wave of 27 per component. A 41-file repo runs one wave. A 414-file repo runs 22.

`CONCURRENCY=27` holds 27 `opencode` processes at once, which a 48 GB machine carried without trouble. Each held 370 to 800 MB.

Reviewers run as an appliance. `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1` keeps the operator's global `~/.claude/CLAUDE.md` out of their prompt, which removes about 24,000 tokens per turn. `reviewer.json` layers Serena's manual on top of the global opencode config through `instructions`. A repo's own `CLAUDE.md` still loads.

A reviewer writes its own file with `apply_patch`. The reviewer agents grant it and deny `bash`, `webfetch`, `context7_*`, `repomix_*`, `researcher_*`, and Serena's four write families. They run as `mode: primary`, because opencode ignores a subagent's `tools` block when the agent is selected with `--agent`.

A reviewer must not call `task`. Two of 27 reviewers on a 1070-file repo spawned a subagent that never returned, and `TaskTool` runs a foreground subagent with a blocking `yield`, so the parent hung and Step 2's `wait` hung with it. The agents set `tools.task: false` and `permission.task: {"*": deny}`. After the fix both reviewers completed with zero `task` calls.

Nothing guards against two runs at once. Step 1 wipes `STATE_DIR` and every arm writes to fixed paths, so a second invocation against the same repo destroys the first. Check for an in-flight run before dispatching.

Provider limits are not the constraint. OpenAI reports 40,000,000 tokens per minute and Azure Foundry 15,000,000.

### Step 2b: Confirm Arms Start

Run this as a separate foreground call while Step 2 is still waiting. An arm that never created a session wrote nothing and never will, and it holds a pool slot.

```bash
find "$STATE_DIR/parts" -name 'raw-*.ndjson' -size 0 -mmin +1 | sed 's|.*/raw-||; s|\.ndjson$||; s/^/NO SESSION /'
```

A healthy arm writes NDJSON within seconds of launch. Kill any arm named here. Step 3 re-dispatches it.

### Step 3: Collect and Verify

An arm sometimes returns its findings as its response instead of writing OUTPUT_PATH. `gpt-6-sol` does this. The findings are in the NDJSON, so copy them out first. Then merge each area and model's parts into one file.

```bash
for f in "$STATE_DIR"/parts/raw-*.ndjson; do
  b=$(basename "$f" .ndjson); out="$STATE_DIR/parts/${b#raw-}.md"
  [ -s "$out" ] && continue
  jq -r 'select(.type=="text") | .part.text' "$f" | awk '/^## /{p=1} p' > "$out"
done

for label in openai gemini claude; do
  for area in security architecture solid correctness testing ops performance quality data; do
    out="$STATE_DIR/$label-$area.md"
    parts=$(ls "$STATE_DIR"/parts/"$label-$area"-c*.md 2>/dev/null)
    [ -z "$parts" ] && continue
    { grep -h -m1 '^## ' $parts | head -1; echo; grep -h '^- \*\*' $parts; } > "$out"
    grep -q '^- \*\*' "$out" || echo "No findings." >> "$out"
    for c in "$STATE_DIR"/components/*.txt; do
      comp=$(basename "$c" .txt)
      [ -s "$STATE_DIR/parts/$label-$area-$comp.md" ] || echo "MISSING $label $area $comp"
    done
  done
done
```

```bash
for label in openai gemini claude; do
  echo "== $label =="
  for area in security architecture solid correctness testing ops performance quality data; do
    f="$STATE_DIR/$label-$area.md"
    if [ ! -s "$f" ]; then
      echo "  $area MISSING"
    else
      n=$(grep -c '^- \*\*' "$f")
      cited=$(grep -oE '^- \*\*(High|Medium|Low)\*\* `[^`]+`' "$f" | grep -c ':[0-9]')
      unconf=$(grep -c 'line unconfirmed' "$f")
      echo "  $area ok findings=$n cited=$cited unconfirmed=$unconf"
    fi
  done
done
```

Then check coverage. Each arm's coverage record says which of its files it reviewed. The opened-files count checks the records against what arms actually read.

```bash
total=$(wc -l < "$STATE_DIR/ledger.txt" | tr -d ' ')
while read -r label model area comp; do
  f="$STATE_DIR/coverage/$label-$area-$comp.txt"
  want=$(wc -l < "$STATE_DIR/components/$comp.txt" | tr -d ' ')
  got=$(awk '$2 ~ /^reviewed/' "$f" 2>/dev/null | wc -l | tr -d ' ')
  [ "$got" -lt "$want" ] && echo "SHORT $label $area $comp reviewed=$got of $want"
done < "$STATE_DIR/tasks.txt"
cat "$STATE_DIR"/coverage/*.txt 2>/dev/null | awk '$2 ~ /^reviewed/ {print $1}' | sort -u > "$STATE_DIR/reviewed.txt"
echo "ledger files reviewed by at least one arm=$(comm -12 <(sort "$STATE_DIR/ledger.txt") "$STATE_DIR/reviewed.txt" | wc -l | tr -d ' ') of $total"
comm -23 <(sort "$STATE_DIR/ledger.txt") "$STATE_DIR/reviewed.txt" | sed 's/^/  never reviewed: /'
jq -r 'select(.type=="tool_use") | .part.state.input | (.filePath // .relative_path // .path // empty)' \
  "$STATE_DIR"/parts/raw-*.ndjson 2>/dev/null | sed "s|^$PROJECT_ROOT/||" | sort -u > "$STATE_DIR/opened.txt"
echo "ledger files opened=$(comm -12 <(sort "$STATE_DIR/ledger.txt") "$STATE_DIR/opened.txt" | wc -l | tr -d ' ') of $total"
jq -r '"ocr status=\(.status) files=\(.summary.files_reviewed) findings=\(.comments|length)"' "$STATE_DIR/ocr-scan.json"
```

A `SHORT` line is an arm that marked some of its component `skipped` or wrote no coverage record. Read its reasons in the coverage record. A skip because the file belongs to another area is fine. A skip for lack of depth is a gap.

Re-dispatch a `MISSING` arm with `bash "$STATE_DIR/arm.sh" <label> <model> <area> <comp>`, then rerun the merge.

Treat an area as unreviewed when its merged file is missing, or has neither a finding line nor exactly `No findings.` Never record either as `No findings.` Report every arm still missing after one retry to the operator as not reviewed, naming the model, area, and component.

Compare `cited` against `findings`. A finding whose first backticked field carries no `:line` is unusable, because nobody can confirm it without re-reading the whole file. `cited` counts a finding carrying a `path:line` whether or not it ends with `line unconfirmed`, so subtract `unconfirmed` for the count the reviewer stands behind. Read uncited findings before re-dispatching, and re-dispatch only when they carry no symbol either.

### Step 4: Sweep

One sweep arm per area and model gets the whole ledger and that area's merged findings, and looks only for defects not already listed. It catches what a component boundary hid.

```bash
: > "$STATE_DIR/sweeps.txt"
for entry in $MODELS; do
  for area in $AREAS; do
    [ -s "$STATE_DIR/${entry%%:*}-$area.md" ] && echo "${entry%%:*} ${entry#*:} $area sweep" >> "$STATE_DIR/sweeps.txt"
  done
done
xargs -P "$CONCURRENCY" -L 1 bash "$STATE_DIR/arm.sh" < "$STATE_DIR/sweeps.txt"

for f in "$STATE_DIR"/parts/raw-*-sweep.ndjson; do
  b=$(basename "$f" .ndjson); out="$STATE_DIR/parts/${b#raw-}.md"
  [ -s "$out" ] || jq -r 'select(.type=="text") | .part.text' "$f" | awk '/^## /{p=1} p' > "$out"
  merged="$STATE_DIR/${b#raw-}"; merged="${merged%-sweep}.md"
  n=$(grep -c '^- \*\*' "$out")
  if [ "$n" -gt 0 ]; then
    sed -i.bak '/^No findings\.$/d' "$merged" && rm -f "$merged.bak"
    grep -h '^- \*\*' "$out" >> "$merged"
  fi
  echo "$(basename "$merged" .md) sweep added=$n"
done
```

Re-export `STATE_DIR`, `TARGET_PATH`, and `PROJECT_ROOT`, and reset `AREAS`, `MODELS`, and `CONCURRENCY`, when this runs as a separate call from Step 2.

### Step 5: Scan, Collate, Verify, and Report

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

Then run the scripted stages. Run each model stage as a background Bash call. Its pool returns when every call has finished, and the completion notification is the signal to continue. Never poll a running stage with `sleep`.

```bash
S=<this skill's directory>/scripts
RUN=<RUN_DIR printed by Step 1>
python3 "$S/checkout.py" "$RUN"
python3 "$S/normalize.py" "$RUN"
python3 "$S/collate.py" "$RUN"         # one model call per component, background
uv run --with scikit-learn --with scipy --with numpy python "$S/windows.py" "$RUN"
python3 "$S/merge.py" "$RUN"           # one model call per similarity window, background
python3 "$S/rank.py" "$RUN"
python3 "$S/verify.py" "$RUN"          # one model call per Critical or High issue, background
python3 "$S/report.py" "$RUN"
```

| Stage | Output | What it does |
| ----- | ------ | ------------ |
| `checkout.py` | `checkout/` | Exports the reviewed commit with `git archive` and deletes `judge_exclude` paths, such as `CLAUDE.md`, `.claude/`, and review state. Every model stage reads only this tree. |
| `normalize.py` | `findings.jsonl` | Parses every merged findings file and ocr's comments into findings with stable IDs. Exits 1 on any bullet it cannot parse. |
| `collate.py` | `issues-by-component.jsonl` | Groups each component's findings into issues, where one issue is one code change. Every finding ID must land in exactly one issue or in the dropped list. |
| `windows.py` | `windows.json` | Orders all issues by text similarity and cuts overlapping windows of 150, so one window can see a defect reported in two components. |
| `merge.py` | `global_merges.json` | Merges issues that describe the same defect, where one change fixes all. The same pattern in independent places stays apart. |
| `rank.py` | `issues.jsonl`, `issues.md` | Applies the merges and ranks by severity, source count, and finding count. |
| `verify.py` | `verify/results.jsonl`, `verify/second.jsonl` | Opus at high tries to refute each Critical and High issue and returns a verdict, quoted evidence, the locations and members that do not hold, and its own severity. Fable at high rechecks, blind, every issue the verifier confirms as Critical. |
| `report.py` | `report.md` | Counts, every confirmed issue at the lower of its two ratings, the refuted ones with the reason, and coverage gaps. |

Every model call runs as its own `claude -p --bare` process with `--tools Bash,Read` under `--permission-mode dontAsk`, a 5-minute prompt cache, and the prompt on stdin. The pool checks that each process started with exactly those tools, checks every answer's content, and retries a rejected answer up to three times with the reasons appended. A verdict whose evidence quote is not the code at the reviewed commit is rejected. The review-tickets skill documents the measurements behind each of these settings.

The merge rule is narrower than it was. An earlier rule also merged the same kind of defect with the same kind of fix. It built one issue of 77 findings across 24 files, and tickets built from it cited locations that did not support the claim.

Report the counts from `report.md`, the confirmed Critical issues, and the coverage gaps to the operator. The run directory is the input to the review-tickets skill.

## Expected Output Files

`.llmtmp/review-deep/` holds the whole run and is wiped at the start of the next one:

- `<label>-<area>.md`, 27 merged findings files, component parts plus sweep
- `ocr-scan.json` and `ocr-scan.log`, the coverage pass
- `ledger.txt` and `skipped.txt`, the reviewable files and the excluded ones with ocr's reason
- `components/cNN.txt`, the partition
- `coverage/<label>-<area>-<comp>.txt`, each arm's reviewed or skipped record
- `reviewed.txt` and `opened.txt`, the files arms marked reviewed and the files they opened
- `parts/<label>-<area>-<comp>.md`, `parts/raw-*.ndjson`, `parts/*.log`, each arm's findings, event stream, and stderr
- `arm.sh`, `tasks.txt`, `sweeps.txt`, the runner and its work lists

The run directory, `${XDG_CACHE_HOME:-~/.cache}/review-deep/<repo>-<commit12>/`, holds Step 5's output and survives the next review of a different commit:

- `run.json`, the repository, commit, models, concurrency, judge exclusions, and commit sentence
- `checkout/`, the export every judge reads, and `checkout_excluded.json`
- `findings.jsonl`, `issues-by-component.jsonl`, `dropped.jsonl`, `unassigned.jsonl`, `windows.json`, `global_merges.json`
- `issues.jsonl` and `issues.md`, every issue with its member findings inlined
- `verify/results.jsonl` and `verify/second.jsonl`, the verdicts
- `report.md`
- `collate/`, `merge/`, `verify/first/`, `verify/second/`, each with `pool.log` and every model process's event stream under `calls/`

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

## Tests

Tests and evals for both review skills live in `evals/review/` at the root of the clanker-skills repository, outside the installed skill.

| Check | Command, from `evals/review/` | Cost |
| ----- | ------ | ---- |
| Unit tests, one directory per skill | `uv run --with pytest pytest -q unit/review_deep` and `unit/review_tickets` | none |
| End-to-end replay on the harbor fixture | `uv run --with pytest pytest -q test_end_to_end.py` | none |
| Live quality eval against `fixture/truth.json` | `python3 live_eval.py WORK_DIR --run` | about $3 at list price |

Run the unit tests and the replay after any change to `scripts/`. The replay stops with "prompt changed" when a prompt changes. Record again with `python3 pipeline.py WORK_DIR --mode record`, check the run with `live_eval.py`, and save it with `python3 golden.py save RUN_DIR`. Run the live eval on demand after changing a model, an effort level, or a prompt.

## Rules

- The invoking agent is a launcher. It performs no review analysis of its own. The Step 5 scripts and their model calls do all of it.
- NEVER let a Step 5 model call read the live working tree. They run in the run directory's `checkout/`.
- NEVER poll a background stage with `sleep` or a wait loop. Wait for its completion notification.
- Keep prompts in `prompts/` as `.txt`. A markdown formatter rewrote a `.md` prompt and changed its meaning.
- ALWAYS redirect stdin from `/dev/null` on `opencode run`. Omitting it hangs the process before session creation with no output and no error, which is anomalyco/opencode issue #38723.
- Impose no token cap and no turn cap on a reviewer. Let it finish.
- Run Step 2b a minute or so after dispatch, and again during long runs. An arm with an empty NDJSON is dead and holds a pool slot, and wall time cannot tell that apart from a slow review.
- Run the Step 2 and Step 4 blocks as background Bash calls. The pool blocks until every arm exits, and backgrounding keeps that out of the main session.
- Launch every arm through the pool and the ocr scan in one bash block. They are independent processes.
- Use plain message invocation, not `--command`. The `--command` flag has a known issue with the context7 MCP server.
- Do NOT clean up per-area files, NDJSON, or logs during a run. Step 1 wipes them at the start of the next one.
- If an arm fails, still wait for and report the others.
- Reviewer agents live in `configs/opencode/agents/` and are glob-linked by `./install`. A machine that has not run install since they changed fails with an unknown agent.
