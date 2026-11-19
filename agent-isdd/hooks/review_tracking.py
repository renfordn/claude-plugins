#!/usr/bin/env python3
"""review_tracking: which high-risk slices have a code-reviewer run recorded.

Risk-tier parsing is copied from high_risk_reviewer.py (which later delegates here). Only
code-reviewer subagent stops count as reviews. Reviews persist via sdd_state.mark_reviewed.
Hook entry fails open: no workflow, no decision -> exit 0, no output."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import markers
import sdd_state

_HEADING = re.compile(r"^#{2,3}\s+(?:Slice|Phase)\s+(" + markers.ID + r")\s*:", re.MULTILINE | re.IGNORECASE)
_TIER_NEW = re.compile(r"\*\*Risk Tier:\*\*\s+(high-risk|standard)", re.IGNORECASE)
_TIER_OLD = re.compile(r"###\s+Risk Tier\s*\n\s*-\s*`(high-risk|standard)`", re.IGNORECASE)
_FALLBACK = re.compile(r"^Accepted via AskUserQuestion:\s*([^:]+?)\s*:\s*(\S.*)$", re.IGNORECASE)
REPORT_MARKER = "<!--CODE-REVIEWER-REPORT-->"


def high_risk_slices(tasks_md_text):
    """Normalized ids of slices whose Risk Tier is high-risk, in document order."""
    text = tasks_md_text or ""
    heads = list(_HEADING.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.start():end]
        tier = _TIER_NEW.search(body) or _TIER_OLD.search(body)
        if tier and tier.group(1).lower() == "high-risk":
            out.append(markers.normalize_slice_id(m.group(1)))
    return out


def record_review(state_json_path, slice_id):
    """Persist a review for `slice_id` (normalized) via sdd_state.mark_reviewed."""
    try:
        sdd_state.mark_reviewed(state_json_path, markers.normalize_slice_id(str(slice_id)))
    except OSError:
        pass  # fail open: an unwritable state path must never break a hook


def _fallback_ids(value):
    """Slice ids waived by an explicit `Accepted via AskUserQuestion: <ids|all>: <reason>`
    Review Fallback; None means all slices; an empty set means nothing is waived (any other text)."""
    m = _FALLBACK.match((value or "").strip())
    if not m:
        return set()
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    if any(n.lower() == "all" for n in names):
        return None
    return {markers.normalize_slice_id(n) for n in names if re.fullmatch(markers.ID, n)}


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _reviewed_ids(feature_dir):
    reviewed = sdd_state.read_reviewed(os.path.join(feature_dir, "workflow-state.json"))
    return {markers.normalize_slice_id(str(k)) for k, v in reviewed.items() if v}


def unreviewed(feature_dir, fields=None):
    """The single review-gate rule. Slice ids still needing review ([] when satisfied):
    - high-risk-tier slices (tasks.md) with no reviewed entry;
    - when the feature-level `Risk` is high (first token), every tasks.md slice with no reviewed
      entry (no tasks.md: ["(feature)"] unless something is reviewed).
    The Review Fallback in `fields` (default: parsed from workflow-state.md) waives the ids it
    names; `all` waives everything. complete_guard passes the simulated post-write fields."""
    if fields is None:
        fields = sdd_state.parse_state(os.path.join(feature_dir, "workflow-state.md"))
    waived = _fallback_ids(fields.get("review fallback"))
    if waived is None:
        return []
    tasks = read_text(os.path.join(feature_dir, "tasks", "tasks.md"))
    reviewed = _reviewed_ids(feature_dir)
    out = [i for i in high_risk_slices(tasks) if i not in waived and i not in reviewed]
    risk = (fields.get("risk") or "").strip().lower().split()
    if risk and risk[0] == "high":
        ids = []
        for m in _HEADING.finditer(tasks):
            sid = markers.normalize_slice_id(m.group(1))
            if sid not in ids:
                ids.append(sid)
        if not ids:
            extra = [] if reviewed else ["(feature)"]
        else:
            extra = [i for i in ids if i not in reviewed and i not in waived]
        out += [i for i in extra if i not in out]
    return out


def unreviewed_high_risk(feature_dir):
    """Tier-rule-only view of `unreviewed` (ignores feature-level Risk); used by the checkpoint."""
    fields = dict(sdd_state.parse_state(os.path.join(feature_dir, "workflow-state.md")))
    fields.pop("risk", None)
    return unreviewed(feature_dir, fields)


def is_code_reviewer_stop(payload):
    """True only for a code-reviewer subagent stop whose report carries the report marker."""
    payload = payload or {}
    agent = str(payload.get("agent_type") or "")
    if agent.split(":")[-1].lower() != "code-reviewer":
        return False
    return REPORT_MARKER in _report_text(payload)


def _report_text(payload):
    """Final subagent message: last_assistant_message, else the tail of agent_transcript_path
    (mirrors subagent_report.report_text_from_payload; fails open to "")."""
    # Deliberately differs from subagent_report.report_text_from_payload: never falls back to the
    # parent session's transcript_path (it could hold another agent's marker and scope).
    text = payload.get("last_assistant_message")
    if isinstance(text, str) and text:
        return text
    try:
        from subagent_report import extract_last_assistant_text
        return extract_last_assistant_text(payload.get("agent_transcript_path") or "")
    except Exception:
        return ""


def record_from_payload(payload, state_json_path):
    """On a code-reviewer stop whose report carries a REVIEW-SCOPE marker, record that slice."""
    if not is_code_reviewer_stop(payload):
        return None
    text = _report_text(payload)
    slice_id = markers.parse_review_scope(text)
    if not slice_id:
        return None
    record_review(state_json_path, slice_id)
    return markers.normalize_slice_id(slice_id)


def evaluate(payload):
    state_path = sdd_state.active_state_file(payload.get("cwd") or os.getcwd())
    if not state_path:
        return None
    record_from_payload(payload, os.path.join(os.path.dirname(state_path), "workflow-state.json"))
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    try:
        evaluate(payload if isinstance(payload, dict) else {})
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
