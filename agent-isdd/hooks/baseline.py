#!/usr/bin/env python3
"""baseline hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def record(cwd, state_json):
    """Record branch/head/dirty files into workflow-state.json. Stub: no-op."""
    return None


def diff(cwd, state_json):
    """Changes since the recorded baseline, as three lists. Stub: all empty."""
    return {"branch_changed": [], "head_moved": [], "files_changed": []}


def evaluate(payload):
    """Hook entry. Stub: no-op, returns None."""
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
