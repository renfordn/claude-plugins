"""Shared helpers for SDD hooks: locate and parse the active workflow-state.md.

Kept dependency-free (stdlib only) so it runs under any python3.

Note: workflow-state.md lives under the central memory dir (see sdd_memory.memory_dir),
not under <root>/spec/*/. A legacy repo-local spec/ directory from before this convention
change is not migrated or supported by find_state_files/active_state_file -- none exist in
this canonical repo.

Caution: every function here is discovery-based -- it locates state via memory_dir(cwd), never
via an explicit path handed to it in a hook's own PreToolUse/PostToolUse/SubagentStop payload.
memory_dir() is `${CLAUDE_PLUGIN_DATA}`-based and therefore plugin-identity-scoped (see
path_resolution.py's "identity-split hazard"): a caller of find_state_files/active_state_file
running under one identity's env var will not see state written under a different identity's
data dir, and gets exactly the same empty result as "no workflow is active at all." Every hook
in this plugin that calls these functions inherits that caveat.
"""
import glob
import json
import os
import re

from sdd_memory import memory_dir

# Entries retained in workflow-state.json's escalation_history (oldest dropped first).
MAX_ESCALATION_HISTORY = 50


def is_complete_state(path):
    """True when a workflow-state.md's `- Workflow Status:` field is `Complete`.

    A finished feature must drop out of discovery -- otherwise, as the newest-mtime
    workflow-state.md, it stays "active" forever and every later hook run (in unrelated
    sessions) keeps writing into its folder.
    """
    return parse_state(path).get("workflow status", "").strip().lower() == "complete"


def find_state_files(root):
    """Return non-Complete workflow-state.md paths under <memory_dir(root)>/spec/*/, newest-first."""
    pattern = os.path.join(memory_dir(root), "spec", "*", "workflow-state.md")
    files = [p for p in glob.glob(pattern) if not is_complete_state(p)]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def active_state_file(root):
    """Most recently modified non-Complete workflow-state.md under memory_dir(root), or None."""
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


def write_test_author_pending(path, slices, detected_at):
    """Set workflow-state.json's test_author_pending field, preserving other fields.

    `slices` is a list of {"name": str, "files": [str, ...]} dicts -- one per high-risk
    slice detected at agent-tdd's slicing_complete checkpoint (see high_risk_reviewer.py).
    Creates the file if it doesn't exist yet, mirroring write_rollback_pending's
    tolerant-of-missing-file behavior.
    """
    data = parse_state_json(path)
    data["test_author_pending"] = {"slices": slices, "detected_at": detected_at}
    write_state_json(path, data)


def clear_test_author_pending(path):
    """Remove test_author_pending from workflow-state.json. No-op if file or field missing."""
    data = parse_state_json(path)
    if "test_author_pending" not in data:
        return
    del data["test_author_pending"]
    write_state_json(path, data)


def clear_rollback_pending(path):
    """Remove rollback_pending from workflow-state.json. No-op if file or field is missing."""
    data = parse_state_json(path)
    if "rollback_pending" not in data:
        return
    del data["rollback_pending"]
    write_state_json(path, data)


def read_escalation_pending(path):
    """Return the escalation_pending dict, or None when absent (no pending escalation)."""
    return parse_state_json(path).get("escalation_pending")


def write_escalation_pending(path, escalation):
    """Set workflow-state.json's escalation_pending field, preserving other fields."""
    data = parse_state_json(path)
    data["escalation_pending"] = escalation
    write_state_json(path, data)


def clear_escalation_pending(path):
    """Remove escalation_pending from workflow-state.json. No-op if file or field is missing."""
    data = parse_state_json(path)
    if "escalation_pending" not in data:
        return
    del data["escalation_pending"]
    write_state_json(path, data)


def write_escalation_outcome(path, entry):
    """Append `entry` to workflow-state.json's escalation_history list, creating the list if
    absent, and clear escalation_pending in the same write -- mirrors write_rollback_pending's
    tolerant-of-missing-file behavior, but appends rather than overwrites (escalation history is
    a durable audit trail; see design.md's Data Contracts And Interfaces), capped at the most
    recent MAX_ESCALATION_HISTORY entries.

    `entry` is expected to be {reason, from_model, to_model, detected_at, outcome, resolved_at}.
    """
    data = parse_state_json(path)
    history = data.get("escalation_history")
    if not isinstance(history, list):
        history = []
    history.append(entry)
    data["escalation_history"] = history[-MAX_ESCALATION_HISTORY:]
    if "escalation_pending" in data:
        del data["escalation_pending"]
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
