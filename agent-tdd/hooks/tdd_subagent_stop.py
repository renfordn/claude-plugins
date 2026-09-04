#!/usr/bin/env python3
"""SubagentStop hook: parse agent-TDD handoff reports and update per-slice progress.

Fires on every SubagentStop in any session where agent-tdd is installed. Only acts
when <!--AGENT-TDD-REPORT--> is found in the transcript's terminal assistant message.
All other subagent stops are silent no-ops.

Complementary to agent-isdd/hooks/subagent_report.py: that hook owns rollback write-back
to workflow-state.json; this hook owns tdd-progress.json. The two never conflict because
they write to different files.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdd_state import read_tdd_progress, write_tdd_progress  # noqa: E402

REPORT_MARKER = "<!--AGENT-TDD-REPORT-->"
PHASE_RE = re.compile(r"<!--AGENT-TDD-PHASE:(\w+)-->")
PLAN_FLAG_RE = re.compile(r'<!--AGENT-TDD-PLAN-FLAG:\s*reason="[^"]*"-->')
SECTION_RE = re.compile(r"^\*\*([^*]+)\*\*", re.MULTILINE)

TAIL_BYTES = 32768


def _extract_last_assistant_text(transcript_path):
    """Tail-read transcript JSONL and return the last assistant message text.
    Returns (text, truncated) where truncated=True means the file was larger than
    TAIL_BYTES so the head of the file was not read.
    """
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - TAIL_BYTES)
            fh.seek(start)
            raw = fh.read()
    except OSError:
        return "", False

    truncated = start > 0
    lines = raw.split(b"\n")
    if truncated:
        lines = lines[1:]  # drop potentially partial first line

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

    return (blocks[-1].strip() if blocks else ""), truncated


def _section_text(report, header):
    """Extract text under a **Header** section, up to the next **Header** or end."""
    pattern = re.compile(
        r"\*\*" + re.escape(header) + r"\*\*\s*(.*?)(?=\*\*[^*]|\Z)",
        re.DOTALL,
    )
    m = pattern.search(report)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_report(text):
    """Parse an agent-TDD handoff report and return a slice dict."""
    # Phase
    phase_m = PHASE_RE.search(text)
    status = "refactor_complete" if (phase_m and phase_m.group(1) == "refactor_complete") \
        else "green_pending_review"

    # Description: first non-empty line of the **Plan** section (most slice-specific text).
    # Fallback: first non-empty non-marker line in the whole report.
    plan_text = _section_text(text, "Plan")
    description = ""
    if plan_text:
        for ln in plan_text.splitlines():
            ln = ln.strip()
            if ln:
                description = ln
                break
    if not description:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and stripped not in (REPORT_MARKER,) \
                    and not stripped.startswith("<!--AGENT-TDD-PHASE:"):
                description = stripped
                break

    # Acceptance Criteria
    ac_text = _section_text(text, "Acceptance Criteria")
    ac_status = ac_text[:200].replace("\n", " ").strip() if ac_text else "not found"

    # Research Gap Flag: present and non-empty
    gap_text = _section_text(text, "Research Gap Flag")
    has_research_gap = bool(gap_text) and gap_text.lower() not in ("", "none", "n/a")

    # Plan Validity Flag: the marker line is the authoritative signal (matches how the caller-side
    # agent-isdd hook detects it), not the prose section -- but also check the section text so
    # progress tracking stays accurate even for a caller that has no marker-based rollback path of
    # its own and only reads the prose report.
    has_plan_flag = bool(PLAN_FLAG_RE.search(text))
    if not has_plan_flag:
        flag_text = _section_text(text, "Plan Validity Flag")
        has_plan_flag = bool(flag_text) and flag_text.lower() not in ("", "none", "n/a")

    # Handoff Facts: present and not "none"
    facts_text = _section_text(text, "Handoff Facts")
    has_handoff_facts = bool(facts_text) and facts_text.lower() not in ("", "none", "n/a")

    return {
        "description": description or "(no description)",
        "status": status,
        "acceptance_criteria_status": ac_status,
        "has_research_gap": has_research_gap,
        "has_plan_validity_flag": has_plan_flag,
        "has_handoff_facts": has_handoff_facts,
        "timestamp": datetime.datetime.now().isoformat(),
    }


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    transcript_path = payload.get("transcript_path", "")

    if not transcript_path:
        sys.exit(0)

    text, truncated = _extract_last_assistant_text(transcript_path)

    if REPORT_MARKER not in text:
        # Truncation warning only when transcript has content but marker wasn't found
        if truncated and text:
            print(json.dumps({"systemMessage": (
                "agent-TDD: transcript present but <!--AGENT-TDD-REPORT--> not found "
                "in last 32 KB — report may be truncated. Inspect transcript directly "
                "before continuing."
            )}))
        sys.exit(0)

    entry = _parse_report(text)

    # Read existing progress; update in-place if same description + green_pending_review
    data = read_tdd_progress(cwd)
    slices = data["slices"]
    updated = False
    for existing in slices:
        if (existing.get("description") == entry["description"]
                and existing.get("status") == "green_pending_review"):
            existing.update(entry)
            updated = True
            break
    if not updated:
        entry["id"] = len(slices) + 1
        slices.append(entry)

    write_tdd_progress(cwd, data)

    gap = "yes" if entry["has_research_gap"] else "no"
    plan_flag = "yes" if entry["has_plan_validity_flag"] else "no"
    facts = "yes" if entry["has_handoff_facts"] else "no"
    print(json.dumps({"systemMessage": (
        f"agent-TDD [{entry['status']}]: {entry['description']} "
        f"| AC: {entry['acceptance_criteria_status']} "
        f"| gap={gap} | plan_flag={plan_flag} | facts={facts}"
    )}))
    sys.exit(0)


if __name__ == "__main__":
    main()
