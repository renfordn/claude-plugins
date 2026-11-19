#!/usr/bin/env python3
"""user_led_guard hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def evaluate(payload, state_path=None):
    """Return a deny reason (str) for a non-test edit in user-led mode, else None. `state_path` is the active workflow-state.md resolved by pre_write_dispatch. Stub: None."""
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
