"""Pins for spec-driven-development/SKILL.md (split from test_isdd_ref_pointers.py)."""
import hashlib

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def test_sdd_turn_management_is_byte_identical():
    """Stall-bug guard: the Continuation Guarantee section must never be moved or reworded."""
    text = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    i = text.index("## Turn Management: Continuation Guarantee")
    j = text.index("## Internal Routing Rule")
    assert hashlib.sha256(text[i:j].encode()).hexdigest() == (
        "3c862a522c491ddde750bb32bd6cb3636a80884b384c6f963c70751f6f4b69a4"
    )
    assert "Subagents cannot talk to the user" in text


def test_sdd_size_gate_and_second_trigger_preserved():
    sdd_dir = SKILLS / "spec-driven-development"
    main = (sdd_dir / "SKILL.md").read_text(encoding="utf-8")
    assert (sdd_dir / "SKILL.md").stat().st_size <= 13580
    assert "**Second trigger: `Current Phase: Tasks` on continue.**" in main
