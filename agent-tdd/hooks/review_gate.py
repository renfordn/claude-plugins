#!/usr/bin/env python3
"""Review gate: a paused agent-TDD can't be resumed until an independent review has run.

SubagentStop       agent-TDD reporting green_pause opens a gate for its agent_id, recording the
                   slice id (explicit <!--SLICE-ID: N--> marker, else a line-start "Slice N:"
                   title; never a prose mention). Any other agent-TDD report from that agent
                   closes it. A <!--CODE-REVIEWER-REPORT--> from the code-reviewer agent clears
                   gates via clear_gates, scoped by its <!--REVIEW-SCOPE: slice=N--> marker.
PostToolUse(Bash)  the same marker in the output of code-reviewer's review_headless.sh clears
                   gates the same way.
PreToolUse         SendMessage to an agent whose gate is open and unreviewed is denied, unless
  (SendMessage)    the message carries an explicit label: self-reviewed, review skipped, or
                   reviewed by: <who>. That keeps every bypass on record in the transcript.

Scoping: a scoped review clears only gates of that slice. An unscoped review clears the sole
open gate (backward compatible; a residual risk if the reviewer meant another slice) and clears
nothing when several are open, warning via systemMessage. State lives in the main checkout's
memory dir so worktree subagents and the lead share it.

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
    from tdd_state import state_cwd, tdd_memory_dir
    return os.path.join(tdd_memory_dir(state_cwd(cwd)), "review-gate.json")


def _read(cwd):
    try:
        with open(_gate_path(cwd), encoding="utf-8") as fh:
            gates = json.load(fh)
        return gates if isinstance(gates, dict) else {}
    except (OSError, ValueError):
        return {}


def clear_gates(cwd, scope=None):
    """Mark gates reviewed. scope given: only gates whose slice == scope. scope None: the one
    open gate if exactly one is open, else none. Returns a systemMessage dict when an unscoped
    review was ignored, else None."""
    from tdd_state import update_json
    result = {}

    def fn(gates):
        open_gates = [g for g in gates.values()
                      if isinstance(g, dict) and not g.get("reviewed")]
        if scope is not None:
            from markers import normalize_slice_id
            targets = [g for g in open_gates
                       if normalize_slice_id(g.get("slice")) == normalize_slice_id(scope)]
            if open_gates and not targets:
                listed = ", ".join(str(g.get("slice")) if g.get("slice") is not None
                                   else "none" for g in open_gates)
                result["msg"] = (
                    f"review-gate: review scoped to slice {scope} matched no open gate; "
                    f"open gates are for slices: {listed}. None was cleared.")
        elif len(open_gates) == 1:
            targets = open_gates
        else:
            targets = []
            if open_gates:
                result["msg"] = (
                    f"review-gate: the review was unscoped (no <!--REVIEW-SCOPE: slice=N--> "
                    f"marker) and {len(open_gates)} agent-TDD gates are open, so none was "
                    "cleared. Re-run the review with a scope marker.")
        for g in targets:
            g["reviewed"] = True
        return gates

    update_json(_gate_path(cwd), fn)
    return {"systemMessage": result["msg"]} if "msg" in result else None


def _subagent_text(payload):
    text = payload.get("last_assistant_message")
    if text:
        return text
    from tdd_state import extract_last_assistant_text
    return extract_last_assistant_text(payload.get("agent_transcript_path", ""))[0]


def on_subagent_stop(payload, cwd):
    text = _subagent_text(payload)
    agent_id = payload.get("agent_id")
    if TDD_MARKER in text and agent_id:
        from tdd_state import update_json
        opened = GREEN_PAUSE in text
        from markers import parse_slice_id_strict
        slice_id = parse_slice_id_strict(text)

        def fn(gates):
            if opened:
                gates[agent_id] = {
                    "opened_at": datetime.datetime.now().isoformat(timespec="seconds"),
                    "reviewed": False, "slice": slice_id}
            else:
                gates.pop(agent_id, None)
            return gates

        update_json(_gate_path(cwd), fn)
    if REVIEW_MARKER in text and str(payload.get("agent_type", "")).endswith("code-reviewer"):
        from markers import parse_review_scope
        return clear_gates(cwd, parse_review_scope(text))
    return None


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


def raw_text(payload, raw):
    """Text of the Bash tool output (scope marker lives there); raw payload as fallback."""
    resp = payload.get("tool_response")
    if isinstance(resp, dict):
        return f"{resp.get('stdout', '')}\n{resp.get('stderr', '')}"
    return resp if isinstance(resp, str) else raw


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
        return on_subagent_stop(payload, cwd)
    elif (event == "PostToolUse" and payload.get("tool_name") == "Bash"
          and "review_headless.sh" in str((payload.get("tool_input") or {}).get("command", ""))
          and "finding-verifier" not in str((payload.get("tool_input") or {}).get("command", ""))):
        from markers import parse_review_scope
        return clear_gates(cwd, parse_review_scope(raw_text(payload, raw)))
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
