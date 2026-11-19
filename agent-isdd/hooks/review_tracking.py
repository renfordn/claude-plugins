#!/usr/bin/env python3
"""review_tracking hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def high_risk_slices(tasks_md_text):
    """Ids of slices whose Risk Tier is high-risk. Stub: empty list."""
    return []


def record_review(state_json_path, slice_id):
    """Persist a review for `slice_id` (via sdd_state.mark_reviewed). Stub: no-op."""
    return None


def unreviewed_high_risk(feature_dir):
    """High-risk slice ids lacking a reviewed entry or Review Fallback. Stub: empty list."""
    return []


def evaluate(payload):
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
