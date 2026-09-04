#!/usr/bin/env python3
"""PostToolUse hook: track which files get touched (Write/Edit/MultiEdit/Read)
across sessions in a lightweight `hotspots.json`, so nelly_session_start.py
can surface the top hotspots in the session-start brief.

Pure stdlib, zero LLM cost -- one JSON read + one JSON write per tool call,
no subprocess. Silent: no stdout, no logging, never blocks or reports
failure back to the tool call (PostToolUse cannot undo a tool call that
already happened, same convention as nelly_index_update.py).

`hotspots.json` lives at `<memory_dir>/hotspots.json`:
    {"files": {"<repo-relative-path>": {"count": N, "last_seen": "<iso>"}},
     "updated_at": "<iso>"}

Capped at MAX_FILES entries -- when a touch would push the count over the
cap, the least-recently-seen file(s) are evicted first, so the file stays a
bounded, fast read regardless of how many distinct files a long-running
project accumulates.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely, same convention as the other Nelly gate hooks.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_memory  # noqa: E402

MAX_FILES = 50
_TRACKED_TOOLS = ("Write", "Edit", "MultiEdit", "Read")


def _relative_path(cwd, file_path):
    if not file_path:
        return None
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    abspath = os.path.normpath(abspath)
    try:
        return os.path.relpath(abspath, cwd)
    except ValueError:
        return abspath  # different drive on Windows -- fall back to absolute


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("files"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"files": {}, "updated_at": None}


def _save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def _touch(data, rel_path, now):
    files = data["files"]
    entry = files.get(rel_path, {"count": 0, "last_seen": None})
    entry["count"] = entry.get("count", 0) + 1
    entry["last_seen"] = now
    files[rel_path] = entry

    if len(files) > MAX_FILES:
        ordered = sorted(files.items(), key=lambda kv: kv[1].get("last_seen") or "")
        for stale_path, _ in ordered[: len(files) - MAX_FILES]:
            del files[stale_path]

    data["updated_at"] = now
    return data


def _run():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        return

    payload = json.load(sys.stdin)
    if payload.get("tool_name") not in _TRACKED_TOOLS:
        return

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        return

    cwd = payload.get("cwd") or os.getcwd()
    rel = _relative_path(cwd, file_path)
    if not rel:
        return

    d = nelly_memory.memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    hotspots_path = os.path.join(d, "hotspots.json")

    now = datetime.datetime.now().replace(microsecond=0).isoformat()
    data = _load(hotspots_path)
    _touch(data, rel, now)
    _save(hotspots_path, data)


def main():
    try:
        _run()
    except Exception:
        pass  # never break the user's tool call
    sys.exit(0)


if __name__ == "__main__":
    main()
