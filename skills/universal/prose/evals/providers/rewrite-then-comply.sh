#!/usr/bin/env bash
# Compliance loop. A paragraph goes in, the contract rewrites it while recording
# which style-rules drove each decision, and a second session grades the edit
# against the contract text.
#
# This replaces the provenance question. The old judge asked whether a rewrite
# read human, which had no ground truth and could not tell a correct rewrite
# from an over-application, because both look like a lost human verdict. This
# one asks whether the edit complies, and names the style-rule behind every
# finding.
#
# The judge receives the contract through its prompt, which keeps the rule set
# versioned and visible in the run and keeps the persona, the chat register and
# the LSP rules out of a grader that has no use for them.
#
# --bare gives that directly. It skips hooks, LSP and plugin filtering, and it loads
# no CLAUDE.md, so a judge started anywhere holds nothing but its prompt. Probed from
# inside this repo it answers NO RULE when asked to quote PC-synthetic-negation.
#
# It replaces --setting-sources project plus a temp-directory jail. That flag alone
# does not isolate a session whose cwd sits inside this repo, because ~/.claude/CLAUDE.md
# is a symlink into it, so the earlier version had to cd elsewhere first. --bare removes
# the cwd dependency. It costs nothing measurable, 25s against 21s on one case.
#
# The judge sees the original as well as the edit. Over-application is invisible from
# the output alone, since a deleted span leaves nothing behind to quote.
#
# promptfoo exec provider. Receives the passage as $1 and prints one artifact
# carrying the rewrite, the editor notes, and the findings.
set -euo pipefail

EVAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$(mktemp)"
MID="$(mktemp)"
trap 'rm -f "$SRC" "$MID"' EXIT
printf '%s' "$1" >"$SRC"

# The rewriter loads the contract and the prose skill. That is the thing under test.
#
# --setting-sources project drops user settings, which is where this machine's hooks
# live. On one 213-call run the claude-mem worker went unreachable for 65 consecutive
# hooks and some sessions returned the block banner in place of a rewrite, which the
# judge then graded as prose. That produced 10 PC-assistant-tool-leaks findings and 21
# runs with no notes file.
#
# The contract and the skill both survive the flag, because ~/.claude/CLAUDE.md is a
# symlink into this repo, so from a cwd inside it they resolve as project sources.
# --bare would also drop hooks but strips the contract and the skill with them, which
# removes the thing under test. Verified by probe: under --bare the session answers no
# to holding a <prose-contract> block and cannot invoke the prose skill.
#
# Write is allowed so the editor can put its notes in a file instead of in stdout.
# --allowedTools is variadic, so a flag has to follow it or it swallows the prompt
# argument and claude exits with "Input must be provided".
args=(-p --strict-mcp-config --allowedTools Write --output-format text
      --setting-sources project
      --mcp-config '{"mcpServers":{}}' --no-session-persistence)
[[ -n "${EVAL_MODEL:-}" ]] && args+=(--model "$EVAL_MODEL")

judge_args=(-p --output-format text --strict-mcp-config --bare
            --mcp-config '{"mcpServers":{}}' --no-session-persistence)
JM="${JUDGE_MODEL:-${EVAL_MODEL:-}}"
[[ -n "$JM" ]] && judge_args+=(--model "$JM")

# Medium effort, measured against the judge's own noise floor rather than assumed.
# Re-judging 48 stored rewrites with the same model and settings twice agreed on
# 39 percent of findings and 81 percent of clean-or-dirty verdicts. Opus at medium
# scored 30 and 79 against that floor, so it cannot be shown to differ. Sonnet
# scored 21 and 67, which is below the floor, and is not a substitute at any effort.
judge_args+=(--effort "${JUDGE_EFFORT:-medium}")

strip_glyph() { perl -CSD -pe 'if ($. == 1) { s/^(?:[^\x00-\x7F]+\s*)+// }'; }

# The contract is the judge's whole rule set, so a stale copy grades against
# rules that are no longer deployed. Rebuild whenever the source file moves.
CONTRACT="${CONTRACT_FILE:-$EVAL_ROOT/../../../../../../configs/claude-code/claude_md.md}"
CAT="$EVAL_ROOT/corpus/catalog.md"
if [[ ! -f "$CAT" || "$CONTRACT" -nt "$CAT" ]]; then
  TMP_CAT="$(mktemp)"
  python3 "$EVAL_ROOT/tools/extract-catalog.py" "$TMP_CAT"
  mv -f "$TMP_CAT" "$CAT"
fi

# The rewrite prompt invokes the prose skill and says nothing about how to write. A
# guard against a defect hides the defect. Telling the editor to invent no numbers
# duplicates PC-add-nothing and PC-computed-number and suppresses the exact failure the
# judge is about to grade, so the run scores the prompt instead of the contract.
#
# Notes go to a file rather than to stdout, so what this measures is what a real
# `/prose` run prints. The instruction sits after the rewrite instruction because an
# editor that enumerates before editing does not edit the way one that just edits does.
# Writing notes afterward reduces that effect without removing it, which is a known
# limit rather than a solved problem.
#
NOTES_DIR="${REWRITE_NOTES_DIR:-$EVAL_ROOT/corpus/notes}"
mkdir -p "$NOTES_DIR"
HASH="$(shasum -a 256 "$SRC" | cut -c1-12)"
NOTES="$NOTES_DIR/$HASH.$$.txt"

rewrite_prompt="$(python3 "$EVAL_ROOT/tools/render-template.py" \
  "$EVAL_ROOT/prompts/rewrite-notes.txt" --set "notes=$NOTES" input "$SRC")"
claude "${args[@]}" "$rewrite_prompt" | strip_glyph >"$MID"

judge_prompt="$(python3 "$EVAL_ROOT/tools/render-template.py" \
  "$EVAL_ROOT/prompts/comply.txt" \
  catalog "$CAT" source "$SRC" rewrite "$MID")"

printf '<<<REWRITE>>>\n'
cat "$MID"
printf '<<<NOTES>>>\n'
cat "$NOTES" 2>/dev/null || printf 'NO NOTES FILE\n'
printf '<<<FINDINGS>>>\n'
claude "${judge_args[@]}" "$judge_prompt" | strip_glyph
