"""Test utility functions in findings_validator.py"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from findings_validator import get_tier_expectations, validate_report_input


def test_get_tier_expectations():
    """Test that tier expectations are documented per level."""
    expectations = {
        "Quick": {"min": 1, "max": 2},
        "Standard": {"min": 2, "max": 3},
        "Deep": {"min": 3, "max": 4},
        "Ultra": {"min": 3, "max": 5},
    }

    for level, expected in expectations.items():
        result = get_tier_expectations(level)
        assert result == expected, f"Tier expectations for {level} mismatch: {result} != {expected}"


def test_validate_report_input_with_review_level():
    """Test that validate_report_input accepts review_level parameter."""
    findings = [{"summary": "Test"}]
    result = validate_report_input(findings, review_level="Deep")
    assert result["review_level"] == "Deep"
    assert len(result["findings"]) == 1


def test_validate_report_input_invalid_review_level():
    """Test that invalid review_level raises error."""
    findings = [{"summary": "Test"}]
    try:
        validate_report_input(findings, review_level="Invalid")
        assert False, "Should have raised ValueError for invalid review_level"
    except ValueError as e:
        assert "Invalid review_level" in str(e)


if __name__ == "__main__":
    tests = [
        test_get_tier_expectations,
        test_validate_report_input_with_review_level,
        test_validate_report_input_invalid_review_level,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
        except Exception as e:
            print(f"✗ {test.__name__}: {type(e).__name__}: {e}")
