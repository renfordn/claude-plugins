#!/usr/bin/env python3
"""SubagentStop hook: capture a finished SDD subagent's final report into the
active feature's recap log, so the delegation loop is never lost.

Only logs when (a) an SDD workflow is active and (b) the subagent's final message
looks like a phase-worker report (spec-reviewer) -- keeps unrelated
subagents, and the plugin's own mechanical helper (research-consolidator, the
cross-plugin agent-ux:ux-agent), from adding recap noise. Implementation-phase
reports (agent-TDD / test-author) are out of scope for this plugin -- they
belong to the separate agent-tdd plugin.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import (  # noqa: E402
    active_state_file,
    read_escalation_pending,
    write_escalation_outcome,
    write_escalation_pending,
    write_rollback_pending,
)
from model_escalate_marker import detect_model_escalate_in_report, escalation_message  # noqa: E402

# Marker recognizing an agent-tdd report shape, per design.md's edge case: only classify an
# escalation outcome when the report carries agent-tdd's own phase marker -- an unrelated
# spec-reviewer report must never be misclassified against a stale escalation_pending.
AGENT_TDD_PHASE_MARKER = re.compile(r"<!--AGENT-TDD-PHASE:")

# Markers that identify a spec-reviewer report.
SDD_MARKERS = re.compile(
    r"(?i)(verdict|acceptance criteria|\bEARS\b|tasks\.md|handoff|"
    r"rewritten|readiness|phase status|recommended phase status)"
)

# Explicit, plugin-controlled marker the phase-worker subagent emits as
# the first line of its final report. Preferred over SDD_MARKERS because it
# can't be coincidentally triggered by unrelated natural-language text.
EXPLICIT_MARKER = re.compile(r"<!--SDD-REPORT:(spec-reviewer)-->")

# Human-relay rollback marker per INTEROP.md's "<- agent-tdd / code-reviewer (rollback
# request)" convention: a human (or whichever context is driving) pastes this directly into a
# message re-entering agent-isdd, naming agent-isdd's own phase vocabulary explicitly since a
# human relaying a code-reviewer finding can reasonably know it. Recognized independently of
# is_sdd_report -- agent-TDD/test-author's own narrative reports are otherwise explicitly
# out of scope for this hook (see module docstring), but this structural marker is a
# distinct, explicit signal crossing back into agent-isdd's territory, not a narrative
# report to log.
ROLLBACK_MARKER = re.compile(
    r'<!--SDD-ROLLBACK-REQUEST:\s*target=(Requirements|Design|Tasks)\s+reason="([^"]*)"-->'
)

# Automatic path: agent-tdd's own generic, caller-agnostic Plan Validity Flag marker (see
# agent-tdd/INTEROP.md's "Plan Validity Flag" section) -- agent-TDD never knows agent-isdd's
# phase vocabulary, so it carries a reason only, no target. This hook defaults the target to
# "Requirements" -- per references/rollback-guide.md's already-established "Which target phase
# to name" policy, an unclear/absent target defaults to the more conservative (earlier) phase,
# since it's always safer to re-confirm a phase that may have been fine than to skip past one
# that actually needs revision -- and prefixes the reason so workflow-manager's "Rollback
# Request Intake" contract, which already reads the reason text and re-derives the target
# rather than trusting a stored value blindly, can re-target forward (to Design or Tasks) if
# the reason clearly indicates a narrower problem instead.
PLAN_FLAG_MARKER = re.compile(r'<!--AGENT-TDD-PLAN-FLAG:\s*reason="([^"]*)"-->')

# Note: an earlier TEST_AUTHOR_NEEDED_MARKER convention (marker emitted by agent-TDD itself)
# was removed 2026-09-16 -- detection of high-risk slices needing test-author now happens in
# high_risk_reviewer.py, which parses agent-TDD's slicing_complete phase marker plus tasks.md
# already on disk (no separate marker needed; see design.md's Research Basis for this feature).


# Narrative "confirmed passing test-suite evidence" detection for escalation-outcome
# classification (see design.md's Data Contracts And Interfaces). Conservative: a failure or
# ambiguous phrase must never match here, even if a passing-sounding word appears nearby -- the
# negative lookahead/context guards below exist for exactly that reason.
VALIDATION_MARKERS = re.compile(
    r"(?i)("
    r"\ball\s+tests?\s+passing\b"
    r"|\bfull\s+regression\s+green\b"
    r"|\b\d+\s+tests?\s+passing\b"
    r"|\b\d+\s*/\s*\d+\s+pass(?:ing|ed)?\b"
    r"|\bregression[^.\n]*\ball\s+pass(?:ing|ed)?\b"
    r")"
)

# Explicit negative phrasing that must never be treated as validation evidence even though it
# contains test-related words -- checked first so it can veto an incidental positive match.
VALIDATION_FAILURE_MARKERS = re.compile(
    r"(?i)(\btests?\s+failing\b|\bsuite\s+red\b|\bregression[^.\n]*\bred\b)"
)


def _has_validation_evidence(text):
    """True only when `text` contains conservative, unambiguous narrative evidence of a passing
    test suite (see VALIDATION_MARKERS above), and no explicit failure phrasing. No match, or
    only ambiguous/failure phrasing, => False -- never assumed true."""
    if not text:
        return False
    if VALIDATION_FAILURE_MARKERS.search(text):
        return False
    return bool(VALIDATION_MARKERS.search(text))


def _has_further_escalation_marker(text):
    """True when `text` carries a rollback request, plan-validity flag, or a fresh
    MODEL-ESCALATE marker -- any of these means the re-spawned attempt did not cleanly resolve
    the original escalation (see design.md's Success Criteria and double-escalation edge case)."""
    return bool(
        ROLLBACK_MARKER.search(text)
        or PLAN_FLAG_MARKER.search(text)
        or detect_model_escalate_in_report(text)
    )


def _classify_escalation_outcome(report, escalation_pending):
    """Classify a re-spawned agent-tdd report against the recorded escalation_pending entry.

    Returns "succeeded" only when _has_validation_evidence is true AND no further escalation/
    blocker/rollback marker is present. A further marker present forces "failed" regardless of
    validation evidence (marker presence dominates). Otherwise (no evidence, no further marker)
    => "ambiguous". `escalation_pending` is accepted for interface symmetry/future use but not
    currently consulted -- classification depends only on the report's own content.
    """
    del escalation_pending  # unused for now; kept for interface symmetry (see design.md)
    if _has_further_escalation_marker(report):
        return "failed"
    if _has_validation_evidence(report):
        return "succeeded"
    return "ambiguous"


def is_sdd_report(text):
    return bool(EXPLICIT_MARKER.search(text) or SDD_MARKERS.search(text))


def extract_rollback_request(text):
    """Return {"target": ..., "reason": ...} from a human-relayed marker, else None."""
    m = ROLLBACK_MARKER.search(text)
    if not m:
        return None
    return {"target": m.group(1), "reason": m.group(2)}


def extract_plan_validity_flag(text):
    """Return {"target": ..., "reason": ...} from agent-tdd's own automatic marker, else None.

    Target always defaults to "Requirements" here -- see the PLAN_FLAG_MARKER comment above.
    """
    m = PLAN_FLAG_MARKER.search(text)
    if not m:
        return None
    reason = m.group(1)
    return {
        "target": "Requirements",
        "reason": f"[agent-tdd Plan Validity Flag, target defaulted to Requirements (most "
                   f"conservative) -- re-evaluate against reason] {reason}",
    }


def _append_pending_rollback_line(state_md_path, target, reason):
    line = f'\n- Pending Rollback Request: target={target} reason="{reason}"\n'
    try:
        with open(state_md_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def extract_last_assistant_text(transcript_path, tail_bytes=16384):
    """Read only the tail of the transcript to find the last assistant message.
    SDD subagent reports are always the terminal output; reading the full JSONL
    file is wasteful for large transcripts. 16 KB comfortably covers any report.
    """
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - tail_bytes)
            fh.seek(start)
            raw = fh.read()
    except OSError:
        return ""

    lines = raw.split(b"\n")
    if start > 0:
        lines = lines[1:]  # drop potentially partial first line caused by mid-line seek

    blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else None
        role = ev.get("type") or (msg.get("role") if msg else "")
        is_assistant = role == "assistant" or (msg and msg.get("role") == "assistant")
        if not is_assistant:
            continue
        content = msg.get("content") if msg else ev.get("content")
        if isinstance(content, str):
            blocks.append(content)
        elif isinstance(content, list):
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            joined = "\n".join(p for p in parts if p)
            if joined:
                blocks.append(joined)
    return blocks[-1].strip() if blocks else ""


def report_text_from_payload(payload):
    """The stopping subagent's final message. transcript_path is the parent session's
    transcript on current Claude Code, so it's only the last fallback."""
    text = payload.get("last_assistant_message")
    if text:
        return text.strip()
    return extract_last_assistant_text(
        payload.get("agent_transcript_path") or payload.get("transcript_path", ""))


def main(payload=None):
    """Returns the systemMessage text (or None) instead of printing it directly, so
    subagent_dispatch.py can run this alongside the other SubagentStop hooks in one process
    and merge their messages. Standalone invocation (tests, direct hooks.json entry) still
    reads stdin and prints exactly as before via the __main__ block below.
    """
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        return None

    report = report_text_from_payload(payload)
    if not report:
        return None

    feature_dir = os.path.dirname(state)
    json_path = os.path.join(feature_dir, "workflow-state.json")

    # Escalation-outcome classification: independent of the rollback-marker check below (a
    # rollback/plan-flag marker in the SAME report is itself a "further marker" that classifies
    # the escalation as failed -- see design.md's edge cases) -- only fires when escalation_pending
    # is present AND the report is recognized as agent-tdd-shaped, so a stale escalation_pending
    # is never misclassified against an unrelated report (e.g. spec-reviewer).
    escalation_msg = None
    escalation_pending = read_escalation_pending(json_path)
    if escalation_pending and AGENT_TDD_PHASE_MARKER.search(report):
        outcome = _classify_escalation_outcome(report, escalation_pending)
        entry = dict(escalation_pending, outcome=outcome,
                     resolved_at=datetime.datetime.now().isoformat())
        write_escalation_outcome(json_path, entry)
        escalation_msg = f"Escalation resolved: {outcome}"

    # A new MODEL-ESCALATE marker in this report: record it now, where agent-TDD's report is
    # actually visible, so the caller learns to re-spawn at a higher tier before it acts.
    new_escalation = detect_model_escalate_in_report(report)
    if new_escalation:
        pending = {k: new_escalation.get(k) for k in ("reason", "from_model", "to_model")}
        pending["detected_at"] = datetime.datetime.now().isoformat()
        write_escalation_pending(json_path, pending)
        respawn_msg = escalation_message(pending)
        escalation_msg = f"{escalation_msg}.\n\n{respawn_msg}" if escalation_msg else respawn_msg

    # Human-relay marker takes priority if somehow both are present in the same report --
    # it names an explicit target, which is strictly more information than the automatic
    # marker's defaulted one.
    rollback = extract_rollback_request(report) or extract_plan_validity_flag(report)
    if rollback:
        write_rollback_pending(json_path, rollback["target"], rollback["reason"], "agent-tdd")
        _append_pending_rollback_line(state, rollback["target"], rollback["reason"])
        rollback_msg = (
            f"SDD: a rollback request was received (target={rollback['target']}) — "
            "recorded as rollback_pending in workflow-state.json and workflow-state.md. "
            "The next /isdd-continue will route it through the Rewind Contract."
        )
        return f"{rollback_msg} {escalation_msg}." if escalation_msg else rollback_msg

    if escalation_msg:
        return escalation_msg

    if not is_sdd_report(report):
        return None  # not an SDD phase-worker report — stay quiet

    log = os.path.join(feature_dir, "recap", "subagent-reports.md")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## Subagent report — {ts}\n\n{report}\n"
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        return None

    return (
        f"SDD: captured a subagent report to {os.path.relpath(log, cwd)} — "
        f"integrate it into recap.md and update workflow-state."
    )


if __name__ == "__main__":
    _msg = main()
    if _msg:
        print(json.dumps({"systemMessage": _msg}))
    sys.exit(0)
