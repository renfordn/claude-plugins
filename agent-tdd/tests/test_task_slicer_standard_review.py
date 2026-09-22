"""
Test: task-slicer SKILL.md documents Standard review on tasks.md.

Red Test — verify that Standard review invocation is documented.
"""

from pathlib import Path

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "task-slicer" / "SKILL.md"


def read_task_slicer_skill():
    """Read the task-slicer SKILL.md file."""
    return _SKILL_PATH.read_text()


def test_standard_review_documented():
    """Test that Standard review is documented."""
    content = read_task_slicer_skill()
    assert "Standard" in content and "review" in content.lower(), \
        "Standard review not documented in task-slicer SKILL.md"


def test_code_reviewer_invocation_documented():
    """Test that /code-reviewer invocation is documented."""
    content = read_task_slicer_skill()
    assert "code-reviewer" in content.lower() or "/code-reviewer" in content, \
        "/code-reviewer invocation not documented"


def test_focus_areas_documented():
    """Test that focus areas for Standard review are documented."""
    content = read_task_slicer_skill()
    focus_areas = ["clarity", "depend", "sequenc", "validation"]
    found = sum(1 for area in focus_areas if area in content.lower())
    assert found >= 3, f"Expected ≥3 focus areas documented, found {found}"


def test_gate_logic_documented():
    """Test that gate logic is documented."""
    content = read_task_slicer_skill()
    assert ("gate" in content.lower() or "block" in content.lower() or "proceed" in content), \
        "Gate logic not documented"


def test_tasks_md_scope_documented():
    """Test that tasks.md is mentioned as the scope."""
    content = read_task_slicer_skill()
    assert "tasks.md" in content, "tasks.md scope not documented"


if __name__ == "__main__":
    tests = [
        test_standard_review_documented,
        test_code_reviewer_invocation_documented,
        test_focus_areas_documented,
        test_gate_logic_documented,
        test_tasks_md_scope_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
