#!/usr/bin/env python3
"""PreToolUse hook: deny spawning agent-tdd:agent-TDD (the Design Spec handoff) unless the
active feature's requirements.md and design.md both have `State: Approved` on disk, the
state records `Implementation Requested: Yes`, and the frozen Approval Hash (requirements.md +
design.md, see approval.py) still matches. A pending approval or a legacy (pre-hash) feature is
frozen at this spawn and allowed; a mismatch or blank hash is denied with the AskUserQuestion +
`approval.py refreeze` recovery steps. Applies to every agent-TDD spawn, Track: Fast included.

Modeled on slice_spec_gate.py's allow()/deny()/no_decision() shape -- deny() in particular,
since memory_permission.py (this plugin's other PreToolUse gate) only ever allows or no-ops.
Only mutation: freezing the Approval Hash (see check_approval). Scoped to exactly `agent-tdd:agent-TDD` so it can't misfire
on an unrelated Task call; every other spawn passes through untouched.

If no SDD workflow is active at all, this is not this plugin's business to gate a non-SDD
spawn -- falls through (no decision) rather than denying.

Caution (see path_resolution.py's "identity-split hazard"): "no active workflow" is exactly
what this hook also sees if the active feature's state was written under a *different* plugin
identity's data dir than the one this hook itself resolves to this session -- e.g. state
scaffolded by a manual `python3 hooks/sdd_memory.py ...` Bash call (which never gets
`${CLAUDE_PLUGIN_DATA}` injected) instead of a real hook. In that case this hook can't tell "no
workflow" apart from "workflow is one directory over," and falls through the same way --
silently allowing an unapproved Design Spec spawn rather than denying it. Never invoke
hooks/*.py directly outside the real registered hook chain; see path_resolution.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approval  # noqa: E402
from sdd_state import active_state_file, parse_state, parse_state_json  # noqa: E402

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


def _approval_cmd(sub, feature_dir):
    """Runnable command with real absolute paths (CLAUDE_PLUGIN_ROOT is unset in the model's own
    Bash calls); CLAUDE_PLUGIN_DATA is the value this hook resolved."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "approval.py")
    data = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return f'CLAUDE_PLUGIN_DATA="{data}" python3 "{script}" {sub} "{feature_dir}"'


def check_approval(state_path, who="Design Spec"):
    """Returns a deny reason, or None to allow. Applies to every agent-TDD spawn (Design Spec
    and Track: Fast alike). May freeze the Approval Hash (pending approval / legacy feature):
    a state write from a PreToolUse hook, accepted; approval.py's refreeze/approve CLI is the
    recovery path."""
    feature_dir = os.path.dirname(state_path)
    requirements_path = os.path.join(feature_dir, "requirements", "requirements.md")
    design_path = os.path.join(feature_dir, "design", "design.md")

    if not _is_approved(requirements_path):
        return (
            f"SDD {who} gate: requirements.md is missing or not State: Approved "
            f"({requirements_path}). Complete and approve Requirements before spawning "
            "agent-tdd:agent-TDD."
        )
    if not _is_approved(design_path):
        return (
            f"SDD {who} gate: design.md is missing or not State: Approved "
            f"({design_path}). Complete and approve Design before spawning agent-tdd:agent-TDD."
        )
    fields = parse_state(state_path)
    if fields.get("implementation requested", "").strip().lower() not in ("yes", "true"):
        return (
            f"SDD {who} gate: `Implementation Requested: Yes` is not recorded in {state_path}. "
            "First confirm with the user via AskUserQuestion that they approve moving to "
            "Implementation; only after they approve, run: "
            f"{_approval_cmd('approve', feature_dir)} "
            "-- then retry the agent-tdd:agent-TDD spawn."
        )
    json_fields = parse_state_json(os.path.join(feature_dir, "workflow-state.json"))
    try:
        with open(requirements_path, "r", encoding="utf-8") as fh:
            req_text = fh.read()
        with open(design_path, "r", encoding="utf-8") as fh:
            design_text = fh.read()
    except OSError:
        return f"SDD {who} gate: could not read requirements.md/design.md to verify the approval hash."
    status = approval.verify(fields, req_text, design_text, json_fields)
    if status == "ok":
        return None
    if status in ("pending", "legacy"):
        # pending: first spawn after approval -- freeze now. legacy: approved before hashing
        # existed -- allow once and record the hash from here on. Both artifacts were just read
        # non-empty (State: Approved), so freeze cannot refuse.
        approval.freeze(feature_dir)
        return None
    cmd = _approval_cmd("refreeze", feature_dir)
    if status == "mismatch":
        return (
            f"SDD {who} gate: requirements.md/design.md changed after approval (Approval Hash "
            "mismatch). First confirm the changed scope with the user via AskUserQuestion; only "
            f"after they approve, run: {cmd} -- then retry the agent-tdd:agent-TDD spawn."
        )
    return (
        f"SDD {who} gate: the Approval Hash field in {state_path} is blank or invalid. First "
        f"confirm the scope with the user via AskUserQuestion; only after they approve, run: "
        f"{cmd} -- then retry."
    )


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

    reason = check_approval(state_path)
    if reason:
        deny(reason)

    no_decision()


if __name__ == "__main__":
    main()
