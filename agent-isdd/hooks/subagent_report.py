#!/usr/bin/env python3
"""SubagentStop hook: capture a finished SDD subagent's final report into the
active feature's recap log, so the delegation loop is never lost.

Only logs when (a) an SDD workflow is active and (b) the subagent's final message
looks like a phase-worker report (spec-reviewer / tdd-planner) -- keeps unrelated
subagents, and the plugin's own mechanical helpers (planning-agent, the
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
from sdd_state import active_state_file, write_rollback_pending  # noqa: E402

# Markers that identify a spec-reviewer / tdd-planner report.
SDD_MARKERS = re.compile(
    r"(?i)(verdict|acceptance criteria|\bEARS\b|tasks\.md|handoff|"
    r"rewritten|readiness|phase status|recommended phase status)"
)

# Explicit, plugin-controlled marker the two phase-worker subagents emit as
# the first line of their final report. Preferred over SDD_MARKERS because it
# can't be coincidentally triggered by unrelated natural-language text.
EXPLICIT_MARKER = re.compile(r"<!--SDD-REPORT:(tdd-planner|spec-reviewer)-->")

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


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state = active_state_file(cwd)
    if not state:
        sys.exit(0)

    report = extract_last_assistant_text(payload.get("transcript_path", ""))
    if not report:
        sys.exit(0)

    feature_dir = os.path.dirname(state)

    # Human-relay marker takes priority if somehow both are present in the same report --
    # it names an explicit target, which is strictly more information than the automatic
    # marker's defaulted one.
    rollback = extract_rollback_request(report) or extract_plan_validity_flag(report)
    if rollback:
        json_path = os.path.join(feature_dir, "workflow-state.json")
        write_rollback_pending(json_path, rollback["target"], rollback["reason"], "agent-tdd")
        _append_pending_rollback_line(state, rollback["target"], rollback["reason"])
        print(json.dumps({"systemMessage": (
            f"SDD: a rollback request was received (target={rollback['target']}) — "
            "recorded as rollback_pending in workflow-state.json and workflow-state.md. "
            "The next /isdd-continue will route it through the Rewind Contract."
        )}))
        sys.exit(0)

    if not is_sdd_report(report):
        sys.exit(0)  # not an SDD phase-worker report — stay quiet

    log = os.path.join(feature_dir, "recap", "subagent-reports.md")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## Subagent report — {ts}\n\n{report}\n"
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        sys.exit(0)

    print(json.dumps({"systemMessage": (
        f"SDD: captured a subagent report to {os.path.relpath(log, cwd)} — "
        f"integrate it into recap.md and update workflow-state."
    )}))
    sys.exit(0)


if __name__ == "__main__":
    main()
