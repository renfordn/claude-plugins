#!/usr/bin/env python3
"""SubagentStop hook: after an agent-TDD or code-reviewer report, flag linked features whose
implementation progress (agent-isdd's impl-progress.json) or state moved since the last sync.

Implementation work doesn't touch workflow-state.md between slices, so the Edit/Write/Bash flag
never fired during it. Stdlib only; fail-open, always exits 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MARKERS = ("<!--AGENT-TDD-REPORT-->", "<!--CODE-REVIEWER-REPORT-->")


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    message = payload.get("last_assistant_message") or ""
    if not any(m in message for m in MARKERS):
        return
    import fields
    import store
    if not store.store_path():
        return
    pending = set(store.load_store()["pending"])
    new = [d for d in store.drifted_features() if os.path.realpath(d) not in pending]
    for d in new:
        store.add_pending(d)
    if new:
        names = ", ".join(fields.feature_title(d) for d in new[:3])
        print(json.dumps({"systemMessage": f"monday: implementation moved on {names} - run the "
                                           "monday-sync skill to update the board."}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open
        print(f"monday-sync subagent_stop: {exc}", file=sys.stderr)
    sys.exit(0)
