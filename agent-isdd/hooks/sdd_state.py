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
import tempfile

try:
    import fcntl
except ImportError:  # non-POSIX: fall back to atomic replace without a lock (fail open)
    fcntl = None

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


# Fields a workflow-state.md may also write without the leading `- ` (hand-written or older files).
# Only these are read in bare form, so ordinary prose like "Note: ..." is never mistaken for a field.
BARE_FIELDS = frozenset((
    "feature", "title", "slug", "goal", "date", "track", "current phase", "previous phase",
    "workflow status", "pause reason", "next action", "implementation requested", "recap",
    "risk", "risk reason", "implementation mode", "approval hash", "review fallback",
))
_BULLET_FIELD = re.compile(r"^\s*[-*]\s*([A-Za-z][A-Za-z /]+?):\s*(.*\S)?\s*$")
_BARE_FIELD = re.compile(r"^([A-Za-z][A-Za-z /]+?):\s*(.*\S)?\s*$")


def match_field(line):
    """(lowercased key, value) for a `- Field: value` line or a bare `Field: value` line naming a
    BARE_FIELDS key; None otherwise."""
    m = _BULLET_FIELD.match(line)
    if not m:
        m = _BARE_FIELD.match(line)
        if not m or m.group(1).strip().lower() not in BARE_FIELDS:
            return None
    return m.group(1).strip().lower(), (m.group(2) or "").strip()


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
        m = match_field(line)
        if m:
            key, val = m
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


def locked_rewrite_text(path, fn, prefix=".tmp-", errors="strict"):
    """Locked, atomic read-modify-write of a text file: `fn(current_text) -> new_text` ("" when the
    file is missing). A sidecar `<path>.lock` flock serializes writers; the new content goes to a
    mkstemp file in the same directory and is os.replace'd in, preserving the file mode. Returns
    the new text. Undecodable content raises (`errors` is the decoding policy) so a caller never
    silently wipes a file it could not read."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    lock = None
    try:
        if fcntl is not None:
            lock = open(path + ".lock", "a")
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path, "r", encoding="utf-8", errors=errors) as fh:
                current = fh.read()
        except OSError:
            current = ""
        try:
            mode = os.stat(path).st_mode & 0o777
        except OSError:
            mode = 0o644
        text = fn(current)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=prefix)
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return text
    finally:
        if lock is not None:
            lock.close()


def update_json(path, fn):
    """Locked, atomic read-modify-write of a JSON file. Missing/corrupt/non-dict -> {}.
    Returns the new data."""
    result = []

    def _rewrite(text):
        try:
            data = json.loads(text)
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data = fn(data)
        result.append(data)
        return json.dumps(data, indent=2) + "\n"

    locked_rewrite_text(path, _rewrite, errors="replace")  # non-UTF-8 reads as corrupt -> {}
    return result[0]


def write_state_json(path, data):
    """Write a workflow-state.json dict back to disk (atomic, locked; 2-space indent, trailing
    newline). Shared by every hook that mutates it."""
    update_json(path, lambda _old: data)


def _drop_key(path, key):
    """Remove `key` under the lock; a missing file stays missing."""
    if os.path.exists(path):
        update_json(path, lambda d: {k: v for k, v in d.items() if k != key})


def write_rollback_pending(path, target, reason, source):
    """Set workflow-state.json's rollback_pending field, preserving other fields.

    Creates the file if it doesn't exist yet -- workflow-state.json is normally scaffolded
    alongside workflow-state.md, but a hook must not crash if it's momentarily missing.
    """
    update_json(path, lambda d: dict(d, rollback_pending={"target": target, "reason": reason,
                                                          "source": source}))


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
    update_json(path, lambda d: dict(d, test_author_pending={"slices": slices,
                                                             "detected_at": detected_at}))


def clear_test_author_pending(path):
    """Remove test_author_pending from workflow-state.json. No-op if file or field missing."""
    _drop_key(path, "test_author_pending")


def clear_rollback_pending(path):
    """Remove rollback_pending from workflow-state.json. No-op if file or field is missing."""
    _drop_key(path, "rollback_pending")


def read_escalation_pending(path):
    """Return the escalation_pending dict, or None when absent (no pending escalation)."""
    return parse_state_json(path).get("escalation_pending")


def write_escalation_pending(path, escalation):
    """Set workflow-state.json's escalation_pending field, preserving other fields."""
    update_json(path, lambda d: dict(d, escalation_pending=escalation))


def clear_escalation_pending(path):
    """Remove escalation_pending from workflow-state.json. No-op if file or field is missing."""
    _drop_key(path, "escalation_pending")


def write_escalation_outcome(path, entry):
    """Append `entry` to workflow-state.json's escalation_history list, creating the list if
    absent, and clear escalation_pending in the same write -- mirrors write_rollback_pending's
    tolerant-of-missing-file behavior, but appends rather than overwrites (escalation history is
    a durable audit trail; see design.md's Data Contracts And Interfaces), capped at the most
    recent MAX_ESCALATION_HISTORY entries.

    `entry` is expected to be {reason, from_model, to_model, detected_at, outcome, resolved_at}.
    """
    def _fn(data):
        history = data.get("escalation_history")
        if not isinstance(history, list):
            history = []
        history.append(entry)
        data["escalation_history"] = history[-MAX_ESCALATION_HISTORY:]
        data.pop("escalation_pending", None)
        return data

    update_json(path, _fn)


def is_user_led(fields):
    """True when `Implementation Mode` is user (lowercased first token, like Track/Risk)."""
    tokens = (fields or {}).get("implementation mode", "").strip().lower().split()
    return bool(tokens) and tokens[0] == "user"


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



def simulate_write(tool_name, tool_input, current_text):
    """Post-write text for a Write, Edit (old/new/replace_all) or MultiEdit tool call.

    `current_text` is the file's text before the call ("" if it does not exist). Unknown tools
    and edits whose old_string is absent leave the text unchanged (fail open).
    """
    tool_input = tool_input or {}
    current_text = current_text or ""
    if tool_name == "Write":
        return tool_input.get("content", "")

    def _apply(text, edit):
        """New text, or None when the real tool would reject the edit."""
        old = edit.get("old_string", "")
        new = edit.get("new_string", "")
        if old == "":
            return new if text == "" else None
        count = text.count(old)
        if count == 0:
            return None
        if edit.get("replace_all"):
            return text.replace(old, new)
        if count > 1:
            return None  # non-unique without replace_all: the real tool errors
        return text.replace(old, new, 1)

    if tool_name == "Edit":
        out = _apply(current_text, tool_input)
        return current_text if out is None else out
    if tool_name == "MultiEdit":
        text = current_text
        for edit in tool_input.get("edits") or []:
            text = _apply(text, edit)
            if text is None:
                return current_text  # all-or-nothing
        return text
    return current_text


def read_reviewed(path):
    """The reviewed map ({slice_id: True}) from workflow-state.json; {} when absent."""
    reviewed = parse_state_json(path).get("reviewed")
    return reviewed if isinstance(reviewed, dict) else {}


def mark_reviewed(path, slice_id):
    """Persist `slice_id` as reviewed in workflow-state.json, preserving other fields."""
    def _fn(data):
        reviewed = data.get("reviewed")
        if not isinstance(reviewed, dict):
            reviewed = {}
        reviewed[str(slice_id)] = True
        data["reviewed"] = reviewed
        return data

    update_json(path, _fn)


def read_baseline(path):
    """The baseline dict ({branch, head, dirty_files}) or None when never recorded."""
    baseline = parse_state_json(path).get("baseline")
    return baseline if isinstance(baseline, dict) else None


def write_baseline(path, branch, head, dirty_files):
    """Store the {branch, head, dirty_files} baseline in workflow-state.json."""
    baseline = {"branch": branch, "head": head, "dirty_files": list(dirty_files or [])}
    update_json(path, lambda d: dict(d, baseline=baseline))


# Phases whose own artifact `- State: Approved` should be followed by entering the next phase.
# Tasks is not a real next phase on the Design -> Implementation handoff (agent-tdd slices
# internally; no tasks.md is produced), so Design-approved with no tasks.md is NOT a stall.
_STALL_PHASE_ORDER = ["Requirements", "Design", "Tasks"]
_STALL_ARTIFACT = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
}
_STALL_NEXT_FILE = {
    "Design": "design/design.md",
}


def detect_stall(fields, feature_dir):
    """(phase, next_phase) when the current phase's artifact is Approved but the next phase
    was not entered; False otherwise. Only Requirements -> Design can stall: Design -> Tasks
    never needs a tasks.md, so design-approved/no-tasks.md is not a stall."""
    current = (fields or {}).get("current phase", "").strip()
    for i, phase in enumerate(_STALL_PHASE_ORDER):
        if not current.startswith(phase):
            continue
        artifact = _STALL_ARTIFACT.get(phase)
        if not artifact or i + 1 >= len(_STALL_PHASE_ORDER):
            return False
        next_phase = _STALL_PHASE_ORDER[i + 1]
        next_rel = _STALL_NEXT_FILE.get(next_phase)
        if not next_rel:
            return False
        state = parse_state(os.path.join(feature_dir, artifact)).get("state", "").strip().lower()
        if state == "approved" and not os.path.exists(os.path.join(feature_dir, next_rel)):
            return (phase, next_phase)
        return False
    return False
