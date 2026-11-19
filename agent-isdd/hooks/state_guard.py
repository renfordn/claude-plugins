#!/usr/bin/env python3
"""state_guard hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


_RISK_RANK = {"low": 0, "elevated": 1, "high": 2}
_GUARDED_TOOLS = ("Write", "Edit", "MultiEdit")
MAX_HOOK_HISTORY = 100


def _is_state_file(raw, cwd, state_path):
    """True when `raw` names the active workflow-state.md (file identity, not string compare)."""
    if not isinstance(raw, str) or not raw:
        return False
    path = os.path.join(cwd, os.path.expanduser(raw))
    try:
        return os.path.samestat(os.stat(path), os.stat(state_path))
    except OSError:
        return os.path.realpath(path) == os.path.realpath(state_path)


def _first_token(value):
    parts = value.strip().lower().split()
    return parts[0] if parts else ""


def _parse_text(text):
    from sdd_state import match_field
    fields = {}
    for line in text.splitlines():
        m = match_field(line)
        if m and m[0] not in fields:
            fields[m[0]] = m[1]
    return fields


def _log_mode_switch(state_path, old_mode, new_mode):
    import datetime
    from sdd_state import update_json
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def apply(data):
        history = data.setdefault("hook_history", [])
        if not isinstance(history, list):
            history = data["hook_history"] = []
        history.append({"hook": "state_guard/mode_switch", "outcome": "Attempted",
                        "from": old_mode, "to": new_mode, "timestamp": ts})
        del history[:-MAX_HOOK_HISTORY]
        return data

    update_json(os.path.join(os.path.dirname(os.path.abspath(state_path)), "workflow-state.json"), apply)


def evaluate(payload, state_path=None):
    """Return a deny reason (str) for a Track/Risk transition the write would make illegal,
    else None. `state_path` is the active workflow-state.md resolved by pre_write_dispatch.

    Denied: Track Standard->Fast; Track becoming Fast while Risk is not low; any Risk downgrade
    (low < elevated < high). Also logs (never denies) an `Implementation Mode` change as a
    hook_history entry in workflow-state.json. Only acts when the written file is the active
    workflow-state.md (file identity). Fails open on any missing/unparseable data."""
    if not state_path or not isinstance(payload, dict):
        return None
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool not in _GUARDED_TOOLS or not isinstance(tool_input, dict):
        return None
    cwd = payload.get("cwd") or os.getcwd()
    if not _is_state_file(tool_input.get("file_path"), cwd, state_path):
        return None
    from sdd_state import simulate_write
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            old_text = fh.read()
    except OSError:
        return None
    old = _parse_text(old_text)
    new = _parse_text(simulate_write(tool, tool_input, old_text))
    old_track, new_track = _first_token(old.get("track", "")), new.get("track", "").strip().lower()
    old_risk, new_risk = _first_token(old.get("risk", "")), new.get("risk", "").strip().lower()
    if old_track == "standard" and new_track != "standard":
        return ("Track cannot change from Standard (to %r). Only Fast -> Standard is a legal "
                "change; ask the user if the scope has really shrunk." % (new_track or "unset"))
    if _first_token(new.get("track", "")) == "fast" and new_risk not in ("", "low"):
        return ("Risk above low requires Track: Standard (Risk is %r) -- set Track: Standard in "
                "the same edit." % new_risk)
    if old_risk in _RISK_RANK and (new_risk not in _RISK_RANK
                                   or _RISK_RANK[new_risk] < _RISK_RANK[old_risk]):
        return ("Risk cannot be lowered, removed or made unrecognised (%s -> %s). Risk only goes "
                "up (low < elevated < high); ask the user if the assessment was wrong."
                % (old_risk, new_risk or "unset"))
    old_mode, new_mode = old.get("implementation mode", ""), new.get("implementation mode", "")
    if old_mode.strip().lower() != new_mode.strip().lower():
        try:
            _log_mode_switch(state_path, old_mode, new_mode)
        except Exception:
            pass
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    try:
        evaluate(payload if isinstance(payload, dict) else {})
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
