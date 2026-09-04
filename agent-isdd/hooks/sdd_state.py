"""Shared helpers for SDD hooks: locate and parse the active workflow-state.md.

Kept dependency-free (stdlib only) so it runs under any python3.

Note: workflow-state.md lives under the central memory dir (see sdd_memory.memory_dir),
not under <root>/spec/*/. A legacy repo-local spec/ directory from before this convention
change is not migrated or supported by find_state_files/active_state_file -- none exist in
this canonical repo.
"""
import glob
import json
import os
import re

from sdd_memory import memory_dir


def find_state_files(root):
    """Return workflow-state.md paths under <memory_dir(root)>/spec/*/ sorted newest-first."""
    pattern = os.path.join(memory_dir(root), "spec", "*", "workflow-state.md")
    files = glob.glob(pattern)
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def active_state_file(root):
    """Most recently modified workflow-state.md under memory_dir(root), or None."""
    files = find_state_files(root)
    return files[0] if files else None


def parse_state(path):
    """Parse the `- Field: value` lines of a workflow-state.md into a dict.

    Keys are lowercased field names, e.g. 'current phase', 'implementation requested'.
    """
    fields = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return fields
    for line in text.splitlines():
        m = re.match(r"\s*[-*]\s*([A-Za-z][A-Za-z /]+?):\s*(.*\S)?\s*$", line)
        if m:
            key = m.group(1).strip().lower()
            val = (m.group(2) or "").strip()
            if key not in fields:
                fields[key] = val
    return fields


def parse_state_json(path):
    """Load workflow-state.json into a dict, tolerant of a missing or malformed file.

    Mirrors parse_state's tolerant-failure behavior for the .md sibling: never raises,
    returns {} when the file can't be read or parsed.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_state_json(path, data):
    """Write a workflow-state.json dict back to disk. Shared by every hook that mutates it,
    so the on-disk formatting (2-space indent, trailing newline) stays consistent."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def write_rollback_pending(path, target, reason, source):
    """Set workflow-state.json's rollback_pending field, preserving other fields.

    Creates the file if it doesn't exist yet -- workflow-state.json is normally scaffolded
    alongside workflow-state.md, but a hook must not crash if it's momentarily missing.
    """
    data = parse_state_json(path)
    data["rollback_pending"] = {"target": target, "reason": reason, "source": source}
    write_state_json(path, data)


def read_rollback_pending(path):
    """Return the rollback_pending dict, or None when absent (no pending rollback)."""
    return parse_state_json(path).get("rollback_pending")


def clear_rollback_pending(path):
    """Remove rollback_pending from workflow-state.json. No-op if file or field is missing."""
    data = parse_state_json(path)
    if "rollback_pending" not in data:
        return
    del data["rollback_pending"]
    write_state_json(path, data)


def is_pre_implementation(fields):
    """True when the workflow has NOT yet been approved for implementation."""
    impl = fields.get("implementation requested", "").strip().lower()
    status = fields.get("workflow status", "").strip().lower()
    if impl in ("yes", "y", "true"):
        return False
    if "complete" in status or "implement" in status and "await" not in status:
        # e.g. "Implementing" or "Complete" -> gate is open
        return False
    return True
