#!/usr/bin/env python3
"""Stop hook: warn if any slices are pending review."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdd_state import read_tdd_progress, summarize_open_slices  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()

    data = read_tdd_progress(cwd)
    pending, blocked = summarize_open_slices(data)
    if not pending and not blocked:
        sys.exit(0)

    parts = []
    if pending:
        items = "\n".join(pending)
        parts.append(f"agent-TDD: {len(pending)} slice(s) awaiting review resume at session end:\n"
                     f"{items}\n"
                     "Resume via SendMessage to the agent-TDD instance id, or re-spawn with the same Slice Spec.")
    if blocked:
        parts.append("agent-TDD: blocked slices:\n" + "\n".join(blocked))
    print(json.dumps({"systemMessage": "\n".join(parts)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
