"""
Test: design-author documents a Design Gate item for the line-count-ceiling
split/extraction recommendation.

Red Test — verify the new line-count-gate instructions are documented in
design-author/SKILL.md before the corresponding implementation exists.
"""

from pathlib import Path

_SKILL_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "design-author"
    / "SKILL.md"
)


def read_design_author_skill():
    """Read the current design-author/SKILL.md file."""
    return _SKILL_PATH.read_text()


def test_refactor_reduction_bullet_instructions_documented():
    """Test that instructions exist for turning research-consolidator's line_count/
    Line-Count Ceiling fields into a Refactor & Reduction Opportunities bullet."""
    content = read_design_author_skill()
    assert "Line-Count Ceiling" in content, \
        "Line-Count Ceiling field not referenced in design-author/SKILL.md"
    assert "Refactor & Reduction Opportunities" in content, \
        "Refactor & Reduction Opportunities section not referenced in design-author/SKILL.md"


def test_design_gate_checklist_item_documented():
    """Test that the Design Gate checklist documents a line-count-ceiling item."""
    content = read_design_author_skill()
    gate_start = content.index("## Design Gate")
    diagrams_start = content.index("## Diagrams")
    gate_section = content[gate_start:diagrams_start]

    assert "line-count" in gate_section.lower() or "line count" in gate_section.lower(), \
        "Design Gate checklist does not document a line-count-ceiling item"
    assert "ceiling" in gate_section.lower(), \
        "Design Gate checklist does not mention the line-count ceiling"


def test_file_summaries_field_list_includes_line_count():
    """Test that the Research First step's file_summaries field-list enumeration includes
    line_count, matching research-consolidator.md's schema and INTEROP.md's JSON example."""
    content = read_design_author_skill()
    marker = "`file_summaries` are structured for cross-feature reuse"
    field_list_start = content.index(marker)
    window = content[field_list_start:field_list_start + 200]

    assert "line_count" in window, \
        "file_summaries field-list enumeration is missing line_count (schema drift vs. " \
        "research-consolidator.md and INTEROP.md)"


def test_code_reviewer_exclusion_guardrail_documented():
    """Test that a guardrail states code-reviewer's Deep review stays out of
    line-count-ceiling territory."""
    content = read_design_author_skill()
    guardrails_start = content.index("## Guardrails")
    guardrails_section = content[guardrails_start:]

    assert "line count" in guardrails_section.lower() or "line-count" in guardrails_section.lower(), \
        "Guardrails section does not document the code-reviewer line-count-ceiling exclusion"
    assert "code-reviewer" in guardrails_section.lower() or "`/code-reviewer`" in guardrails_section, \
        "Guardrails section does not reference code-reviewer in the line-count exclusion note"


if __name__ == "__main__":
    tests = [
        test_refactor_reduction_bullet_instructions_documented,
        test_design_gate_checklist_item_documented,
        test_code_reviewer_exclusion_guardrail_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
