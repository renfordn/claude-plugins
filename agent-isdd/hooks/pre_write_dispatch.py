#!/usr/bin/env python3
"""Single PreToolUse Write|Edit|MultiEdit|NotebookEdit entry point.

Cheap exit first: no active workflow -> exit 0, silent. Otherwise resolve the active
workflow-state.md once and run the guards (state_guard, complete_guard, user_led_guard) in
order, emitting a deny for the first reason returned. Fail open on any error.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _default_guards():
    import state_guard
    import complete_guard
    import user_led_guard
    return [state_guard.evaluate, complete_guard.evaluate, user_led_guard.evaluate]


def run(payload, state_path, guards=None):
    """First deny reason from the guards, else None. Each guard: fn(payload, state_path=...)."""
    for guard in (guards if guards is not None else _default_guards()):
        try:
            reason = guard(payload, state_path=state_path)
        except Exception:
            continue
        if reason:
            return reason
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            sys.exit(0)
        from sdd_state import active_state_file
        state_path = active_state_file(payload.get("cwd") or os.getcwd())
        if not state_path:
            sys.exit(0)
        reason = run(payload, state_path)
    except Exception:
        sys.exit(0)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    sys.exit(0)


if __name__ == "__main__":
    main()
