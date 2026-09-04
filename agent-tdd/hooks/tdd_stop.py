#!/usr/bin/env python3
"""Stop hook: write last-stop.json and warn if any slices are pending review."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdd_state import read_tdd_progress, write_last_stop  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()

    write_last_stop(cwd)  # best-effort, silently ignores OSError

    data = read_tdd_progress(cwd)
    pending = [s for s in data["slices"] if s.get("status") == "green_pending_review"]

    if not pending:
        sys.exit(0)

    items = "\n".join(f"  - [{s['id']}] {s['description']}" for s in pending)
    print(json.dumps({"systemMessage": (
        f"agent-TDD: {len(pending)} slice(s) awaiting review resume at session end:\n"
        f"{items}\n"
        "Resume via SendMessage to the agent-TDD instance id, or re-spawn with the same Slice Spec."
    )}))
    sys.exit(0)


if __name__ == "__main__":
    main()
