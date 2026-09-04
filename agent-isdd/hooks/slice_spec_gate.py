#!/usr/bin/env python3
"""PreToolUse gate: deny spawning agent-tdd:agent-TDD / agent-tdd:test-author unless the
constructed Slice Spec looks complete, per INTEROP.md's field mapping.

Mirrors commit_audit_gate.py's verify-then-allow/deny pattern -- the one other hard gate in
this plugin. Deliberately scoped to exactly these two subagent_type values so it can never
misfire on an unrelated Task call; every other spawn passes through untouched. This is the
one hook point in the "sibling-plugin hook reliability" feature where a hard gate is
justified (see design.md's Risks And Tradeoffs) -- the Implementation Handoff is a single,
narrowly-scoped, consequential call, unlike routine phase-transition writes.

The check is deliberately shallow (field-name presence in the prompt text), not a full
parse: a hook can't semantically judge Slice Spec quality, only whether the required
sections were included at all.
"""
import json
import sys

GATED_SUBAGENT_TYPES = ("agent-tdd:agent-TDD", "agent-tdd:test-author")

# (field label as it should appear in the Slice Spec prompt, human-readable name for the
# deny reason)
REQUIRED_FIELDS = (
    ("Objective", "Objective"),
    ("Test Intent", "Test Intent"),
    ("Risk Tier", "Risk Tier"),
    ("Data Contracts", "Data Contracts And Interfaces"),
)


def allow():
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }}))
    sys.exit(0)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def no_decision():
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type") or ""
    if subagent_type not in GATED_SUBAGENT_TYPES:
        no_decision()

    prompt = tool_input.get("prompt") or ""
    missing = [name for marker, name in REQUIRED_FIELDS if marker not in prompt]
    if missing:
        deny(
            "SDD Slice Spec gate: the constructed Slice Spec for "
            f"{subagent_type} is missing required field(s): {', '.join(missing)} "
            "(see INTEROP.md's field mapping). Fill in the missing field(s) and retry."
        )

    allow()


if __name__ == "__main__":
    main()
