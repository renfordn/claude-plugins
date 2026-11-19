"""Slice 23: fast-track.md / start-protocol.md use Risk (Fast only when Risk low)."""
import re
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "skills" / "spec-driven-development" / "references"
FT = (REFS / "fast-track.md").read_text(encoding="utf-8")
SP = (REFS / "start-protocol.md").read_text(encoding="utf-8")


def _para(text, token):
    return next(p for p in re.split(r"\n\s*\n", text) if token in p)


def test_fast_track_ties_fast_to_risk_low_and_points_to_risk_depth():
    p = " ".join(_para(FT, "Risk").split())
    assert "Risk is low" in p
    assert "references/risk-depth.md" in p


def test_fast_track_breadcrumb_pointer_no_visible_progress():
    assert "Visible Progress" not in FT
    assert "references/ux-conventions.md" in FT and "Breadcrumb" in FT


def test_start_protocol_risk_before_track_with_separate_reason_line():
    p = " ".join(_para(SP, "Classify Risk first").split())
    assert "references/risk-depth.md" in p
    assert "`- Risk: low`" in p and "`- Risk Reason:" in p
    assert p.index("Classify Risk first") < p.index("Track: Fast")


def test_pinned_markers_and_triggers_kept():
    for m in ("Ready to move to Tasks", "ready for direct Slice Spec handoff to `agent-tdd`",
              "**Escape hatch**", "Review handoff mode: skip"):
        assert m in FT
    assert "intent/intent.md" in SP and "Fast Track classification" in SP
