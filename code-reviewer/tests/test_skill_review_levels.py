"""
Test: SKILL.md documents review levels correctly.

Red Test — verify that review level definitions are present and complete.
"""

import re


def read_skill_md():
    """Read the current SKILL.md file."""
    with open("/Users/jay.nelson/Codebase/Claude-Plugins/code-reviewer/skills/code-reviewer/SKILL.md", "r") as f:
        return f.read()


def test_review_level_parameter_section_exists():
    """Test that review_level parameter section is documented."""
    content = read_skill_md()
    assert "review_level" in content, "review_level parameter not documented in SKILL.md"
    assert "Quick | Standard | Deep | Ultra" in content or ("Quick" in content and "Standard" in content and "Deep" in content and "Ultra" in content), \
        "Not all 4 review levels documented"


def test_all_four_levels_documented():
    """Test that all 4 review levels have required subsections."""
    content = read_skill_md()

    for level in ["Quick", "Standard", "Deep", "Ultra"]:
        assert level in content, f"Review level '{level}' not found in SKILL.md"

        # Each level should have multiple references (name, purpose, checks, etc.)
        count = content.count(level)
        assert count >= 3, f"Review level '{level}' mentioned too few times ({count}); expected ≥3 (name, purpose, use case)"


def test_all_required_fields_per_level():
    """Test that each level has the required documentation fields."""
    content = read_skill_md()
    required_fields = ["Purpose", "Checks", "Skipped", "Token Budget", "Use Cases", "Output Style"]

    # Look for review level section and verify required fields are mentioned
    assert "Purpose" in content, "'Purpose' field not found in review level docs"
    assert "Token Budget" in content or "token" in content.lower(), "'Token Budget' field not found"
    assert "Output Style" in content or "Skipped" in content, "'Output Style' or 'Skipped' field not found"


def test_auto_detection_rules_section_exists():
    """Test that Auto-Detection Rules section is present."""
    content = read_skill_md()
    assert "Auto-Detection" in content, "Auto-Detection Rules section not found"

    # Verify priority order is documented (explicit, phase, file scope, prior context, fallback)
    assert "Explicit" in content or "explicit" in content, "Explicit request priority not documented"
    assert "phase" in content.lower() or "Phase" in content, "Phase context priority not documented"
    assert "File" in content or "file" in content, "File scope priority not documented"


def test_graceful_degradation_section_exists():
    """Test that Graceful Degradation section is present."""
    content = read_skill_md()
    assert "Degradation" in content or "degrade" in content.lower(), \
        "Graceful Degradation section not found in SKILL.md"
    assert "Ultra" in content, "Ultra level degradation not documented"


def test_cross_references_to_design():
    """Test that cross-references to design.md are present."""
    content = read_skill_md()
    # Should reference design.md for design rationale
    assert "design.md" in content.lower() or "Design" in content, \
        "Cross-references to design.md not found"


if __name__ == "__main__":
    # Run tests to show failures
    tests = [
        test_review_level_parameter_section_exists,
        test_all_four_levels_documented,
        test_all_required_fields_per_level,
        test_auto_detection_rules_section_exists,
        test_graceful_degradation_section_exists,
        test_cross_references_to_design,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
