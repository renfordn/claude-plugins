#!/usr/bin/env python3
"""Stop hook: non-blocking reminder when the active workflow is paused on a blocker.

Only speaks up when a workflow is Blocked or Awaiting Confirmation, so it stays
quiet during normal work. Never blocks the stop.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state  # noqa: E402
from sdd_memory import memory_dir  # noqa: E402


def _write_last_stop_marker(cwd):
    """Record 'the last time a session ended normally' so SessionStart can tell
    a clean resume apart from recovering after an interrupted session. Additive
    and best-effort — never affects Stop's control flow."""
    try:
        d = memory_dir(cwd)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last-stop.json"), "w", encoding="utf-8") as fh:
            json.dump({"timestamp": datetime.datetime.now().isoformat()}, fh)
    except OSError:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        sys.exit(0)

    _write_last_stop_marker(cwd)

    f = parse_state(state)
    status = f.get("workflow status", "").lower()
    if "block" in status or "await" in status or "confirm" in status:
        title = f.get("title", "the active feature")
        pause_reason = f.get("pause reason", "").strip()
        next_action = f.get("next action", "").strip()
        if pause_reason and next_action:
            detail = f"{pause_reason}. Next: {next_action}"
        else:
            detail = pause_reason or next_action or "see workflow-state.md"
        print(json.dumps({
            "systemMessage": (
                f"SDD reminder: '{title}' is paused ({f.get('workflow status', '?')}) — "
                f"{detail}. Run /sdd-continue when ready."
            )
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
