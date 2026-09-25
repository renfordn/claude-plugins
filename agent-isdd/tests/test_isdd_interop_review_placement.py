"""
Test: agent-isdd INTEROP.md documents Strategic Review Placement.

Red Test — verify that Strategic Review Placement table and Ralph Loops integration are documented.
"""

from pathlib import Path

_INTEROP_PATH = Path(__file__).resolve().parent.parent / "INTEROP.md"


def read_isdd_interop():
    """Read the agent-isdd INTEROP.md file."""
    return _INTEROP_PATH.read_text()


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
    """Test that the note explaining review levels replaced hook-driven auto-invocation is
    present. Corrected 2026-09-25: the original wording ("Alternative to abandoned hook
    pipeline") was later reworded to "(Current Approach)" / "Rather than hooks managing
    invocation" and no longer contains "abandon" anywhere in the file, so the old substring
    check only kept passing by coincidence (unrelated "hook" and "pipeline" hits elsewhere)."""
    content = read_isdd_interop()
    assert "(Current Approach)" in content, \
        "Note marking review levels as the current (vs. a prior) approach not found"
    assert "Rather than hooks managing invocation" in content, \
        "Note that hooks no longer manage review invocation not found"


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
