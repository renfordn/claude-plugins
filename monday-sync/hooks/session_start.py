#!/usr/bin/env python3
"""SessionStart hook: tell the model which isdd features still need a monday board sync.

Silent when nothing is pending. Stdlib only; fail-open, always exits 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAX_TITLES = 5


def main():
    import fields
    import store
    if not store.store_path():
        return
    for d in store.drifted_features():
        store.add_pending(d)               # backstop for state changed outside Edit/Write
    pending = store.list_pending()
    if not pending:
        return
    n = len(pending)
    lines = [f"monday: {n} feature{'s' if n != 1 else ''} need board sync - run the monday-sync skill."]
    lines += [f"- {fields.feature_title(d)} ({d})" for d in pending[:MAX_TITLES]]
    if n > MAX_TITLES:
        lines.append(f"- ...and {n - MAX_TITLES} more (cli.py pending list)")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open
        print(f"monday-sync session_start: {exc}", file=sys.stderr)
    sys.exit(0)
