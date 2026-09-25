#!/usr/bin/env bash
# Independent review in a fresh `claude -p` process, for when the Agent tool can't spawn.
set -euo pipefail

brief="${1:?usage: review_headless.sh \"<brief: mode, review_level, scope, acceptance criteria>\"}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v claude >/dev/null || { echo "review_headless: claude CLI not on PATH" >&2; exit 127; }

agent="$(awk 'n >= 2; /^---$/ { n++ }' "$root/agents/code-reviewer.md")"
agent="${agent//'${CLAUDE_PLUGIN_ROOT}'/$root}"

exec claude -p "$agent

Headless run: only Read, Grep, Glob and read-only git (diff/log/show/status) are permitted here.
Tests cannot be run, so evidence that would need execution caps at tier-2.

## Review brief
$brief" \
  --allowedTools Read Grep Glob "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)" "Bash(git status:*)" \
  --disallowedTools Edit Write NotebookEdit Agent
