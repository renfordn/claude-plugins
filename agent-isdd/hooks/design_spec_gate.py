#!/usr/bin/env python3
"""PreToolUse hook: deny spawning agent-tdd:agent-TDD (the Design Spec handoff) unless the
active feature's requirements.md and design.md both have `State: Approved` on disk.

Modeled on slice_spec_gate.py's allow()/deny()/no_decision() shape -- deny() in particular,
since memory_permission.py (this plugin's other PreToolUse gate) only ever allows or no-ops.
Read-only: never mutates state. Scoped to exactly `agent-tdd:agent-TDD` so it can't misfire
on an unrelated Task call; every other spawn passes through untouched.

If no SDD workflow is active at all, this is not this plugin's business to gate a non-SDD
spawn -- falls through (no decision) rather than denying.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file  # noqa: E402

GATED_SUBAGENT_TYPE = "agent-tdd:agent-TDD"


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def no_decision():
    sys.exit(0)


def _is_approved(path):
    """True when `path` exists and contains a `- State: Approved` line (any case)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return False
    for line in content.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if stripped.lower().startswith("state:") and stripped.split(":", 1)[1].strip().lower() == "approved":
            return True
    return False


def main(payload=None):
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            no_decision()

    tool_input = payload.get("tool_input") or {}
    if tool_input.get("subagent_type") != GATED_SUBAGENT_TYPE:
        no_decision()

    cwd = payload.get("cwd") or os.getcwd()
    state_path = active_state_file(cwd)
    if not state_path:
        # No active SDD workflow -- not this plugin's business to gate a non-SDD spawn.
        no_decision()

    feature_dir = os.path.dirname(state_path)
    requirements_path = os.path.join(feature_dir, "requirements", "requirements.md")
    design_path = os.path.join(feature_dir, "design", "design.md")

    if not _is_approved(requirements_path):
        deny(
            "SDD Design Spec gate: requirements.md is missing or not State: Approved "
            f"({requirements_path}). Complete and approve Requirements before spawning "
            "agent-tdd:agent-TDD."
        )
    if not _is_approved(design_path):
        deny(
            "SDD Design Spec gate: design.md is missing or not State: Approved "
            f"({design_path}). Complete and approve Design before spawning agent-tdd:agent-TDD."
        )

    no_decision()


if __name__ == "__main__":
    main()
