#!/usr/bin/env python3
"""PreToolUse hook entrypoint (matcher: Agent).

Bridges Claude Code's actual hook contract (JSON on stdin, `hookSpecificOutput`
on stdout) to orchestrator.hooks.before_continue.handle_agent_spawn, the pure
context-injection function this plugin already implements and tests.

Contract (see https://code.claude.com/docs/en/hooks.md):
  stdin:  {"cwd": ..., "tool_name": "Agent", "tool_input": {"prompt": ..., "subagent_type": ..., "description": ..., ...}, ...}
  stdout: {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {...full original tool_input, "prompt": "..."}}}

`updatedInput` replaces the entire tool input, not just the fields this hook cares about —
it must carry every field the caller originally sent (description, subagent_type,
run_in_background, ...) with only `prompt` swapped for the context-injected version, or the
Agent tool call fails schema validation for missing required fields.

Any failure degrades to a no-op (exit 0, no output) so a broken hook never blocks
a real agent spawn.

DISABLED (2026-09-15): confirmed Claude Code harness bug, not fixable from this hook. The
Agent tool's PreToolUse `tool_input` never contains `description` in the first place (the
harness doesn't forward it to hooks), and `updatedInput` is validated as the *complete*
replacement input against the Agent tool's full schema rather than merged onto the original
tool_input -- so no hook can ever supply `description` back correctly, even with the merge
fix below in place (kept for whenever the harness bug is fixed; do not remove). Confirmed via:
(1) manual simulation of this exact patched script produces a fully correct updatedInput
including `description`; (2) the failure is identical across all 3 install locations after
patching; (3) the failure persists identically across a genuine app relaunch (new PID). See
~/.claude/sdd-memory/*/spec/2026-09-15-angular-dashboard-container/workflow-state.md for the
full investigation (independently reproduced in a different project the same day). Report to
Anthropic as a Claude Code bug; do not re-enable without new evidence the harness behavior
changed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hook_state import (  # noqa: E402
    workflow_state_path, load_workflow_state, save_workflow_state, error_registry_path,
)


def main():
    sys.exit(0)  # noqa: unreachable below is intentional, see DISABLED note above
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    spawn_prompt = tool_input.get("prompt")
    agent_type = tool_input.get("subagent_type") or payload.get("agent_type") or "unknown"
    if not spawn_prompt:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    state_path = workflow_state_path(cwd)
    if not state_path:
        sys.exit(0)  # no active SDD workflow — nothing to inject

    workflow_state = load_workflow_state(state_path)
    workflow_state["error_registry_path"] = error_registry_path(cwd)

    try:
        from orchestrator.hooks.before_continue import handle_agent_spawn
        modified_prompt = handle_agent_spawn(agent_type, spawn_prompt, workflow_state)
    except Exception:
        sys.exit(0)  # graceful degradation — never block the spawn

    save_workflow_state(state_path, workflow_state)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**tool_input, "prompt": modified_prompt}
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
