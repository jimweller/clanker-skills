#!/usr/bin/env bash
# The launder loop. Rewrites the passage against the contract, then hands the
# rewrite to a fresh session that classifies it as human or generated.
#
# The judge is a separate process with no history, so it never learns the text
# was rewritten and cannot score the edit rather than the prose. It does load the
# same global instructions, so it is a contract-aware judge, which is a known
# limitation rather than an accident.
#
# The number that matters is the share of rewrites the judge calls human. The
# baseline arm, providers/judge-only.sh, gives the floor.
#
# promptfoo exec provider. Receives the passage as $1 and prints one word.
#
# Set LAUNDER_KEEP_REWRITE to a directory to retain each rewrite for reading.
set -euo pipefail

EVAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$(mktemp)"
MID="$(mktemp)"
trap 'rm -f "$SRC" "$MID"' EXIT
printf '%s' "$1" >"$SRC"

# The rewriter loads the contract. That is the thing under test.
args=(-p --output-format text --strict-mcp-config
      --mcp-config '{"mcpServers":{}}' --no-session-persistence)
[[ -n "${EVAL_MODEL:-}" ]] && args+=(--model "$EVAL_MODEL")

# --setting-sources project gives a session that never loads ~/.claude/CLAUDE.md.
# Without it the judge can recite the 55-bullet catalog verbatim and grades the
# text against the contract rather than reading it, which turns every verdict
# into a compliance check on the rules that produced the text.
judge_args=(-p --output-format text --strict-mcp-config --setting-sources project
            --mcp-config '{"mcpServers":{}}' --no-session-persistence)
[[ -n "${EVAL_MODEL:-}" ]] && judge_args+=(--model "$EVAL_MODEL")

strip_glyph() { perl -CSD -pe 'if ($. == 1) { s/^(?:[^\x00-\x7F]+\s*)+// }'; }

rewrite_prompt="$(python3 "$EVAL_ROOT/tools/render-template.py" \
  "$EVAL_ROOT/prompts/rewrite.txt" input "$SRC")"
claude "${args[@]}" "$rewrite_prompt" | strip_glyph >"$MID"

# Always keep the intermediate. The verdict alone says a rewrite failed and not
# why, and the why is usually sentence-length uniformity that the report can
# only measure with the text in hand. Named by source hash so a rewrite pairs
# back to the paragraph that produced it across repeats.
KEEP="${LAUNDER_KEEP_REWRITE:-$EVAL_ROOT/corpus/rewrites}"
mkdir -p "$KEEP"
HASH="$(shasum -a 256 "$SRC" | cut -c1-12)"
cp "$MID" "$KEEP/$HASH.$$.txt"

# A [GAP: ...] marker is an editorial annotation the contract asks for, not
# prose, and no human draft carries one. Leaving it in hands the judge a tell
# that has nothing to do with whether the sentences read human.
perl -CSD -i -pe 's/\s*\[\s*GAPS?\s*:[^\]]*\]//gi' "$MID"

judge_prompt="$(python3 "$EVAL_ROOT/tools/render-template.py" \
  "$EVAL_ROOT/prompts/discriminate.txt" passage "$MID")"
claude "${judge_args[@]}" "$judge_prompt" | strip_glyph
