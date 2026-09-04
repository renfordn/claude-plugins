#!/usr/bin/env python3
"""SessionStart hook: announce this project's per-feature SDD spec-state directory
and surface any in-progress workflow so it can be resumed."""
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import find_state_files, parse_state  # noqa: E402
from sdd_memory import memory_dir  # noqa: E402


def _interruption_note(cwd):
    """Best-effort, display-only: note when a pre-compact snapshot exists that is
    newer than the last recorded normal Stop, suggesting this session is
    recovering from an interruption rather than resuming cleanly. Returns ""
    when there's nothing to say (matches this hook's additive-only convention).
    """
    d = memory_dir(cwd)
    snapshots = glob.glob(os.path.join(d, "snapshots", "*"))
    if not snapshots:
        return ""
    newest_snapshot = max(snapshots, key=os.path.getmtime)
    snapshot_mtime = os.path.getmtime(newest_snapshot)

    last_stop_path = os.path.join(d, "last-stop.json")
    last_stop_mtime = None
    if os.path.isfile(last_stop_path):
        last_stop_mtime = os.path.getmtime(last_stop_path)

    if last_stop_mtime is None or snapshot_mtime > last_stop_mtime:
        ts = datetime.datetime.fromtimestamp(snapshot_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"Note: a pre-compact snapshot exists from {ts} with no matching "
            f"normal stop since — this session may be recovering from an "
            f"interrupted prior session rather than a clean resume."
        )
    return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    lines = []

    # Always tell the session where this project's per-feature spec state lives
    # (workflow-state.md, recap.md, requirements/design/tasks), so every
    # subagent uses the literal absolute path (no env needed). Note: reads/
    # writes under spec/** are auto-approved by hooks/memory_permission.py —
    # no permission-prompt friction. Cross-feature, goal-bearing, and
    # cross-project memory lives in agent-nelly, not here.
    mem = memory_dir(cwd)
    lines.append(f"SDD per-feature state for this project: {mem}")

    note = _interruption_note(cwd)
    if note:
        lines.append("")
        lines.append(note)

    # Surface in-progress workflows, if any.
    files = find_state_files(cwd)
    if files:
        lines.append("")
        lines.append("Active spec-driven-development workflow(s) in this repo:")
        for path in files[:5]:
            f = parse_state(path)
            title = f.get("title", os.path.basename(os.path.dirname(path)))
            phase = f.get("current phase", "?")
            status = f.get("workflow status", "?")
            nxt = f.get("next action", "")
            entry = f"- {title}: phase '{phase}', status '{status}'."
            if nxt:
                entry += f" Next: {nxt}"
            json_path = os.path.join(os.path.dirname(path), "workflow-state.json")
            entry += " workflow-state.json: present." if os.path.isfile(json_path) else " workflow-state.json: absent."
            lines.append(entry)
        lines.append("Run /sdd-status for detail, or /sdd-continue to resume.")

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}))
    sys.exit(0)


if __name__ == "__main__":
    main()
