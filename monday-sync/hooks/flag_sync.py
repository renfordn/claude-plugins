#!/usr/bin/env python3
"""PostToolUse (Write|Edit|MultiEdit) hook: flag an isdd feature as needing a monday board sync.

When the written path is <...>/spec/<feature>/workflow-state.md, the feature dir (realpath) is
added to ${CLAUDE_PLUGIN_DATA}/store.json pending. If Current Phase or Workflow Status differs from
what the feature's monday.json last synced, additionalContext asks for the monday-sync skill (F8).

Stdlib only; depends only on store.py and fields.py.
Skips features opted out with `cli.py record --unlink`; while a sync is running (sidecar
`syncing_since` < 10 min old) it still flags but doesn't nudge. Fail-open: never blocks, always exits 0.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_STATE_PATH = re.compile(r"/spec/[^/]+/workflow-state\.md$")
_BASH_SPEC = re.compile(r"spec/(\d{4}-\d{2}-\d{2}-[A-Za-z0-9._-]+)")


SYNC_WINDOW_S = 600


def _syncing(sidecar):
    """True while a monday-sync run marked by `cli.py sync-begin` is under 10 minutes old."""
    since = sidecar.get("syncing_since")
    if not since:
        return False
    try:
        started = datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    age = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
    return 0 <= age < SYNC_WINDOW_S


def main():
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input") or {}
        path = (tool_input.get("file_path") or "").replace("\\", "/")
    except (ValueError, AttributeError):
        return
    if payload.get("tool_name") == "Bash":
        command = tool_input.get("command") or ""
        if "workflow-state" not in command:
            return
        import store
        if not store.store_path():
            return
        for slug in dict.fromkeys(_BASH_SPEC.findall(command)):
            for feature_dir in store.feature_dirs_for_slug(slug):
                flag(feature_dir)
        return
    if not _STATE_PATH.search(path):
        return
    flag(os.path.dirname(path))


def flag(feature_dir):
    import fields
    import store
    if not store.store_path():
        return
    sidecar = store.load_sidecar(feature_dir)
    if sidecar.get("unlinked"):
        return                                   # opted out with `cli.py record --unlink`
    store.add_pending(feature_dir)
    if _syncing(sidecar):
        return                                   # the running sync's own isdd_updates edit

    f = fields.read_fields(feature_dir)
    synced = sidecar.get("synced_fields") or {}
    phase, status = f.get("current phase"), f.get("workflow status")
    if phase == synced.get("phase") and status == synced.get("workflow_status"):
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (f"monday: {fields.feature_title(feature_dir, f)} changed phase/status "
                              f"(now {phase or '?'} / {status or '?'}) - run the monday-sync skill "
                              "to update the board."),
    }}))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open
        print(f"monday-sync flag_sync: {exc}", file=sys.stderr)
    sys.exit(0)
