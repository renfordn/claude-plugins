"""
Test: agent-isdd INTEROP.md documents Strategic Review Placement.

Red Test — verify that Strategic Review Placement table and Ralph Loops integration are documented.
"""


def read_isdd_interop():
    """Read the agent-isdd INTEROP.md file."""
    with open("/Users/jay.nelson/Codebase/Claude-Plugins/agent-isdd/INTEROP.md", "r") as f:
        return f.read()


def test_strategic_review_placement_section_exists():
    """Test that Strategic Review Placement section exists."""
    content = read_isdd_interop()
    assert "Strategic Review Placement" in content or ("Review" in content and "Phase" in content), \
        "Strategic Review Placement section not found"


def test_review_placement_table_present():
    """Test that a table documenting review placement by phase exists."""
    content = read_isdd_interop()
    # Should have a table with pipe characters (markdown table)
    has_table = "| Phase |" in content or ("|" in content and "Review" in content)
    assert has_table or ("Requirements" in content and "Design" in content and "review" in content.lower()), \
        "Review placement table not found"


def test_ralph_loops_integration_documented():
    """Test that Ralph Loops integration is documented."""
    content = read_isdd_interop()
    assert "ralph loop" in content.lower() or "ralph loops" in content.lower(), \
        "Ralph Loops integration not documented"


def test_abandoned_hook_pipeline_note_added():
    """Test that note about abandoned hook-driven pipeline is present."""
    content = read_isdd_interop()
    assert "abandon" in content.lower() or ("hook" in content.lower() and "pipeline" in content), \
        "Note about abandoned hook-driven pipeline not found"


def test_ultra_level_as_alternative_noted():
    """Test that Ultra review level is noted as alternative to hooks."""
    content = read_isdd_interop()
    assert "Ultra" in content, \
        "Ultra review level not documented in agent-isdd INTEROP.md"


def test_auto_detection_note_present():
    """Test that note about auto-detection living in calling code is present."""
    content = read_isdd_interop()
    assert ("auto-detect" in content.lower() or "auto detection" in content.lower()) and \
           ("caller" in content or "calling code" in content), \
        "Auto-detection note not found"


if __name__ == "__main__":
    tests = [
        test_strategic_review_placement_section_exists,
        test_review_placement_table_present,
        test_ralph_loops_integration_documented,
        test_abandoned_hook_pipeline_note_added,
        test_ultra_level_as_alternative_noted,
        test_auto_detection_note_present,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
