"""Slice 26: design-author SKILL.md is user-invocable false and uses Risk-based depth wording."""
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "design-author" / "SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")
FRONT = TEXT.split("---")[1]


def test_frontmatter_user_invocable_false_without_internal_prefix():
    assert re.search(r"^user-invocable: false$", FRONT, re.M)
    assert "[Internal" not in FRONT
    assert "Invoked by /isdd" in FRONT


def test_plan_reviewer_skip_keyed_on_recorded_track_fast():
    bullet = " ".join(next(b for b in re.split(r"\n\s*-\s", TEXT) if "Skip this step only when" in b).split())
    assert "`Track: Fast` is recorded" in bullet
    assert "Risk low" in bullet
    assert "spec-driven-development/references/fast-track.md" in bullet
    assert "trivial, low-risk change" not in TEXT
