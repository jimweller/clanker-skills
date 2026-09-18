#!/usr/bin/env bash
# Baseline arm of the launder loop. Classifies the passage as written without
# rewriting it, so the run has a floor to beat.
#
# promptfoo exec provider. Receives the passage as $1 and prints one word.
set -euo pipefail

EVAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASSAGE="$(mktemp)"
trap 'rm -f "$PASSAGE"' EXIT
printf '%s' "$1" >"$PASSAGE"

# --setting-sources project gives a session that never loads ~/.claude/CLAUDE.md.
# Without it the judge can recite the 55-bullet catalog verbatim and grades the
# text against the contract rather than reading it, which turns every verdict
# into a compliance check on the rules that produced the text.
args=(-p --output-format text --strict-mcp-config --setting-sources project
      --mcp-config '{"mcpServers":{}}' --no-session-persistence)
[[ -n "${EVAL_MODEL:-}" ]] && args+=(--model "$EVAL_MODEL")

prompt="$(python3 "$EVAL_ROOT/tools/render-template.py" \
  "$EVAL_ROOT/prompts/discriminate.txt" passage "$PASSAGE")"

claude "${args[@]}" "$prompt" \
  | perl -CSD -pe 'if ($. == 1) { s/^(?:[^\x00-\x7F]+\s*)+// }'
