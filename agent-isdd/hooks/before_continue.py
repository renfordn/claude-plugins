#!/usr/bin/env python3
"""Before-continue hook: surface workflow stalls, escalations, rollbacks and spawn-model warnings.

Workflow conditions (priority order; the first that applies wins):
1. Stalled phases (Requirements approved but Design not entered; via sdd_state.detect_stall)
2. Model escalations (agent ran out of reasoning at its tier; recorded via sdd_state.update_json)
3. Rollback requests from agent-tdd (task conflicts, design contradictions)

Independently, a PreToolUse Agent spawn of agent-TDD or test-author with an explicit non-sonnet
model adds a neutral warning (skipped when it matches a pending escalation's to_model). The
warning never denies and is joined with any workflow message into one systemMessage.

Stalled phase detection: when a phase's artifact is Approved but the next phase's artifact
hasn't been created, the orchestrator likely provided guidance and ended its turn instead
of continuing to the next phase. This hook surfaces the stall so /isdd-continue can auto-resume.

This hook runs at workflow resume (on /isdd-continue) and surfaces pending actions.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, detect_stall, parse_state, parse_state_json, update_json  # noqa: E402
from subagent_report import extract_last_assistant_text  # noqa: E402
from model_escalate_marker import detect_model_escalate_in_report, escalation_message  # noqa: E402


def _detect_model_escalate_marker(transcript_path):
    """Detect a MODEL-ESCALATE marker in the transcript's last assistant
    message, using Task 7's isolated parsing utility (model_escalate_marker.py).

    Fallback only: this is the parent session's transcript, where agent-TDD's report arrives as
    a tool result, not an assistant message. The primary detection is subagent_report.py's, at
    agent-TDD's own SubagentStop.

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


_WATCHED_AGENTS = {"agent-TDD", "test-author"}


def _spawn_target(payload):
    """(agent, model) for an Agent spawn of a watched agent with an explicit model, else None."""
    if payload.get("tool_name") != "Agent":
        return None
    ti = payload.get("tool_input") or {}
    agent = str(ti.get("subagent_type", "")).split(":")[-1]
    model = str(ti.get("model") or "").strip()
    if agent not in _WATCHED_AGENTS or not model or "sonnet" in model.lower():
        return None
    return agent, model


def _model_warning(target, pending_escalation):
    """Neutral warning for a non-sonnet spawn; None when it matches a pending escalation."""
    if not target:
        return None
    agent, model = target
    to_model = str((pending_escalation or {}).get("to_model") or "").strip().lower()
    if to_model and to_model in model.lower():
        return None
    return (
        f"{agent} default is sonnet; confirm '{model}' is the slice's Model Tier "
        f"or an escalation."
    )


def _emit(messages):
    if messages:
        print(json.dumps({"systemMessage": "\n\n".join(messages)}))
    sys.exit(0)


def main():
    """Surface stalls, escalations, rollbacks and spawn-model warnings as one systemMessage."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    target = _spawn_target(payload)
    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        _emit([w for w in [_model_warning(target, None)] if w])

    feature_dir = os.path.dirname(state)
    json_path = os.path.join(feature_dir, "workflow-state.json")
    # Use transcript_path from payload if provided (for testing); otherwise construct it
    transcript_path = payload.get("transcript_path") or os.path.join(feature_dir, "transcript.jsonl")

    state_json = parse_state_json(json_path)
    state_md = parse_state(state)

    messages = []
    pending = state_json.get("escalation_pending")

    stall = detect_stall(state_md, feature_dir)
    escalation = None if stall else _detect_model_escalate_marker(transcript_path)
    if escalation:
        pending = escalation

    warning = _model_warning(target, pending)
    if warning:
        messages.append(warning)

    if stall:
        current_phase, next_phase = stall
        title = state_md.get("title", "the active feature")
        messages.append(
            f"🔄 **Workflow Stall Detected**: '{title}'\n\n"
            f"**Phase {current_phase} is Approved** (its artifact says `State: Approved`) but **{next_phase} has not been entered** (no {next_phase.lower()}.md yet).\n\n"
            f"This typically means the orchestrator provided guidance/decisions at a phase boundary "
            f"and then ended its turn instead of continuing with the next phase skill.\n\n"
            f"**Resuming now** will automatically advance to the {next_phase} phase and continue the workflow. "
            f"This is expected behavior — no action needed on your end."
        )
        _emit(messages)

    if escalation:
        # Top-level key, mirroring agent-tdd's rollback_pending contract.
        try:
            update_json(json_path, lambda d: {**d, "escalation_pending": escalation})
        except Exception:
            pass  # Silent failure — don't block user
        messages.append(escalation_message(escalation))
        _emit(messages)

    rollback = state_json.get("rollback_pending")
    if rollback:
        target_phase = rollback.get("target", "Requirements")
        reason = rollback.get("reason", "unknown issue")
        source = rollback.get("source", "agent-tdd")
        messages.append(
            f"⚠️ **Rollback Pending** (from {source})\n\n"
            f"**Issue:** {reason}\n\n"
            f"**Suggested action:** Rewind to **{target_phase}** phase to address the issue.\n\n"
            f"To proceed, reply with: `/isdd-rewind {target_phase}`\n"
            f"Or type a message to discuss first."
        )
    _emit(messages)


if __name__ == "__main__":
    main()
