#!/usr/bin/env python3
"""approval hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def approval_hash(design_text, tasks_text):
    """Hash of the approved scope, recorded as Approval Hash. Stub: empty string."""
    return ""


def verify(fields, design_text, tasks_text):
    """ok | missing | mismatch | legacy. Stub: legacy."""
    return "legacy"


def evaluate(payload):
    """Handle a PostToolUse ExitPlanMode payload. Stub: no-op, returns None."""
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
