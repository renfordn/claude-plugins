#!/usr/bin/env python3
"""PostToolUseFailure hook: detect a failed agent-nelly spawn (subagent_type not found) and clear
the stale `agent_nelly_available` cache in workflow-state.json, so the next Availability Check
(see workflow-manager/SKILL.md's "Availability Check" section) re-derives it instead of trusting a
stale SessionStart-time snapshot.

Corrected 2026-09-16: originally registered on PostToolUse, which never fires for this failure
mode -- a subagent_type-not-found rejection is a parameter-validation failure, so the Agent tool
never executes at all, and Claude Code's hooks docs are explicit that PostToolUse doesn't fire
when the tool never executes; PostToolUseFailure does. Confirmed live: an invalid subagent_type
surfaces as a hard tool-call-level error, not a completed tool result. This hook was effectively
dead code under its original registration.

Scope: `agent-nelly:agent-nelly` only. `agent-tdd:agent-TDD` is deliberately out of scope here --
per INTEROP.md's "Availability check" section, agent-tdd's availability is checked inline, once,
at the implementation handoff, and is never cached in workflow-state.json by design. There is no
corresponding field for this hook to clear, and introducing one would contradict that documented
decision -- a separate call for whoever owns that doc, not this hook.

UNVERIFIED PAYLOAD SHAPE: no real PostToolUseFailure payload for the Agent tool was available to
confirm this against (see the agent-tdd handoff report for this slice). Detection below is a
best-effort guess at Claude Code's PostToolUseFailure conventions -- an `is_error`-style truthy
field on `tool_response`, an `error` string containing "not found", or (when `tool_response` is a
string/list of content blocks instead of a dict) a case-insensitive substring match for "not
found" alongside the subagent_type string. It is deliberately conservative and fail-closed: any
payload shape that doesn't clearly match one of these is a no-op -- never a crash, never a
false-positive clear. CONFIRM/ADJUST THIS against a real harness
payload once one is available.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state_json, write_state_json  # noqa: E402

TARGET_SUBAGENT_TYPE = "agent-nelly:agent-nelly"


def _flatten_text(value):
    """Best-effort flatten of a str/list-of-content-blocks value into one lowercase string
    for substring matching. Returns "" for shapes we don't recognize, rather than guessing
    further -- callers treat "" as "no match" (fail-closed)."""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).lower()
    return ""


def _text_indicates_not_found(text):
    """Shared substring check for the two text-bearing shapes below -- both require "not
    found" alongside the target subagent_type name, never "not found" alone (too broad)."""
    return bool(text) and "not found" in text and TARGET_SUBAGENT_TYPE.lower() in text


def is_failed_spawn(tool_response):
    """True only when tool_response clearly indicates TARGET_SUBAGENT_TYPE wasn't found.
    Ambiguous or unrecognized shapes return False -- see module docstring's fail-closed note.
    """
    if isinstance(tool_response, dict):
        if tool_response.get("is_error") is True:
            return True
        error_field = tool_response.get("error")
        if isinstance(error_field, str) and "not found" in error_field.lower():
            return True
        return _text_indicates_not_found(_flatten_text(tool_response.get("content")))

    return _text_indicates_not_found(_flatten_text(tool_response))


def main(payload=None):
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}

    tool_input = payload.get("tool_input") or {}
    if tool_input.get("subagent_type") != TARGET_SUBAGENT_TYPE:
        return None

    if not is_failed_spawn(payload.get("tool_response")):
        return None

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        return None

    feature_dir = os.path.dirname(state)
    json_path = os.path.join(feature_dir, "workflow-state.json")
    data = parse_state_json(json_path)
    if data.get("agent_nelly_available") is not True:
        return None  # nothing stale to clear -- also covers a missing/unparseable file

    data["agent_nelly_available"] = False
    write_state_json(json_path, data)

    return (
        "SDD: detected a failed agent-nelly:agent-nelly spawn (subagent_type not found) -- "
        "cleared the stale agent_nelly_available cache in workflow-state.json. The next "
        "Availability Check will re-derive it instead of trusting the stale snapshot."
    )


if __name__ == "__main__":
    _msg = main()
    if _msg:
        print(json.dumps({"systemMessage": _msg}))
    sys.exit(0)
