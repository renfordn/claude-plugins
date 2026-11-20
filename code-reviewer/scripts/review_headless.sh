#!/usr/bin/env bash
# Run one of this plugin's agents in a fresh `claude -p` process, for when the Agent tool can't spawn.
set -euo pipefail

usage='usage: review_headless.sh [--agent code-reviewer|finding-verifier] [--scope <slice-id>] [--cwd <path>] "<brief>"  (env: REVIEW_SCOPE, REVIEW_CWD)'
agent_name=code-reviewer
scope="${REVIEW_SCOPE:-}"; cwd="${REVIEW_CWD:-}"
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --agent) agent_name="${2:?$usage}" ;;
    --scope) scope="${2:?$usage}" ;;
    --cwd) cwd="${2:?$usage}" ;;
    *) echo "review_headless: unknown flag '$1'" >&2; exit 2 ;;
  esac
  shift 2
done
[[ "$agent_name" =~ ^[a-z-]+$ ]] || { echo "review_headless: bad agent name '$agent_name'" >&2; exit 2; }
# Same shape as agent-tdd's slice ID marker (copied, not imported): 3, 0a, 12b.
[[ -z "$scope" || "$scope" =~ ^[0-9]+[A-Za-z0-9]*$ ]] || { echo "review_headless: bad scope '$scope'" >&2; exit 2; }
[[ -z "$cwd" || -d "$cwd" ]] || { echo "review_headless: cwd '$cwd' is not a directory" >&2; exit 2; }
brief="${1:?$usage}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agent_file="$root/agents/$agent_name.md"
[[ -f "$agent_file" ]] || { echo "review_headless: no agent $agent_file" >&2; exit 2; }
command -v claude >/dev/null || { echo "review_headless: claude CLI not on PATH" >&2; exit 127; }

model="$(awk '/^---$/ { n++; next } n == 1 && /^model:/ { print $2; exit }' "$agent_file")"
[[ "$model" != inherit ]] || model=""
agent="$(awk 'n >= 2; /^---$/ { n++ }' "$agent_file")"
agent="${agent//'${CLAUDE_PLUGIN_ROOT}'/$root}"

extra=""
[[ -z "$scope" || "$agent_name" != code-reviewer ]] || extra+="
Review scope: slice=$scope
Begin your report with the line <!--REVIEW-SCOPE: slice=$scope--> before the report marker."
[[ -z "$cwd" ]] || extra+="
Review cwd: $cwd"
[[ -z "$cwd" ]] || cd "$cwd"

exec claude -p "$agent

Headless run: only Read, Grep, Glob and read-only git (grep/diff/log/show/status) are permitted here.
Tests cannot be run, so evidence that would need execution caps at tier-2.$extra

## Brief
$brief" \
  --allowedTools Read Grep Glob "Bash(git grep:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)" "Bash(git status:*)" \
  --disallowedTools Edit Write NotebookEdit Agent \
  ${model:+--model "$model"}
