"""
Test: design-author SKILL.md documents Deep review gate before Tasks phase.

Red Test — verify that Deep review invocation is documented in design-author.
"""


def read_design_author_skill():
    """Read the current design-author SKILL.md file."""
    with open("/Users/jay.nelson/Codebase/Claude-Plugins/agent-isdd/skills/design-author/SKILL.md", "r") as f:
        return f.read()


def test_deep_review_gate_documented():
    """Test that Deep review gate is documented before Tasks phase."""
    content = read_design_author_skill()
    # Should mention Deep review before advancing to Tasks
    assert "Deep" in content and "review" in content.lower(), \
        "Deep review not mentioned in design-author SKILL.md"


def test_design_validation_section_exists():
    """Test that Design Validation section exists."""
    content = read_design_author_skill()
    assert "Design Validation" in content or "Deep Review" in content or ("Deep" in content and "design" in content.lower()), \
        "Design Validation/Deep Review section not found"


def test_review_invocation_step_documented():
    """Test that /code-reviewer invocation step is documented."""
    content = read_design_author_skill()
    # Should mention invoking /code-reviewer or code-reviewer skill
    assert "code-reviewer" in content.lower() or "/code-reviewer" in content, \
        "/code-reviewer invocation not documented"


def test_gate_logic_documented():
    """Test that gate logic (block on critical findings) is documented."""
    content = read_design_author_skill()
    # Should describe what to do with findings
    assert ("gate" in content.lower() or "block" in content.lower() or "critical" in content.lower()), \
        "Gate logic/blocking on findings not documented"


def test_review_focus_documented():
    """Test that review focus areas are documented."""
    content = read_design_author_skill()
    # Should describe what Deep review should focus on for design
    assert ("design" in content.lower() or "coherence" in content.lower() or "pattern" in content.lower()), \
        "Deep review focus not documented"


if __name__ == "__main__":
    tests = [
        test_deep_review_gate_documented,
        test_design_validation_section_exists,
        test_review_invocation_step_documented,
        test_gate_logic_documented,
        test_review_focus_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
