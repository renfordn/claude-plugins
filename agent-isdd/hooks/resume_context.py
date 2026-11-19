#!/usr/bin/env python3
"""resume_context hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build_context(payload):
    """Context string injected on UserPromptSubmit, or None. Stub: None."""
    return None


def evaluate(payload):
    return build_context(payload)


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
