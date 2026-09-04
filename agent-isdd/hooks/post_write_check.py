#!/usr/bin/env python3
"""PostToolUse hook: single entry-point combining the two previously separate
hooks (phase_task_sync.py + state_consistency_check.py) that fired on every
Write/Edit/MultiEdit/NotebookEdit. Running one Python process instead of two
halves subprocess startup overhead on every file write in the session.

Behaviour is unchanged from the two originals, plus one additive sync:
  - workflow-state.md writes: sync mirrored fields to workflow-state.json
    (silently, authoritative writer per workflow-manager's Write Responsibilities
    section), mirror the same fields into a lightweight `.sdd-state.json` at the
    project root (cwd) so other tools can cheaply read current phase without
    parsing markdown or reaching into ~/.claude/sdd-memory, then remind the model
    to sync the visible progress UI.
  - tasks/tasks.md writes: remind the model to sync the visible progress UI.
  - All other paths: silent no-op, exit 0.

Both JSON syncs are silent (no systemMessage) on normal operation; the
hook_history entry in workflow-state.json serves as the audit trail for the
memory-dir copy. `.sdd-state.json` is a plain mirror with no history of its own.
The UI sync reminder fires for both watched paths and produces a single
systemMessage.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import parse_state, parse_state_json, write_state_json  # noqa: E402

PHASE_TASK_SUFFIXES = ("workflow-state.md", "tasks/tasks.md")

FIELD_MAP = {
    "current phase": "current_phase",
    "workflow status": "phase_state",
    "pause reason": "pause_reason",
    "implementation requested": "implementation_requested",
}


def _sync_json(file_path):
    """Sync mirrored fields from workflow-state.md into workflow-state.json.
    Silent on success; no-ops gracefully on any IO or parse failure.
    """
    if not os.path.isfile(file_path):
        return

    json_path = os.path.join(os.path.dirname(file_path), "workflow-state.json")
    if not os.path.isfile(json_path):
        return  # no paired .json -- not this hook's job to fabricate one

    md_fields = parse_state(file_path)
    json_fields = parse_state_json(json_path)

    updates = {}
    for md_key, json_key in FIELD_MAP.items():
        md_val = md_fields.get(md_key)
        if md_val is None:
            continue
        if json_fields.get(json_key) != md_val:
            updates[json_key] = md_val

    if not updates:
        return  # nothing to sync

    for json_key, md_val in updates.items():
        json_fields[json_key] = md_val

    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    json_fields["last_updated"] = ts
    history = json_fields.setdefault("hook_history", [])
    history.append({
        "hook": "post_write_check/state_sync",
        "outcome": "Synced",
        "fields": sorted(updates.keys()),
        "timestamp": ts,
    })
    write_state_json(json_path, json_fields)


def _write_root_state(cwd, md_fields):
    """Mirror the same fields into <cwd>/.sdd-state.json -- additive to the memory-dir
    workflow-state.json sync above, never a replacement. Lets other tools cheaply read
    current phase without parsing workflow-state.md or resolving the memory dir.
    """
    if not cwd or not md_fields:
        return

    data = {
        json_key: md_fields[md_key]
        for md_key, json_key in FIELD_MAP.items()
        if md_fields.get(md_key) is not None
    }
    if not data:
        return

    data["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    write_state_json(os.path.join(cwd, ".sdd-state.json"), data)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    norm = file_path.replace("\\", "/")

    is_state = norm.endswith("workflow-state.md")
    is_watched = is_state or norm.endswith("tasks/tasks.md")

    if not is_watched:
        sys.exit(0)

    if is_state:
        _sync_json(file_path)
        _write_root_state(payload.get("cwd"), parse_state(file_path))

    print(json.dumps({
        "systemMessage": (
            "SDD: a phase/slice artifact was written. On phase transitions, "
            "delegate to agent-ux:ux-agent (phase_transition envelope). Sync "
            "the TaskCreate/TaskUpdate/TaskList checklist directly from the "
            "calling skill (agent-ux:ux-agent's subagent context can't reach "
            "those deferred tools) — see INTEROP.md's \"-> agent-ux (UX "
            "rendering)\" section."
        )
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
