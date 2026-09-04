#!/usr/bin/env python3
"""SessionStart hook: surface pending review slices at session startup."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdd_state import read_tdd_progress, tdd_memory_dir  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    lines = [f"agent-TDD state for this project: {tdd_memory_dir(cwd)}"]

    data = read_tdd_progress(cwd)
    pending = [s for s in data["slices"] if s.get("status") == "green_pending_review"]

    if pending:
        lines.append("")
        lines.append(f"Slices awaiting review resume ({len(pending)}):")
        for s in pending:
            lines.append(f"  - [{s['id']}] {s['description']}")
        lines.append(
            "Resume via SendMessage to the agent-TDD instance id, "
            "or re-spawn with the same Slice Spec."
        )

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}))
    sys.exit(0)


if __name__ == "__main__":
    main()
