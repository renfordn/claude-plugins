"""Pins for design-author SKILL.md fast-track move (split from test_isdd_ref_pointers.py)."""
import re

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def _paragraph_with(text: str, needle: str) -> str:
    for para in re.split(r"\n\s*\n", text):
        if needle in para:
            return para
    return ""


def test_design_author_fast_track_moved_to_shared_fast_track_reference():
    main = (SKILLS / "design-author" / "SKILL.md").read_text(encoding="utf-8")
    ft = (SKILLS / "spec-driven-development" / "references" / "fast-track.md").read_text(encoding="utf-8")
    ptr = "../spec-driven-development/references/fast-track.md"
    assert main.count(ptr) == 1
    assert "Track: Fast" in _paragraph_with(main, ptr)
    # Moved text is verbatim in the shared reference.
    for marker in ("Ready to move to Tasks", "ready for direct Slice Spec handoff to `agent-tdd`",
                   "**Escape hatch**: if satisfying the Design Gate turns out to need real"):
        assert marker in ft, marker
    assert (SKILLS / "design-author" / "SKILL.md").stat().st_size <= 13457
