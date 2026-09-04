#!/usr/bin/env python3
"""Before-continue hook: surface pending rollback requests from agent-tdd.

When agent-tdd's task slicing phase finds an unrecoverable blocker (task conflicts,
design contradiction, research gap), it emits a <!--AGENT-TDD-PLAN-FLAG:reason="...">
marker. The SubagentStop hook catches it and writes rollback_pending to workflow-state.json.

This hook runs at workflow resume (on /isdd-continue) and surfaces the rollback to the
user with reasoning and suggested action.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state_json


def main():
    """Check for pending rollback; surface to user if found.

    Also detects agent-tdd paused state (e.g., mid-refactor waiting for code-review)
    and handles resumption via continuation context.
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        sys.exit(0)

    feature_dir = os.path.dirname(state)
    json_path = os.path.join(feature_dir, "workflow-state.json")

    state_json = parse_state_json(json_path)
    rollback = state_json.get("rollback_pending")

    if not rollback:
        # Check for agent-tdd paused mid-refactor (code-review gate)
        # This is handled by spec-driven-development skill when it resumes,
        # not here. This hook only handles rollback requests and state checks.
        sys.exit(0)  # no pending rollback — continue normally

    target = rollback.get("target", "Requirements")
    reason = rollback.get("reason", "unknown issue")
    source = rollback.get("source", "agent-tdd")

    # Surface to user with clear action
    message = (
        f"⚠️ **Rollback Pending** (from {source})\n\n"
        f"**Issue:** {reason}\n\n"
        f"**Suggested action:** Rewind to **{target}** phase to address the issue.\n\n"
        f"To proceed, reply with: `/isdd-rewind {target}`\n"
        f"Or type a message to discuss first."
    )

    print(json.dumps({"systemMessage": message}))
    sys.exit(0)


if __name__ == "__main__":
    main()
