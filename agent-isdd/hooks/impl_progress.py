"""Per-feature implementation progress from agent-TDD and code-reviewer reports.

agent-TDD's tdd-progress.json is per project, and workflow-state.md isn't touched between
slices, so nothing told the boards that implementation moved. subagent_report.py feeds each
report here; <feature>/impl-progress.json then drives the Plan Board's slice count, the card's
last-report day and the end-of-turn gate. Stdlib only; every write is best-effort.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import markers  # noqa: E402

FILE = "impl-progress.json"
MAX_EVENTS = 20
_TDD = "<!--AGENT-TDD-REPORT-->"
_REVIEW = "<!--CODE-REVIEWER-REPORT-->"
_PHASE = re.compile(r"<!--AGENT-TDD-PHASE:(\w+)-->")
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


_PLAN_LINE = re.compile(r"^[ \t]*\*\*Plan\*\*[ \t]*[\u2014\u2013:-]?[ \t]*(.*)$", re.MULTILINE)


def _slice_no(report, review=False):
    """Strictly keyed slice id (markers contract), normalised; None when not explicit. TDD reports
    also accept the single '**Plan** <sep> Slice N: ...' heading line, never later prose."""
    sid = (markers.parse_review_scope(report) if review else None) or markers.parse_slice_id_strict(report)
    if not sid and not review:
        m = _PLAN_LINE.search(report)
        t = markers.SLICE_TITLE_RE.match(m.group(1)) if m else None
        sid = t.group(1) if t else None
    return markers.normalize_slice_id(sid) if sid else None


def _event(report):
    """(kind, phase, slice) for a recognised report, else None."""
    if _TDD in report:
        m = _PHASE.search(report)
        return "tdd", m.group(1) if m else None, _slice_no(report)
    if _REVIEW in report:
        return "review", None, _slice_no(report, review=True)
    return None


def record(feature_dir, report):
    """Fold one subagent report into impl-progress.json. True when it was an implementation
    report and was saved."""
    ev = _event(report or "")
    if not ev:
        return False
    kind, phase, slice_no = ev
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _fold(old_text):
        try:
            data = json.loads(old_text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            data = {"slices": {}, "allComplete": False, "events": []}
        if not isinstance(data.get("slices"), dict):
            data["slices"] = {}
        if kind == "tdd" and phase == "all_slices_complete":
            data["allComplete"] = True
        elif kind == "tdd" and slice_no and phase in ("green_pause", DONE):
            if data["slices"].get(slice_no) != DONE:
                data["slices"][slice_no] = phase
        data["events"] = (data.get("events") or [])[-(MAX_EVENTS - 1):] + [
            {"at": now, "kind": kind, "phase": phase, "slice": slice_no}]
        return json.dumps(data, indent=1, sort_keys=True)

    try:
        from sdd_state import locked_rewrite_text  # lazy: needs CLAUDE_PLUGIN_DATA; stdlib otherwise
        locked_rewrite_text(path(feature_dir), _fold, errors="replace")
    except Exception:
        return False
    return True


def summary(feature_dir):
    """{done, slices, allComplete, lastDay} or None when nothing was recorded. `lastDay` is the day
    of the last report, not the report, so the board record changes once a day, not on every report."""
    data = load(feature_dir)
    if not data:
        return None
    slices = data.get("slices") or {}
    events = data.get("events") or []
    day = str((events[-1] if events else {}).get("at") or "")[:10]
    return {"done": sum(1 for v in slices.values() if v == DONE), "slices": slices,
            "allComplete": bool(data.get("allComplete")),
            "lastDay": day if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else ""}
