#!/usr/bin/env python3
"""Review gate: a paused agent-TDD can't be resumed until an independent review has run.

SubagentStop       agent-TDD reporting green_pause opens a gate for its agent_id; any other
                   agent-TDD report from that agent closes it. A <!--CODE-REVIEWER-REPORT-->
                   from the code-reviewer agent marks every open gate reviewed.
PostToolUse(Bash)  the same marker in the output of code-reviewer's review_headless.sh marks
                   gates reviewed.
PreToolUse         SendMessage to an agent whose gate is open and unreviewed is denied, unless
  (SendMessage)    the message carries an explicit label: self-reviewed, review skipped, or
                   reviewed by: <who>. That keeps every bypass on record in the transcript.

Fails open: any error here is logged to stderr and the tool call proceeds.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REVIEW_MARKER = "<!--CODE-REVIEWER-REPORT-->"
TDD_MARKER = "<!--AGENT-TDD-REPORT-->"
GREEN_PAUSE = "<!--AGENT-TDD-PHASE:green_pause-->"
LABEL_RE = re.compile(r"self-reviewed|review skipped|reviewed by:", re.IGNORECASE)


def _gate_path(cwd):
    from tdd_state import tdd_memory_dir
    return os.path.join(tdd_memory_dir(cwd), "review-gate.json")


def _read(cwd):
    try:
        with open(_gate_path(cwd), encoding="utf-8") as fh:
            gates = json.load(fh)
        return gates if isinstance(gates, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(cwd, gates):
    path = _gate_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(gates, fh, indent=2)
        fh.write("\n")


def _mark_reviewed(cwd):
    gates = _read(cwd)
    open_gates = [g for g in gates.values() if not g.get("reviewed")]
    for gate in open_gates:
        gate["reviewed"] = True
    if open_gates:
        _write(cwd, gates)


def _subagent_text(payload):
    text = payload.get("last_assistant_message")
    if text:
        return text
    from tdd_subagent_stop import _extract_last_assistant_text
    return _extract_last_assistant_text(payload.get("agent_transcript_path", ""))[0]


def on_subagent_stop(payload, cwd):
    text = _subagent_text(payload)
    agent_id = payload.get("agent_id")
    if TDD_MARKER in text and agent_id:
        gates = _read(cwd)
        if GREEN_PAUSE in text:
            gates[agent_id] = {"opened_at": datetime.datetime.now().isoformat(timespec="seconds"),
                               "reviewed": False}
        else:
            gates.pop(agent_id, None)
        _write(cwd, gates)
    if REVIEW_MARKER in text and str(payload.get("agent_type", "")).endswith("code-reviewer"):
        _mark_reviewed(cwd)


def on_pre_send_message(payload, cwd):
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("to") or tool_input.get("recipient")
    gate = _read(cwd).get(target)
    if not gate or gate.get("reviewed"):
        return None
    message = f"{tool_input.get('message', '')} {tool_input.get('content', '')}"
    if LABEL_RE.search(message):
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"agent-TDD {target} is paused after Green waiting for an independent review, and "
            "none has been recorded. Run one first (code-reviewer's INTEROP.md, \"Independent "
            "review\": spawn code-reviewer:code-reviewer, else scripts/review_headless.sh), then "
            "resume it with the findings. If no independent reviewer is possible, put "
            "'self-reviewed', 'review skipped', or 'reviewed by: <who>' in the resume message "
            "so the bypass is on record."
        ),
    }}


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    event = payload.get("hook_event_name")
    if event == "PostToolUse" and REVIEW_MARKER not in raw:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    if event == "SubagentStop":
        on_subagent_stop(payload, cwd)
    elif (event == "PostToolUse" and payload.get("tool_name") == "Bash"
          and "review_headless.sh" in str((payload.get("tool_input") or {}).get("command", ""))
          and "finding-verifier" not in str((payload.get("tool_input") or {}).get("command", ""))):
        _mark_reviewed(cwd)
    elif event == "PreToolUse" and payload.get("tool_name") == "SendMessage":
        return on_pre_send_message(payload, cwd)
    return None


if __name__ == "__main__":
    try:
        out = main()
    except Exception as exc:  # noqa: BLE001 -- a broken gate must never break the session
        sys.stderr.write(f"[review_gate] {exc}\n")
        out = None
    if out:
        print(json.dumps(out))
    sys.exit(0)
