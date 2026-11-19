"""INTEROP.md is split: a short index plus references/interop-*.md, with the Parallel handoff documented."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEROP = (ROOT / "INTEROP.md").read_text(encoding="utf-8")
TDD = ROOT / "references" / "interop-agent-tdd.md"
REV = ROOT / "references" / "interop-reviewers.md"


def _read(p):
    assert p.is_file(), p
    return p.read_text(encoding="utf-8")


def test_interop_under_ceiling_and_points_at_references():
    assert len(INTEROP.splitlines()) < 400
    assert "references/interop-agent-tdd.md" in INTEROP
    assert "references/interop-reviewers.md" in INTEROP


def test_sections_kept_in_index_for_other_docs():
    for needle in ("## → agent-nelly (memory)", "## → Plan Board (Artifact page)", "Research Digest Cache"):
        assert needle in INTEROP, needle


def test_agent_tdd_reference_documents_parallel_handoff():
    t = _read(TDD)
    for needle in ("Parallel: on", "wave plan", "agent-tdd:tdd-parallel", "all_slices_complete",
                   "Implementation Mode", "isdd-coach", "Track: Fast", "Fallback — Direct Implementation",
                   "Test-Author Gate", "Research Validation"):
        assert needle in t, needle


def test_agent_tdd_reference_describes_current_gates():
    t = _read(TDD)
    for needle in ("Implementation Requested", "approval hash", "approval.py", "approve", "refreeze",
                   "AskUserQuestion", "user_led_guard", "high_risk_reviewer", "design_spec_gate"):
        assert needle in t, needle
    assert "Read-only; never" not in t


def test_reviewers_reference_documents_tracking_and_user_commands():
    r = _read(REV)
    for needle in ("Review scope: slice=", "<!--CODE-REVIEWER-REPORT-->", "<!--REVIEW-SCOPE: slice=N-->", "Risk: high", "Accepted via AskUserQuestion", "complete_guard", "review_tracking",
                   "/isdd-rewind", "/isdd-board-sync", "disable-model-invocation", "Strategic Review Placement",
                   "rollback_pending", "SDD-ROLLBACK-REQUEST"):
        assert needle in r, needle


def test_serial_vs_parallel_framing_in_moved_prose():
    t = _read(TDD)
    assert "serial runs only" in t
    gate = t.split("**Exception — Test-Author Gate")[1][:1500]
    assert "serial" in gate.lower() and "Parallel" in gate
    ready = t.split("**After Tasks readiness passes:**")[1][:1500]
    assert "serial" in ready.lower() and "Parallel" in ready
    assert "Review scope: slice=<ID>" in t
    assert "one-directional" in t and "Track: Fast" in t.split("one-directional")[1][:400]


def test_no_read_only_claim_and_reviewers_frames_rewind_as_user_run():
    assert "Read-only" not in _read(TDD)
    r = _read(REV)
    assert "/isdd-rewind <target>" in r and "user-run" in r
    assert "(rollback-guide.md)" in r and "references/rollback-guide.md`](" not in r
    assert "review-levels.md" in r.split("Tasks-phase Standard review")[1][:200]
    assert "hooks never invoke" in r.lower() or "hooks cannot invoke" in r.lower()
