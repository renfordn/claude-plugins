#!/usr/bin/env python3
"""PreToolUse hook entrypoint (matcher: Agent).

Adopts the agent-isdd non-tampering approach to avoid Claude Code harness schema
validation issues (where updatedInput for the Agent tool fails validation against description):

1. Coordinates and caches orchestrator state in workflow-state.json:
   - Fetches and caches the agent-nelly brief
   - Builds and caches the CapabilityMap
   - Creates pre-spawn checkpoints
   - Evaluates project error patterns
2. Does NOT emit `updatedInput` on stdout (prevents harness schema validation crashes).
3. If an unresolved escalation or rollback is pending, emits a `systemMessage` to alert
   the user/session.
4. Otherwise exits cleanly (exit code 0, no stdout) so the Agent tool call proceeds unblocked.
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
from orchestrator.hook_telemetry import get_hook_telemetry_logger  # noqa: E402


def main():
    """Hook entrypoint: Update workflow state, surface alerts via systemMessage if any,
    and exit cleanly without emitting updatedInput.
    """
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
            sys.exit(0)  # No prompt; nothing to do

        cwd = payload.get("cwd") or os.getcwd()
        state_path = workflow_state_path(cwd)
        if not state_path:
            sys.exit(0)  # No active SDD workflow

        workflow_state_dir = Path(state_path).parent
        error_logger = get_hook_error_logger(workflow_state_dir)
        telemetry = get_hook_telemetry_logger(workflow_state_dir)
        telemetry.emit("hook_invoked", hook="before_continue", agent_type=agent_type)

        workflow_state = load_workflow_state(state_path)
        if not workflow_state:
            error_logger.log_error(
                "Workflow state load failed",
                f"Could not load {state_path}",
                "Continuing without context",
                "before_continue"
            )
            telemetry.emit(
                "hook_completed", hook="before_continue", agent_type=agent_type,
                outcome="workflow_state_load_failed",
            )
            sys.exit(0)

        workflow_state["error_registry_path"] = error_registry_path(cwd)

        # Check for pending rollback/escalation before state processing
        rollback_marker = workflow_state.get("rollback_pending")
        system_message = None
        if rollback_marker:
            if isinstance(rollback_marker, dict):
                source = rollback_marker.get("source") or rollback_marker.get("escalation_type", "prior agent")
                reason = rollback_marker.get("reason") or rollback_marker.get("action_required", "unresolved escalation")
                target = rollback_marker.get("target", "Requirements")
                system_message = (
                    f"⚠️ **Rollback Pending** (from {source})\n\n"
                    f"**Issue:** {reason}\n\n"
                    f"**Suggested action:** Rewind to **{target}** phase to address the issue.\n\n"
                    f"To proceed, reply with: `/isdd-rewind {target}`\n"
                    f"Or type a message to discuss first."
                )
            else:
                system_message = f"⚠️ **Rollback Pending**: {rollback_marker}"

        # Import and execute context coordination logic (caches brief, capability map, checkpoint, etc.)
        from orchestrator.hooks.before_continue import handle_agent_spawn  # noqa: E402
        handle_agent_spawn(agent_type, spawn_prompt, workflow_state)

        # Save updated workflow state with cached artifacts & checkpoints
        save_workflow_state(state_path, workflow_state)

        # Emit systemMessage if an alert is pending (agent-isdd pattern)
        # Note: Do NOT emit updatedInput, avoiding the harness schema validation bug.
        if system_message:
            print(json.dumps({"systemMessage": system_message}))

        telemetry.emit(
            "hook_completed", hook="before_continue", agent_type=agent_type,
            outcome="ok", rollback_pending=bool(rollback_marker),
        )

        sys.exit(0)

    except Exception as e:
        # Any unexpected error: log and exit gracefully (never block agent spawn)
        if workflow_state_dir:
            error_logger = get_hook_error_logger(workflow_state_dir)
            error_logger.log_error(
                type(e).__name__,
                str(e),
                "Continuing with graceful degradation",
                "before_continue"
            )
            get_hook_telemetry_logger(workflow_state_dir).emit(
                "hook_error", hook="before_continue", error_type=type(e).__name__,
            )
        sys.exit(0)


if __name__ == "__main__":
    main()
