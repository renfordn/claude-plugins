#!/usr/bin/env python3
"""Stop hook: non-blocking reminder when the active workflow is paused or stalled.

Detects two conditions:
1. Explicit pause: workflow status contains "block", "await", or "confirm"
2. Mid-workflow stall: a phase marked Complete but next phase not yet entered

Never blocks the stop.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state  # noqa: E402
from sdd_memory import memory_dir  # noqa: E402


PHASE_ORDER = ["Requirements", "Design", "Tasks"]  # Expected phase progression
PHASE_FILES = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
    "Tasks": "tasks/tasks.md",
}


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


def _detect_stalled_phase(state_fields, feature_dir):
    """Check if a phase is marked Complete but next phase hasn't been entered.

    Returns (is_stalled, phase_name, next_phase) or (False, None, None).
    """
    current = state_fields.get("current phase", "").strip()
    status = state_fields.get("workflow status", "").lower()

    # Find current phase in order
    for i, phase in enumerate(PHASE_ORDER):
        if current.startswith(phase):
            # Current phase detected at position i
            # Check if phase is marked as complete
            if "complete" in status:
                # Check if next phase file exists (entry has been attempted)
                if i + 1 < len(PHASE_ORDER):
                    next_phase = PHASE_ORDER[i + 1]
                    next_file = os.path.join(
                        feature_dir,
                        PHASE_FILES[next_phase]
                    )
                    if not os.path.exists(next_file):
                        # Phase complete but next not entered — workflow stalled
                        return (True, phase, next_phase)
            break

    return (False, None, None)


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
    title = f.get("title", "the active feature")
    status = f.get("workflow status", "").lower()
    feature_dir = os.path.dirname(state)

    # Check for explicit pause (block/await/confirm)
    if "block" in status or "await" in status or "confirm" in status:
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

    # Check for stalled phase (completed but next not entered)
    is_stalled, phase_name, next_phase = _detect_stalled_phase(f, feature_dir)
    if is_stalled:
        print(json.dumps({
            "systemMessage": (
                f"⚠️  SDD workflow stalled: '{title}'\n\n"
                f"**Phase {phase_name} marked Complete** but **{next_phase} phase not yet entered**.\n\n"
                f"This likely means the orchestrator provided guidance/decisions and stopped its turn "
                f"before invoking the next phase. Run `/sdd-continue` to resume and advance to {next_phase}."
            )
        }))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
