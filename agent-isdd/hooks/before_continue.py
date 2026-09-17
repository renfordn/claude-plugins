#!/usr/bin/env python3
"""Before-continue hook: surface pending rollback requests or model escalations.

Handles two escalation types:
1. Rollback requests from agent-tdd (task conflicts, design contradictions)
2. Model escalations (agent ran out of reasoning at current tier, needs higher tier)

When agent-tdd's task slicing phase finds an unrecoverable blocker, it emits a
<!--AGENT-TDD-PLAN-FLAG:reason="..."> marker (caught by SubagentStop).

When agent-tdd runs out of reasoning capacity at a lower model tier (e.g., Haiku),
it emits a <!--AGENT-TDD-MODEL-ESCALATE:reason="...";suggest_tier="sonnet"-->  marker
(also caught by SubagentStop and stored in workflow-state.json).

This hook runs at workflow resume (on /isdd-continue) and surfaces pending actions.
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state_json


def _detect_model_escalate_marker(transcript_path):
    """Parse MODEL-ESCALATE marker from transcript if present.

    Marker format: <!--AGENT-TDD-MODEL-ESCALATE: reason="..." from_model="..." to_model="..."-->

    Returns: dict with keys {reason, from_model, to_model, detected_at} or None
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        with open(transcript_path, 'r') as f:
            content = f.read()
    except Exception:
        return None

    # Look for MODEL-ESCALATE marker in transcript
    # Marker format: <!--AGENT-TDD-MODEL-ESCALATE: reason="..." from_model="..." to_model="..."-->
    pattern = r'<!--AGENT-TDD-MODEL-ESCALATE:\s*([^-]*)-->'
    match = re.search(pattern, content)
    if not match:
        return None

    marker_content = match.group(1)
    result = {"detected_at": datetime.now().isoformat()}

    # Parse key="value" pairs from marker content
    fields = re.findall(r'(\w+)="([^"]*)"', marker_content)
    for key, value in fields:
        result[key] = value

    # Escalation must have a reason to be valid
    return result if result.get("reason") else None


def main():
    """Check for pending rollback or model escalation; surface to user if found."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        sys.exit(0)

    feature_dir = os.path.dirname(state)
    json_path = os.path.join(feature_dir, "workflow-state.json")
    # Use transcript_path from payload if provided (for testing); otherwise construct it
    transcript_path = payload.get("transcript_path") or os.path.join(feature_dir, "transcript.jsonl")

    state_json = parse_state_json(json_path)

    # Check for model escalation FIRST (highest priority)
    escalation = _detect_model_escalate_marker(transcript_path)
    if escalation:
        # Record escalation in workflow state
        if "orchestration" not in state_json:
            state_json["orchestration"] = {}
        state_json["orchestration"]["escalation_pending"] = escalation

        # Write updated state
        try:
            with open(json_path, 'w') as f:
                json.dump(state_json, f, indent=2)
        except Exception:
            pass  # Silent failure — don't block user

        reason = escalation.get("reason", "unknown issue")
        from_model = escalation.get("from_model", "Haiku")
        to_model = escalation.get("to_model", "Sonnet")

        message = (
            f"🚀 **Model Escalation Detected**\n\n"
            f"**Issue:** {reason}\n\n"
            f"**Action:** Re-spawning executor agent at **{to_model}** tier "
            f"(escalating from {from_model}) for stronger reasoning.\n\n"
            f"Accumulated context from prior attempts will be cached and reused.\n"
        )

        print(json.dumps({"systemMessage": message}))
        sys.exit(0)

    # Check for rollback (lower priority)
    rollback = state_json.get("rollback_pending")
    if not rollback:
        # Check for agent-tdd paused mid-refactor (code-review gate)
        # This is handled by spec-driven-development skill when it resumes,
        # not here. This hook only handles rollback requests and state checks.
        sys.exit(0)  # no pending rollback — continue normally

    target = rollback.get("target", "Requirements")
    reason = rollback.get("reason", "unknown issue")
    source = rollback.get("source", "agent-tdd")

    # Surface to user with clear action
    message = (
        f"⚠️ **Rollback Pending** (from {source})\n\n"
        f"**Issue:** {reason}\n\n"
        f"**Suggested action:** Rewind to **{target}** phase to address the issue.\n\n"
        f"To proceed, reply with: `/isdd-rewind {target}`\n"
        f"Or type a message to discuss first."
    )

    print(json.dumps({"systemMessage": message}))
    sys.exit(0)


if __name__ == "__main__":
    main()
