#!/usr/bin/env python3
"""SubagentStop hook entrypoint.

Bridges Claude Code's actual hook contract to
orchestrator.hooks.subagent_stop.handle_agent_completion, the pure
handoff-logging/contract-validation function this plugin already implements
and tests.

Contract (see https://code.claude.com/docs/en/hooks.md):
  stdin: {"cwd": ..., "agent_type": ..., "last_assistant_message": ..., "transcript_path": ...}

SubagentStop cannot inject context back into the parent conversation (only
block via exit code 2, or show the user a systemMessage) -- this hook only
observes and logs, so it always exits 0.

Any failure degrades to a no-op so a broken hook never blocks a subagent
from finishing.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hook_state import (  # noqa: E402
    workflow_state_path, load_workflow_state, save_workflow_state,
    BASE, project_slug as _project_slug,
)
from orchestrator.hook_telemetry import get_hook_telemetry_logger  # noqa: E402


def _extract_last_assistant_text(transcript_path, tail_bytes=16384):
    """Fallback for older Claude Code versions without last_assistant_message:
    read only the tail of the transcript to find the last assistant message."""
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
        lines = lines[1:]  # drop a possibly-partial first line from the mid-file seek

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
        sys.exit(0)

    agent_type = payload.get("agent_type") or "unknown"
    report = payload.get("last_assistant_message") or _extract_last_assistant_text(
        payload.get("transcript_path", "")
    )
    if not report:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    state_path = workflow_state_path(cwd)
    if not state_path:
        sys.exit(0)  # no active SDD workflow — nothing to log

    workflow_state = load_workflow_state(state_path)
    workflow_state_dir = Path(state_path).parent
    telemetry = get_hook_telemetry_logger(workflow_state_dir)
    telemetry.emit("hook_invoked", hook="subagent_stop", agent_type=agent_type)

    try:
        from orchestrator.hooks.subagent_stop import handle_agent_completion
        summary = handle_agent_completion(
            agent_type, report, workflow_state,
            error_registry_base_path=BASE, project_slug=_project_slug(cwd)
        )
    except Exception as e:
        telemetry.emit(
            "hook_error", hook="subagent_stop", agent_type=agent_type,
            error_type=type(e).__name__,
        )
        sys.exit(0)  # graceful degradation — never block subagent completion

    telemetry.emit(
        "hook_completed", hook="subagent_stop", agent_type=agent_type,
        outcome="ok",
        validation_result=(summary or {}).get("validation_result"),
        escalation_marker=bool((summary or {}).get("escalation_marker")),
    )

    save_workflow_state(state_path, workflow_state)

    system_message = _build_system_message(agent_type, summary, workflow_state, state_path)
    if system_message:
        print(json.dumps({"systemMessage": system_message}))

    sys.exit(0)


def _build_system_message(agent_type, summary, workflow_state, state_path):
    """Surface a contract violation, escalation, or pending nelly request.

    SubagentStop cannot inject context back into the conversation, but it can
    show the user a systemMessage (see module docstring). Without this, a
    "pause" recovery decision or a detected escalation marker was previously
    only ever written to workflow-state.json's handoff_history, invisible
    unless someone went looking at the file.
    """
    parts = []

    if summary:
        if summary.get("escalation_marker"):
            parts.append(f"{agent_type} raised an escalation marker: {summary['escalation_marker']}")
        if summary.get("validation_result") == "contract_invalid":
            missing = summary.get("error_details", {}).get("missing_fields")
            detail = f" (missing: {', '.join(missing)})" if missing else ""
            action = summary.get("recovery_action") or "no recovery available"
            parts.append(
                f"{agent_type}'s output failed contract validation{detail} — "
                f"orchestrator recovery action: {action}"
            )

    pending = [
        e for e in workflow_state.get("orchestration", {}).get("pending_nelly_requests", [])
        if e["status"] == "pending"
    ]
    if pending:
        ids = ", ".join(e["id"] for e in pending)
        parts.append(
            f"{len(pending)} nelly request(s) awaiting resolution ({ids}) — "
            f"call agent-nelly:agent-nelly, then run "
            f"`python3 resolve_nelly_request.py --state {state_path} --id <id> --result '<json>'` "
            f"(or --list to see the full query for each)"
        )

    return " | ".join(parts) if parts else None


if __name__ == "__main__":
    main()
