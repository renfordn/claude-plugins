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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from tdd_state import (update_json, progress_path,  # noqa: E402
                       extract_last_assistant_text, TAIL_BYTES)
from markers import (parse_slice_id_strict, normalize_slice_id as _norm, _section_text,  # noqa: E402
                     EVIDENCE_PHASES, parse_outcome, parse_blocked)
import tdd_check  # noqa: E402

# Lookup only needs phase + token (the log is the source of truth), so exit/status are optional.
EVIDENCE_TOKEN_RE = re.compile(r"TDD-EVIDENCE (?P<phase>" + "|".join(EVIDENCE_PHASES) + r") (?P<token>[0-9a-f]{8})")

REPORT_MARKER = "<!--AGENT-TDD-REPORT-->"
PHASE_RE = re.compile(r"<!--AGENT-TDD-PHASE:(\w+)-->")
PLAN_FLAG_RE = re.compile(r'<!--AGENT-TDD-PLAN-FLAG:\s*reason="[^"]*"-->')
SECTION_RE = re.compile(r"^\*\*([^*]+)\*\*", re.MULTILINE)

_extract_last_assistant_text = extract_last_assistant_text  # compat alias


FEATURE_RE = re.compile(
    r"<!--\s*(?:FEATURE|SPEC):\s*([^>]*?)\s*-->|^\s*(?:Feature|Spec)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE)


def _feature(text):
    m = FEATURE_RE.search(text)
    return (m.group(1) or m.group(2)).strip() if m else None


def _parse_report(text):
    """Parse an agent-TDD handoff report and return a slice dict."""
    # Phase
    phase_m = PHASE_RE.search(text)
    status = "refactor_complete" if (phase_m and phase_m.group(1) == "refactor_complete") \
        else "green_pending_review"
    if parse_blocked(text) is not None:
        status = "blocked"

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

    blocked_reason = parse_blocked(text)
    return {
        **({"blocked_reason": blocked_reason} if blocked_reason else {}),
        "evidence": {},
        "description": description or "(no description)",
        "status": status,
        "acceptance_criteria_status": ac_status,
        "has_research_gap": has_research_gap,
        "has_plan_validity_flag": has_plan_flag,
        "has_handoff_facts": has_handoff_facts,
        "timestamp": datetime.datetime.now().isoformat(),
    }


def _evidence(text, cwd):
    """{"red": ..., "green": ...} always, plus "coverage" / "bypass" when the report carries such a
    token; each "verified"|"not confirmed"|"unrecorded"|"missing" (bypass: the logged reason when
    verified). Checked against scripts/tdd_check.py's log (the last token per phase wins)."""
    tokens = {}
    for m in EVIDENCE_TOKEN_RE.finditer(text):
        tokens[m.group("phase")] = m.group("token")
    logged = tdd_check.verify(list(tokens.values()), cwd) if tokens else {}
    out = {}
    for phase in ("red", "green", "coverage", "bypass"):
        t = tokens.get(phase)
        if phase in ("coverage", "bypass") and not t:
            continue
        e = logged.get(t) if t else None
        if not t:
            out[phase] = "missing"
        elif e is None or e.get("phase") != phase:
            out[phase] = "unrecorded"
        elif not e.get("confirmed"):
            out[phase] = "not confirmed"
        elif phase == "bypass":
            out[phase] = e.get("reason") or "verified"
        else:
            out[phase] = "verified"
    return out


def _start_info(text, cwd):
    """(kind, multiple) of the slice's start: the report's start token if it has one, else the latest
    start in the log for the slice title of the report's other evidence tokens. (None, False) if unknown."""
    tokens = {m.group("token"): m.group("phase") for m in EVIDENCE_TOKEN_RE.finditer(text)}
    if not tokens:
        return None, False
    log = tdd_check.read_log(cwd)
    by_token = {e.get("token"): e for e in log}
    title = None
    start = None
    for t in tokens:
        e = by_token.get(t)
        if not e:
            continue
        if e.get("phase") == "start":
            start = e
        title = title or e.get("slice")
    starts = [e for e in log if e.get("phase") == "start" and e.get("slice") == title] if title else []
    if start is None and starts:
        start = starts[-1]
    return (start.get("kind") if start else None), len(starts) > 1


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    # transcript_path is the parent session's transcript; the subagent's report is in
    # last_assistant_message (or agent_transcript_path) on current Claude Code.
    text, truncated = payload.get("last_assistant_message") or "", False
    if not text:
        transcript_path = payload.get("agent_transcript_path") or payload.get("transcript_path", "")
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
    entry["evidence"] = _evidence(text, cwd)

    slice_id = parse_slice_id_strict(text)
    feature = _feature(text)
    if slice_id:
        entry["slice"] = slice_id
    if feature:
        entry["feature"] = feature

    def _upsert(data):
        slices = data.get("slices")
        if not isinstance(slices, list):
            slices = data["slices"] = []
        match = None
        for existing in slices:
            if slice_id:
                if (_norm(existing.get("slice")) == slice_id
                        and existing.get("status") != "refactor_complete"
                        and existing.get("feature") == feature):
                    match = existing
                    break
            elif (existing.get("description") == entry["description"]
                    and existing.get("status") in ("green_pending_review", "blocked")):
                match = existing
                break
        if match is not None:
            match.pop("blocked_reason", None)
            match.update(entry)
        else:
            ids = [s.get("id") for s in slices if isinstance(s.get("id"), int)]
            entry["id"] = max(ids, default=0) + 1
            slices.append(entry)
        return data

    path = progress_path(cwd)
    update_json(path, _upsert)

    gap = "yes" if entry["has_research_gap"] else "no"
    plan_flag = "yes" if entry["has_plan_validity_flag"] else "no"
    facts = "yes" if entry["has_handoff_facts"] else "no"
    ev = entry["evidence"]
    evidence = f"red={ev['red']} green={ev['green']}"
    if "coverage" in ev:
        evidence += f" coverage={ev['coverage']}"
    if "bypass" in ev:
        evidence += f" bypass={ev['bypass']}"
    blocked = parse_blocked(text)
    outcome = parse_outcome(text)
    coverage_only = outcome == "coverage-only" and ev.get("coverage") == "verified" and ev["green"] == "missing"
    proven = (ev["green"] == "verified" and (ev["red"] == "verified" or (
        ev.get("coverage") == "verified" and outcome == "refactor"))) or coverage_only
    warn = "" if proven or blocked is not None else (
        " — ⚠ Red→Green was not verified by scripts/tdd_check.py; treat the TDD claim as unproven "
        "and check the tests yourself before accepting the slice.")
    kind, multi = _start_info(text, cwd)
    evidence += f" outcome={outcome or 'none'} kind={kind or 'unknown'}" + (" (multiple starts)" if multi else "")
    print(json.dumps({"systemMessage": (
        f"agent-TDD [{entry['status']}]: {entry['description']} "
        f"| AC: {entry['acceptance_criteria_status']} "
        f"| gap={gap} | plan_flag={plan_flag} | facts={facts} | {evidence}{warn}"
        + (f" | blocked: {blocked}" if blocked is not None else "")
    )}))
    sys.exit(0)


if __name__ == "__main__":
    main()
