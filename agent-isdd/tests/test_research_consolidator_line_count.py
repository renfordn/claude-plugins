"""
Test: research-consolidator documents per-file line-count reporting and
repo line-count-ceiling resolution.

Red Test — verify that the new line-count instructions are documented in
research-consolidator.md before the corresponding implementation exists.
"""

from pathlib import Path

_AGENT_PATH = (
    Path(__file__).resolve().parent.parent / "agents" / "research-consolidator.md"
)


def read_research_consolidator():
    """Read the current research-consolidator.md file."""
    return _AGENT_PATH.read_text()


def test_line_count_field_in_file_summaries_schema():
    """Test that line_count field is documented in the File Summaries schema."""
    content = read_research_consolidator()
    assert "line_count" in content, \
        "line_count field not documented in File Summaries schema"


def test_grep_count_mode_method_documented():
    """Test that the Grep count-mode method for computing line_count is documented."""
    content = read_research_consolidator()
    assert 'pattern: "^"' in content, \
        'Grep pattern "^" not documented as the line-count method'
    assert 'output_mode: "count"' in content, \
        'Grep output_mode "count" not documented as the line-count method'


def test_no_read_line_numbering_guardrail_documented():
    """Test that the guardrail against using Read's own line numbers is documented."""
    content = read_research_consolidator()
    lowered = content.lower()
    assert "read" in lowered and "truncat" in lowered, \
        "Guardrail against Read's own line numbering (which truncates for large files) not documented"


def test_agents_claude_md_lookup_step_documented():
    """Test that an AGENTS.md/CLAUDE.md lookup step for the line-count ceiling is documented."""
    content = read_research_consolidator()
    assert "AGENTS.md" in content, \
        "AGENTS.md lookup step not documented"
    assert "CLAUDE.md" in content, \
        "CLAUDE.md lookup step not documented"


def test_range_resolves_to_upper_bound_documented():
    """Test that the rule resolving a stated range to its upper bound is documented."""
    content = read_research_consolidator()
    assert "upper bound" in content.lower(), \
        "Range-to-upper-bound resolution rule not documented"


def test_default_ceiling_value_documented():
    """Test that the default line-count ceiling value (400) is documented."""
    content = read_research_consolidator()
    assert "400" in content, \
        "Default line-count ceiling value (400) not documented"
    assert "default (no repo convention found)" in content, \
        "Default source label 'default (no repo convention found)' not documented"


def test_line_count_ceiling_report_section_documented():
    """Test that a top-level Line-Count Ceiling report section is documented."""
    content = read_research_consolidator()
    assert "### Line-Count Ceiling" in content, \
        "Top-level '### Line-Count Ceiling' report section not documented"


if __name__ == "__main__":
    tests = [
        test_line_count_field_in_file_summaries_schema,
        test_grep_count_mode_method_documented,
        test_no_read_line_numbering_guardrail_documented,
        test_agents_claude_md_lookup_step_documented,
        test_range_resolves_to_upper_bound_documented,
        test_default_ceiling_value_documented,
        test_line_count_ceiling_report_section_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
