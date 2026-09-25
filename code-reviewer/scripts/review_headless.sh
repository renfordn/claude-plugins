#!/usr/bin/env bash
# Run one of this plugin's agents in a fresh `claude -p` process, for when the Agent tool can't spawn.
set -euo pipefail

usage='usage: review_headless.sh [--agent code-reviewer|finding-verifier|cross-file-reviewer] "<brief>"'
agent_name=code-reviewer
if [[ "${1:-}" == --agent ]]; then agent_name="${2:?$usage}"; shift 2; fi
[[ "$agent_name" =~ ^[a-z-]+$ ]] || { echo "review_headless: bad agent name '$agent_name'" >&2; exit 2; }
brief="${1:?$usage}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agent_file="$root/agents/$agent_name.md"
[[ -f "$agent_file" ]] || { echo "review_headless: no agent $agent_file" >&2; exit 2; }
command -v claude >/dev/null || { echo "review_headless: claude CLI not on PATH" >&2; exit 127; }

agent="$(awk 'n >= 2; /^---$/ { n++ }' "$agent_file")"
agent="${agent//'${CLAUDE_PLUGIN_ROOT}'/$root}"

exec claude -p "$agent

Headless run: only Read, Grep, Glob and read-only git (grep/diff/log/show/status) are permitted here.
Tests cannot be run, so evidence that would need execution caps at tier-2.

## Brief
$brief" \
  --allowedTools Read Grep Glob "Bash(git grep:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)" "Bash(git status:*)" \
  --disallowedTools Edit Write NotebookEdit Agent
