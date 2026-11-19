"""Pins for spec-driven-development/SKILL.md (split from test_isdd_ref_pointers.py)."""
import hashlib

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def test_sdd_turn_management_is_byte_identical():
    """Stall-bug guard. Pin deliberately updated in slice 20: pause condition 3 rewritten (requirements auto-advance; approval = ExitPlanMode or AskUserQuestion for a real gap)."""
    text = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    i = text.index("## Turn Management: Continuation Guarantee")
    j = text.index("## Internal Routing Rule")
    assert hashlib.sha256(text[i:j].encode()).hexdigest() == (
        "3f01ba0478de1315ba282dd2e60bb79c04244de682e40347a3fe0d86f44c83b8"
    )
    assert "Subagents cannot talk to the user" in text


def test_sdd_size_gate_and_second_trigger_preserved():
    sdd_dir = SKILLS / "spec-driven-development"
    main = (sdd_dir / "SKILL.md").read_text(encoding="utf-8")
    assert (sdd_dir / "SKILL.md").stat().st_size <= 9300
    assert "**Second trigger: `Current Phase: Tasks` on continue.**" in main


def _skill():
    return (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")


def test_sdd_skill_is_lean_with_io_contract():
    text = _skill()
    assert len(text.splitlines()) <= 130
    for h in ("## Input", "## Output", "## Done when"):
        assert h in text, h


def test_sdd_skill_documents_implemented_behaviour():
    text = _skill()
    for needle in ("ExitPlanMode", "AskUserQuestion", "Risk", "references/risk-depth.md",
                   "isdd-coach", "agent-tdd:tdd-parallel", "Parallel: on", "UserPromptSubmit"):
        assert needle in text, needle
    # requirements auto-advance: the old stop-for-permission wording is gone
    assert "**After Requirements approval**" not in text
    # sections now enforced by hooks / moved are deleted
    assert "## Task Tracker Sync" not in text and "## Visible Progress" not in text


def test_risk_depth_reference_lists_signals_never_diff_size():
    ref = (SKILLS / "spec-driven-development" / "references" / "risk-depth.md").read_text(encoding="utf-8")
    assert "Read by" in "\n".join(ref.splitlines()[:5])
    low = ref.lower()
    for sig in ("auth", "payments", "data migration", "security", "concurrency", "data deletion", "multi-module"):
        assert sig in low, sig
    assert "diff size" in low and "never" in low
    assert "Fast" in ref and "only rise" in low
