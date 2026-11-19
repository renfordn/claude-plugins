"""Release 2 coherence-review doc fixes (slice 35C): pin each lead decision in the docs."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _t(rel):
    return (ROOT / rel).read_text()


def _flat(rel):
    return re.sub(r"\s+", " ", _t(rel))


HANDOFF = "skills/spec-driven-development/references/implementation-handoff.md"
INTEROP = "references/interop-agent-tdd.md"
COACH = "skills/isdd-coach/SKILL.md"
CHECKPOINT = "skills/spec-driven-development/references/code-reviewer-checkpoint.md"
REWIND_REF = "skills/workflow-manager/references/rewind-and-rollback.md"
REWIND_CMD = "commands/isdd-rewind.md"


def test_f2_user_mode_still_slices_via_agent_tdd():
    for rel in (HANDOFF, INTEROP):
        t = _flat(rel)
        assert "slicing_complete" in t
        assert "must not resume agent-TDD to implement" in t, rel
        assert "only slices" in t, rel
    assert "skip the agent-TDD spawn entirely" not in _flat(HANDOFF)
    c = _flat(COACH)
    assert "single Slice Spec" in c
    assert "slicing_complete" in c


def test_f7_tasks_path_explicit():
    for rel in (HANDOFF, INTEROP):
        assert "<feature spec dir>/tasks/tasks.md" in _t(rel), rel
    h = _flat(HANDOFF)
    for hook in ("high_risk_reviewer", "review_tracking", "complete_guard"):
        assert hook in h


def test_coach_uses_stated_mode_without_asking():
    for rel in (HANDOFF, COACH):
        c = _flat(rel)
        assert "already stated" in c, rel
        assert "without asking" in c, rel
        assert "only when the mode is not stated" in c.lower(), rel


def test_f4_rewind_clears_rollback_pending():
    for rel in (REWIND_CMD, REWIND_REF):
        t = _flat(rel)
        assert "rollback_pending" in t or rel == REWIND_CMD, rel
        assert "earlier" in t or rel == REWIND_CMD, rel
    r = _flat(REWIND_REF)
    assert "equals, or is earlier than, `rollback_pending.target`" in r
    assert "Requirements < Design < Tasks" in r
    assert "sdd_state.clear_rollback_pending('<feature dir>/workflow-state.json')" in r
    assert "clear_rollback_pending" not in _flat(REWIND_CMD)
    assert "skip this spawn" in _flat(HANDOFF) and "slice 1" in _flat(HANDOFF)
    assert "slice 1" in _flat(COACH) and "slice-spec" in _flat(COACH)
    assert "before_continue" in r and "resume_context" in r


def test_f5_checkpoint_current_contract():
    t = _flat(CHECKPOINT)
    for must in ("sole writer", "subagent_dispatch", "high_risk_reviewer.main",
                 "review_tracking.evaluate", "<!--CODE-REVIEWER-REPORT-->",
                 "<!--REVIEW-SCOPE: slice=N-->", "Review scope: slice=N",
                 "complete_guard", "Risk: high", "stop_check",
                 "Accepted via AskUserQuestion: <ids|all>: <reason>", "reviewed"):
        assert must in t, must
    for gone in ("code_reviewer_tracking", "reviewed_phases", "classify_severity",
                 "update_reviewed_phases", "Unused helpers"):
        assert gone not in t, gone
