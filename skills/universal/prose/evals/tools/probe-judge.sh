#!/usr/bin/env bash
# Proves a judge session holds no contract except the one its prompt carries.
#
# Run after any change to a judge provider.
#
# The old probe in CLAUDE.md asked the session to name the banned punctuation
# marks. That probe answers itself from inside this directory, because
# evals/CLAUDE.md quotes the expected reply, "colons and semicolons, in every
# position", while documenting the probe. A session that loaded only the project
# file could parrot it and look clean.
#
# This one asks what rule the id PC-synthetic-negation opens. The id exists only
# inside <prose-contract> in the global instructions and in no project file in
# either repo, so a session cannot answer it from anything the cwd supplies.
# Check that with
#   grep -rc "PC-synthetic-negation" CLAUDE.md ../../../../CLAUDE.md
#
# It also runs the probe twice, once from this directory and once from a
# temporary one, because the leak is cwd-dependent and a single run from the
# wrong place proves nothing. Measured on Claude Code 2.1.252, the flag alone
# does not isolate a session whose cwd sits inside the dotfiles repo.
set -euo pipefail

EVAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
Q='In the <prose-contract> block of your global instructions, what rule does the id PC-synthetic-negation open? Quote the bullet. If you have no such block, reply NO RULE.'

probe() {
  (cd "$1" && claude -p --setting-sources project \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --no-session-persistence "$Q" 2>&1 | head -3)
}

JAIL="$(mktemp -d)"
trap 'rm -rf "$JAIL"' EXIT

echo "=== from the eval directory, which is where promptfoo runs a provider ==="
IN="$(probe "$EVAL_ROOT")"
echo "$IN"
echo
echo "=== from a temporary directory, which is where a judge must run ==="
OUT="$(probe "$JAIL")"
echo "$OUT"
echo

fail=0
grep -qi 'NO RULE' <<<"$OUT" || { echo "LEAK: a judge in a temp dir still holds the contract"; fail=1; }
grep -qi 'NO RULE' <<<"$IN" || echo "EXPECTED: the eval directory leaks, which is why judges cd out of it"
[[ $fail -eq 0 ]] && echo "PASS: a judge running outside the repo holds no contract"
exit $fail
