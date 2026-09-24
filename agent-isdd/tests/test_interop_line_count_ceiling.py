"""
Test: INTEROP.md documents research-consolidator's new line_count/ceiling
schema fields.

Red Test — verify the file_summary JSON example and research_cache field
description mention the new line-count fields before the corresponding
implementation exists.
"""

from pathlib import Path

_INTEROP_PATH = Path(__file__).resolve().parent.parent / "INTEROP.md"


def read_interop():
    """Read the current INTEROP.md file."""
    return _INTEROP_PATH.read_text()


def test_file_summary_json_example_includes_line_count():
    """Test that the file_summary JSON example includes a line_count key."""
    content = read_interop()
    assert '"line_count"' in content, \
        "file_summary JSON example does not include a \"line_count\" key"


def test_research_cache_field_description_mentions_ceiling():
    """Test that the Design Spec field table's research_cache row mentions the
    line-count ceiling."""
    content = read_interop()
    row_start = content.index("| research_cache |")
    row_end = content.index("\n", row_start)
    row = content[row_start:row_end]

    assert "ceiling" in row.lower(), \
        "research_cache field table row does not mention the line-count ceiling"


if __name__ == "__main__":
    tests = [
        test_file_summary_json_example_includes_line_count,
        test_research_cache_field_description_mentions_ceiling,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
