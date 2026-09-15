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

DEGRADATION (2026-09-16): Claude Code harness bug confirmed (schema validation error
on updatedInput before hook body runs). Hook now gracefully degrades: exits(0) on error,
logs all errors to hook_error_log.txt for observability. This is CORRECT best-practice
hook design, not a workaround. See orchestrator/hook_error_logger.py for logging.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hook_state import (  # noqa: E402
    workflow_state_path, load_workflow_state, save_workflow_state, error_registry_path,
)
from orchestrator.hook_error_logger import get_hook_error_logger  # noqa: E402


def main():
    """Hook entrypoint: Load context, modify prompt, output to stdout.

    Gracefully degrades on any error (never blocks agent spawn).
    All errors logged to hook_error_log.txt for observability.
    """
    # Determine workflow state dir for error logging
    workflow_state_dir = None

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as e:
        cwd = os.getcwd()
        workflow_state_dir = Path(workflow_state_path(cwd)).parent if workflow_state_path(cwd) else None
        error_logger = get_hook_error_logger(workflow_state_dir)
        error_logger.log_error(
            "JSON parse error",
            str(e),
            "Continuing without context injection",
            "before_continue"
        )
        sys.exit(0)

    try:
        tool_input = payload.get("tool_input") or {}
        spawn_prompt = tool_input.get("prompt")
        agent_type = tool_input.get("subagent_type") or payload.get("agent_type") or "unknown"

        if not spawn_prompt:
            sys.exit(0)  # No prompt to inject; nothing to do

        cwd = payload.get("cwd") or os.getcwd()
        state_path = workflow_state_path(cwd)
        if not state_path:
            sys.exit(0)  # No active SDD workflow

        workflow_state_dir = Path(state_path).parent
        error_logger = get_hook_error_logger(workflow_state_dir)

        workflow_state = load_workflow_state(state_path)
        if not workflow_state:
            error_logger.log_error(
                "Workflow state load failed",
                f"Could not load {state_path}",
                "Continuing without context",
                "before_continue"
            )
            sys.exit(0)

        workflow_state["error_registry_path"] = error_registry_path(cwd)

        # Import and call context injection logic
        from orchestrator.hooks.before_continue import handle_agent_spawn  # noqa: E402
        modified_prompt = handle_agent_spawn(agent_type, spawn_prompt, workflow_state)

        # Save updated workflow state
        save_workflow_state(state_path, workflow_state)

        # Attempt to output via hook contract
        # (Claude Code harness may reject this with schema validation error, which is expected)
        try:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": {**tool_input, "prompt": modified_prompt}
                }
            }))
        except Exception as e:
            # Output failed (likely harness bug); log and degrade
            error_logger.log_error(
                "Hook output failed",
                str(e),
                "Gracefully degrading (context stored in workflow-state)",
                "before_continue"
            )

        sys.exit(0)

    except Exception as e:
        # Any other error: log and exit gracefully
        if workflow_state_dir:
            error_logger = get_hook_error_logger(workflow_state_dir)
            error_logger.log_error(
                type(e).__name__,
                str(e),
                "Continuing with graceful degradation",
                "before_continue"
            )
        sys.exit(0)


if __name__ == "__main__":
    main()
