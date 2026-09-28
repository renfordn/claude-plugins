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
from sdd_memory import local_state_dir  # noqa: E402


PHASE_ORDER = ["Requirements", "Design", "Tasks"]  # Expected phase progression
PHASE_FILES = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
    "Tasks": "tasks/tasks.md",
}
# Phases that have a completion gate of their own (an artifact with a `- State:` field the
# orchestrator sets to Approved). Tasks has no such artifact-level gate here -- see
# workflow-manager's `continue` row: `Current Phase: Tasks` only ever arises as a rollback
# landing state, not a phase this hook watches for stalling out of.
PHASE_ARTIFACT_FILE = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
}


def _write_last_stop_marker(cwd):
    """Record 'the last time a session ended normally' so SessionStart can tell
    a clean resume apart from recovering after an interrupted session. Additive
    and best-effort — never affects Stop's control flow."""
    try:
        d = local_state_dir(cwd)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last-stop.json"), "w", encoding="utf-8") as fh:
            json.dump({"timestamp": datetime.datetime.now().isoformat()}, fh)
    except OSError:
        pass


def _detect_stalled_phase(state_fields, feature_dir):
    """Check if the current phase's own artifact is Approved but the next phase hasn't
    been entered.

    `Workflow Status: Complete` is NOT the per-phase completion signal -- per
    workflow-manager's contract it is set only once, at the whole feature's final
    handoff/completion, never for an individual phase finishing mid-workflow. The real
    per-phase signal is the phase artifact's own `- State: Approved` field (set by
    requirements-agent/design-author immediately on approval), which is exactly what stays
    true while the orchestrator has provided guidance at a phase boundary and stalled before
    invoking the next phase in the same turn.

    Returns (is_stalled, phase_name, next_phase) or (False, None, None).
    """
    current = state_fields.get("current phase", "").strip()

    # Find current phase in order
    for i, phase in enumerate(PHASE_ORDER):
        if current.startswith(phase):
            artifact_file = PHASE_ARTIFACT_FILE.get(phase)
            if artifact_file and i + 1 < len(PHASE_ORDER):
                artifact_path = os.path.join(feature_dir, artifact_file)
                artifact_state = parse_state(artifact_path).get("state", "").strip().lower()
                if artifact_state == "approved":
                    next_phase = PHASE_ORDER[i + 1]
                    next_file = os.path.join(feature_dir, PHASE_FILES[next_phase])
                    if not os.path.exists(next_file):
                        # Phase's artifact approved but next phase not entered — stalled
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
                f"{detail}. Run /isdd-continue when ready."
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
                f"before invoking the next phase. Run `/isdd-continue` to resume and advance to {next_phase}."
            )
        }))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
