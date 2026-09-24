#!/usr/bin/env python3
"""PreToolUse gate: deny spawning agent-tdd:agent-TDD / agent-tdd:test-author unless the
constructed Slice Spec looks complete, per INTEROP.md's field mapping.

History: originally written pre-Phase-2+3 for every agent-tdd:agent-TDD/test-author spawn,
then disabled entirely (removed from hooks.json) once Phase 2+3 made the Design Spec handoff
(a full requirements.md/design.md/research/cache.md payload, not field-labeled Slice Spec
text) the normal path -- applying this gate's field checks to a Design Spec prompt would deny
every spawn, since a Design Spec has no "Task description"/"Test Intent" labels at all.

Re-enabled 2026-09-17 for `Track: Fast` (see spec-driven-development/SKILL.md's "Fast Track"
section), which reintroduces a genuine single-slice Slice Spec handoff. Only `agent-tdd:
agent-TDD`'s prompt shape is ambiguous between the two tracks (Design Spec vs. Slice Spec), so
only that subagent_type is `Track`-gated: this hook reads the active feature's `Track` first
and no-ops immediately for `Track: Standard` (or no active workflow) before ever looking at
its prompt -- it never guesses which spec shape it's looking at from prompt content alone.
`agent-tdd:test-author` carries no such ambiguity -- it is never spawned with a Design Spec in
either track, so its field check always applies, `Track` notwithstanding.

Mirrors commit_audit_gate.py's verify-then-allow/deny pattern -- the one other hard gate in
this plugin. Deliberately scoped to exactly these two subagent_type values so it can never
misfire on an unrelated Task call; every other spawn passes through untouched. This is the
one hook point in the "sibling-plugin hook reliability" feature where a hard gate is
justified (see design.md's Risks And Tradeoffs) -- the Implementation Handoff is a single,
narrowly-scoped, consequential call, unlike routine phase-transition writes.

The check is deliberately shallow (field-name presence in the prompt text), not a full
parse: a hook can't semantically judge Slice Spec quality, only whether the required
sections were included at all.

Caution (see path_resolution.py's "identity-split hazard"): the Track: Fast detection below
resolves active_state_file(cwd), which is identity-scoped. If the active feature's state lives
under a different plugin identity's data dir than this hook resolves to this session, this
falls through as "no active workflow" -- Track: Fast's field check is silently skipped rather
than applied. Lower-severity than design_spec_gate.py's equivalent gap (a skipped field check,
not an unapproved implementation spawn), but the same underlying gap.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state  # noqa: E402

# (field label as it should appear in the Slice Spec prompt, human-readable name for the
# deny reason). Per agent-tdd/skills/slice-spec/SKILL.md's own field-subset rule, a
# test-author spawn deliberately omits Risk Tier (an agent-TDD-only concern), so it gets its
# own, narrower required-field list rather than sharing agent-TDD's four.
REQUIRED_FIELDS_BY_SUBAGENT_TYPE = {
    "agent-tdd:agent-TDD": (
        ("Task description", "Task description"),
        ("Test Intent", "Test Intent"),
        ("Risk Tier", "Risk Tier"),
        ("Data Contracts", "Data Contracts And Interfaces"),
    ),
    "agent-tdd:test-author": (
        ("Task description", "Task description"),
        ("Test Intent", "Test Intent"),
        ("Data Contracts", "Data Contracts And Interfaces"),
    ),
}


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
    required_fields = REQUIRED_FIELDS_BY_SUBAGENT_TYPE.get(subagent_type)
    if required_fields is None:
        no_decision()

    # agent-tdd:agent-TDD's prompt shape is genuinely ambiguous: Track: Standard sends a
    # Design Spec (full requirements.md/design.md/research/cache.md, no field labels at all)
    # that this gate must never evaluate -- see the module docstring for why. So only apply
    # its field check when the workflow itself says it's looking at a Slice Spec (Track: Fast).
    #
    # agent-tdd:test-author is not ambiguous the same way -- it is never spawned with a Design
    # Spec in either track. Both Standard's own high-risk path (spec-driven-development/
    # SKILL.md's Standard step 6) and Fast Track's (its step 4) pass it the identical
    # field-labeled Task description/Test Intent/Data Contracts And Interfaces subset per
    # agent-tdd/INTEROP.md's field-subset rule, so its check applies regardless of Track.
    if subagent_type == "agent-tdd:agent-TDD":
        cwd = payload.get("cwd") or os.getcwd()
        state_path = active_state_file(cwd)
        if not state_path:
            no_decision()
        track = parse_state(state_path).get("track", "standard").strip().lower()
        if track != "fast":
            no_decision()

    prompt = tool_input.get("prompt") or ""
    missing = [name for marker, name in required_fields if marker not in prompt]
    if missing:
        deny(
            "SDD Slice Spec gate: the constructed Slice Spec for "
            f"{subagent_type} is missing required field(s): {', '.join(missing)} "
            "(see INTEROP.md's field mapping). Fill in the missing field(s) and retry."
        )

    allow()


if __name__ == "__main__":
    main()
