#!/usr/bin/env bash
# promptfoo exec provider. Receives the rendered prompt as $1 and prints the
# reply on stdout.
#
# MCP servers and session persistence are off so a run measures the prose
# contract in the global instructions rather than the surrounding tooling.
# Set EVAL_MODEL to pin a model, otherwise the session default applies.
set -euo pipefail

args=(
  -p
  --output-format text
  --strict-mcp-config
  --mcp-config '{"mcpServers":{}}'
  --no-session-persistence
)

if [[ -n "${EVAL_MODEL:-}" ]]; then
  args+=(--model "$EVAL_MODEL")
fi

# The global instructions prefix every reply with a STARTER_CHARACTER glyph.
# That belongs to the chat register rather than the artifact under test, so the
# leading run of non-ASCII characters comes off line 1 before grading.
claude "${args[@]}" "$1" | perl -CSD -pe 'if ($. == 1) { s/^(?:[^\x00-\x7F]+\s*)+// }'
