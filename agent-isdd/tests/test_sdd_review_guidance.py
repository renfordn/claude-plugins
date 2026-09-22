"""
Test: spec-driven-development SKILL.md documents review level guidance per phase.

Red Test — verify that phase-level review guidance is documented.
"""

from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "spec-driven-development"


def read_sdd_skill():
    """Read the spec-driven-development SKILL.md file, plus references/review-levels.md
    (where the v0.1.46 progressive-disclosure split moved the per-level detail -- see
    CHANGELOG.md's [0.1.46] entry), since guidance now spans both files."""
    content = (_SKILL_DIR / "SKILL.md").read_text()
    review_levels_path = _SKILL_DIR / "references" / "review-levels.md"
    if review_levels_path.exists():
        content += "\n" + review_levels_path.read_text()
    return content


def test_review_level_guidance_section_exists():
    """Test that Review Level Guidance section exists."""
    content = read_sdd_skill()
    assert "Review Level" in content and ("Guidance" in content or "guidance" in content), \
        "Review Level Guidance section not found"


def test_phase_level_guidance_documented():
    """Test that guidance is documented for each phase."""
    content = read_sdd_skill()
    phases = ["Requirements", "Design", "Tasks", "Implementation"]
    # At least one phase should be mentioned with review level guidance
    found_phases = sum(1 for phase in phases if phase in content)
    assert found_phases >= 3, f"Expected ≥3 phases mentioned, found {found_phases}"


def test_review_levels_mentioned():
    """Test that specific review levels are mentioned."""
    content = read_sdd_skill()
    levels = ["Standard", "Deep", "Ultra"]
    found_levels = sum(1 for level in levels if level in content)
    assert found_levels >= 2, f"Expected ≥2 review levels mentioned, found {found_levels}"


def test_table_format_or_list():
    """Test that guidance is presented in a structured format (table or list)."""
    content = read_sdd_skill()
    # Should have either a markdown table or structured list
    has_table = "|" in content and "-" in content
    has_structure = ("| Phase | " in content or "### Phase" in content or "- **" in content)
    assert has_table or has_structure or ("Phase" in content and "Review" in content), \
        "Guidance not presented in structured format"


def test_cross_references_present():
    """Test that cross-references to other docs are present."""
    content = read_sdd_skill()
    assert "design.md" in content or "SKILL.md" in content or "agent-tdd" in content, \
        "Cross-references to related documentation not found"


if __name__ == "__main__":
    tests = [
        test_review_level_guidance_section_exists,
        test_phase_level_guidance_documented,
        test_review_levels_mentioned,
        test_table_format_or_list,
        test_cross_references_present,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
