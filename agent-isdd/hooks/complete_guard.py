#!/usr/bin/env python3
"""complete_guard: PreToolUse guard (called by pre_write_dispatch) that denies a write to the
active workflow-state.md which sets `Workflow Status` to Complete while review evidence is missing.

Rules (evaluated on the post-write text from sdd_state.simulate_write, so a single write that adds
a Review Fallback and sets Complete is judged with that fallback):
- High-risk slices per tasks.md Risk Tier need a `reviewed` entry or a Review Fallback naming them.
- Feature-level `Risk: high`: every slice in tasks.md needs a reviewed entry (ids not in tasks.md
  don't count) or a fallback naming it; with no tasks.md, at least one reviewed entry. Only a
  fallback of `all` waives the feature-level rule; unknown ids in a fallback waive nothing.
- Review Fallback counts only as `Accepted via AskUserQuestion: <ids|all>: <reason>`.
- A write to a state file that is already Complete is not denied.
Fails open on any missing/odd input.

Known limits: Bash writes are not covered (the Stop backstop catches them); the evidence stores
(workflow-state.json `reviewed`, the Review Fallback line) are agent-writable, so provenance is not
verifiable by hooks; tasks.md Risk Tier edits are trusted.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import markers
import review_tracking
import sdd_state


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def _status(text):
    for line in (text or "").splitlines():
        m = sdd_state.match_field(line)
        if m and m[0] == "workflow status":
            return m[1].strip().lower()
    return ""


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _fields_from_text(text):
    fields = {}
    for line in (text or "").splitlines():
        m = sdd_state.match_field(line)
        if m and m[0] not in fields:
            fields[m[0]] = m[1]
    return fields


def _tasks_text(feature_dir):
    return _read(os.path.join(feature_dir, "tasks", "tasks.md"))


def _reviewed_ids(feature_dir):
    reviewed = sdd_state.read_reviewed(os.path.join(feature_dir, "workflow-state.json"))
    return {markers.normalize_slice_id(str(k)) for k, v in reviewed.items() if v}


def feature_unreviewed(feature_dir, fields):
    """Unreviewed slice ids under the feature-level `Risk: high` rule ([] when not applicable or
    satisfied; ["(feature)"] when there is no tasks.md and nothing is reviewed)."""
    if (fields.get("risk") or "").strip().lower() != "high":
        return []
    waived = review_tracking._fallback_ids(fields.get("review fallback"))
    if waived is None:
        return []
    reviewed = _reviewed_ids(feature_dir)
    ids = []
    for m in review_tracking._HEADING.finditer(_tasks_text(feature_dir)):
        sid = markers.normalize_slice_id(m.group(1))
        if sid not in ids:
            ids.append(sid)
    if not ids:
        return [] if reviewed else ["(feature)"]
    return [i for i in ids if i not in reviewed and i not in waived]


def _unreviewed(feature_dir, fields):
    tier = review_tracking.high_risk_slices(_tasks_text(feature_dir))
    waived = review_tracking._fallback_ids(fields.get("review fallback"))
    out = []
    if waived is not None:
        reviewed = _reviewed_ids(feature_dir)
        out = [i for i in tier if i not in waived and i not in reviewed]
    for i in feature_unreviewed(feature_dir, fields):
        if i not in out:
            out.append(i)
    return out


def _deny_text(ids):
    if ids == ["(feature)"]:
        names = "this high-risk feature has"
    else:
        names = "high-risk slice(s) " + ", ".join(ids) + " have"
    return (
        "Cannot set Workflow Status to Complete: %s no code-reviewer review recorded. "
        "Either (1) spawn code-reviewer with `Review scope: slice=N` for each unreviewed slice, or "
        "(2) ask the user via AskUserQuestion and record the answer as "
        "`- Review Fallback: Accepted via AskUserQuestion: <slice ids | all>: <reason>`." % names)


def evaluate(payload, state_path=None):
    """Return a deny reason (str) when a write sets Complete with unreviewed high-risk slices,
    else None. `state_path` is the active workflow-state.md resolved by pre_write_dispatch."""
    if not state_path or not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    target = tool_input.get("file_path")
    if not isinstance(target, str) or not target or not _same_file(target, state_path):
        return None
    current = _read(state_path)
    new = sdd_state.simulate_write(payload.get("tool_name"), tool_input, current)
    if _status(new) != "complete" or _status(current) == "complete":
        return None
    feature_dir = os.path.dirname(os.path.abspath(state_path))
    unreviewed = _unreviewed(feature_dir, _fields_from_text(new))
    return _deny_text(unreviewed) if unreviewed else None


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
