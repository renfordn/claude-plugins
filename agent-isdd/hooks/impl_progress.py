"""Per-feature implementation progress from agent-TDD and code-reviewer reports.

agent-TDD's tdd-progress.json is per project, and workflow-state.md isn't touched between
slices, so nothing told the boards that implementation moved. subagent_report.py feeds each
report here; <feature>/impl-progress.json then drives the Plan Board's slice count and the
end-of-turn gate. Stdlib only; every write is best-effort.
"""
import datetime
import json
import os
import re
import tempfile

FILE = "impl-progress.json"
MAX_EVENTS = 20
_TDD = "<!--AGENT-TDD-REPORT-->"
_REVIEW = "<!--CODE-REVIEWER-REPORT-->"
_PHASE = re.compile(r"<!--AGENT-TDD-PHASE:(\w+)-->")
_SLICE = re.compile(r"\bSlice\s+(\d+)\b")
DONE = "refactor_complete"


def path(feature_dir):
    return os.path.join(feature_dir, FILE)


def load(feature_dir):
    try:
        with open(path(feature_dir), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _slice_no(report):
    """The slice number, preferring the **Plan** section (its first line names this slice) over
    any earlier mention elsewhere in the report."""
    plan = re.search(r"\*\*Plan\*\*(.*?)(?:\n\s*\n|\n\*\*|\Z)", report, re.DOTALL)
    m = _SLICE.search(plan.group(1)) if plan else None
    m = m or _SLICE.search(report)
    return m.group(1) if m else None


def _event(report):
    """(kind, phase, slice) for a recognised report, else None."""
    if _TDD in report:
        m = _PHASE.search(report)
        return "tdd", m.group(1) if m else None, _slice_no(report)
    if _REVIEW in report:
        return "review", None, _slice_no(report)
    return None


def record(feature_dir, report):
    """Fold one subagent report into impl-progress.json. True when it was an implementation
    report and was saved."""
    ev = _event(report or "")
    if not ev:
        return False
    kind, phase, slice_no = ev
    data = load(feature_dir) or {"slices": {}, "allComplete": False, "events": []}
    if kind == "tdd" and phase == "all_slices_complete":
        data["allComplete"] = True
    elif kind == "tdd" and slice_no and phase in ("green_pause", DONE):
        if data["slices"].get(slice_no) != DONE:
            data["slices"][slice_no] = phase
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["events"] = (data.get("events") or [])[-(MAX_EVENTS - 1):] + [
        {"at": now, "kind": kind, "phase": phase, "slice": slice_no}]
    try:
        fd, tmp = tempfile.mkstemp(dir=feature_dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path(feature_dir))
    except OSError:
        return False
    return True


def summary(feature_dir):
    """{done, slices, allComplete, last} or None when nothing was recorded. `last` drops `at`
    so the board record's hash changes with the event, not the clock."""
    data = load(feature_dir)
    if not data:
        return None
    slices = data.get("slices") or {}
    events = data.get("events") or []
    last = {k: v for k, v in (events[-1] if events else {}).items() if k != "at"} or None
    return {"done": sum(1 for v in slices.values() if v == DONE), "slices": slices,
            "allComplete": bool(data.get("allComplete")), "last": last}
