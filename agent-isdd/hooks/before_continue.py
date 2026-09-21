#!/usr/bin/env python3
"""Before-continue hook: surface workflow stalls, rollbacks, or model escalations.

Handles three conditions (checked in priority order):
1. Stalled phases (phase Complete but next phase not entered)
2. Rollback requests from agent-tdd (task conflicts, design contradictions)
3. Model escalations (agent ran out of reasoning at current tier, needs higher tier)

Stalled phase detection: when a phase is marked Complete but the next phase's artifact
hasn't been created, the orchestrator likely provided guidance and ended its turn instead
of continuing to the next phase. This hook surfaces the stall so /sdd-continue can auto-resume.

This hook runs at workflow resume (on /isdd-continue) and surfaces pending actions.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state, parse_state_json  # noqa: E402
from subagent_report import extract_last_assistant_text  # noqa: E402
from model_escalate_marker import detect_model_escalate_in_report  # noqa: E402


def _detect_model_escalate_marker(transcript_path):
    """Detect a MODEL-ESCALATE marker in the transcript's last assistant
    message, using Task 7's isolated parsing utility (model_escalate_marker.py).

    Marker format: <!--AGENT-TDD-MODEL-ESCALATE: reason="..." from_model="..." to_model="..."-->

    Returns: dict with keys {reason, from_model, to_model, detected_at} or None
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    report_text = extract_last_assistant_text(transcript_path)
    parsed = detect_model_escalate_in_report(report_text)
    if not parsed:
        return None

    return {
        "reason": parsed["reason"],
        "from_model": parsed.get("from_model"),
        "to_model": parsed["to_model"],
        "detected_at": datetime.now().isoformat(),
    }


def _detect_stalled_phase(state_fields, feature_dir):
    """Detect if a phase is Complete but next phase hasn't been entered.

    Returns (is_stalled, current_phase, next_phase) or (False, None, None).
    """
    current = state_fields.get("current phase", "").strip()
    status = state_fields.get("workflow status", "").lower()

    phase_order = ["Requirements", "Design", "Tasks"]
    phase_files = {
        "Requirements": "requirements/requirements.md",
        "Design": "design/design.md",
        "Tasks": "tasks/tasks.md",
    }

    # Find current phase in order
    for i, phase in enumerate(phase_order):
        if current.startswith(phase):
            # Current phase detected at position i
            # Check if phase is marked as complete
            if "complete" in status:
                # Check if next phase file exists (entry has been attempted)
                if i + 1 < len(phase_order):
                    next_phase = phase_order[i + 1]
                    next_file = os.path.join(feature_dir, phase_files[next_phase])
                    if not os.path.exists(next_file):
                        # Phase complete but next not entered — workflow stalled
                        return (True, phase, next_phase)
            break

    return (False, None, None)


def main():
    """Check for pending rollback, model escalation, or stalled phases; surface if found."""
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
    state_md = parse_state(state)

    # Check for stalled phase FIRST (workflow continuity issue)
    is_stalled, current_phase, next_phase = _detect_stalled_phase(state_md, feature_dir)
    if is_stalled:
        title = state_md.get("title", "the active feature")
        message = (
            f"🔄 **Workflow Stall Detected**: '{title}'\n\n"
            f"**Phase {current_phase} is marked Complete** but **{next_phase} has not been entered**.\n\n"
            f"This typically means the orchestrator provided guidance/decisions at a phase boundary "
            f"and then ended its turn instead of continuing with the next phase skill.\n\n"
            f"**Resuming now** will automatically advance to the {next_phase} phase and continue the workflow. "
            f"This is expected behavior — no action needed on your end."
        )
        print(json.dumps({"systemMessage": message}))
        sys.exit(0)

    # Check for model escalation (highest priority remaining)
    escalation = _detect_model_escalate_marker(transcript_path)
    if escalation:
        # Record escalation in workflow state (top-level key; agent-tdd's
        # rollback_pending is also top-level, so this mirrors that contract)
        state_json["escalation_pending"] = escalation

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
            f"**Action:** Call the `get_spawn_context` tool from plugin-harness's bundled "
            f"`spawn-context` MCP server (args: agent_type=\"agent-tdd\", cwd=this project) to "
            f"pull accumulated context from the {from_model}-tier attempt, then re-spawn "
            f"`agent-TDD` at **{to_model}** tier with that context so it can continue from where "
            f"the lower tier left off. The tool's exact callable name is harness-prefixed (not "
            f"the bare string `get_spawn_context`) — if it isn't already visible, use ToolSearch "
            f"with query \"get_spawn_context\" to find and load it before calling it.\n"
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
