"""
Test: findings_validator.py supports review_level field and Evidence Tier validation.

Red Test — verify review_level support and tier validation per level.
"""

import sys
sys.path.insert(0, "/Users/jay.nelson/Codebase/Claude-Plugins/shared")

from findings_validator import validate_finding, validate_findings, validate_report_input


def test_review_level_field_accepted():
    """Test that review_level field is accepted in findings."""
    finding = {
        "summary": "Test finding",
        "evidence_tier": 2,
        "review_level": "Standard"
    }
    result = validate_finding(finding)
    assert result.get("review_level") == "Standard", "review_level field not preserved"


def test_all_review_levels_accepted():
    """Test that all review levels are accepted."""
    levels = ["Quick", "Standard", "Deep", "Ultra"]
    for level in levels:
        finding = {
            "summary": "Test",
            "evidence_tier": 2,
            "review_level": level
        }
        result = validate_finding(finding)
        assert result.get("review_level") == level, f"review_level '{level}' not preserved"


def test_evidence_tier_validation_quick_level():
    """Test that Quick level allows tier-1..2 findings."""
    # Quick level should accept tier-1 and tier-2
    for tier in [1, 2]:
        finding = {
            "summary": "Test",
            "evidence_tier": tier,
            "review_level": "Quick"
        }
        result = validate_finding(finding)
        assert result["evidence_tier"] == tier, f"Quick level should accept tier-{tier}"


def test_evidence_tier_validation_standard_level():
    """Test that Standard level allows tier-2..3 findings."""
    # Standard level should accept tier-2 and tier-3
    for tier in [2, 3]:
        finding = {
            "summary": "Test",
            "evidence_tier": tier,
            "review_level": "Standard"
        }
        result = validate_finding(finding)
        assert result["evidence_tier"] == tier, f"Standard level should accept tier-{tier}"


def test_evidence_tier_validation_deep_level():
    """Test that Deep level allows tier-3..4 findings."""
    # Deep level should accept tier-3 and tier-4
    for tier in [3, 4]:
        finding = {
            "summary": "Test",
            "evidence_tier": tier,
            "review_level": "Deep"
        }
        result = validate_finding(finding)
        assert result["evidence_tier"] == tier, f"Deep level should accept tier-{tier}"


def test_evidence_tier_validation_ultra_level():
    """Test that Ultra level allows tier-3..5 findings."""
    # Ultra level should accept tier-3, tier-4, and tier-5
    for tier in [3, 4, 5]:
        finding = {
            "summary": "Test",
            "evidence_tier": tier,
            "review_level": "Ultra"
        }
        result = validate_finding(finding)
        assert result["evidence_tier"] == tier, f"Ultra level should accept tier-{tier}"


def test_backward_compatibility_no_review_level():
    """Test that findings without review_level default to Standard tier rules."""
    # Finding without review_level should be treated as Standard (tier-2..3)
    finding = {
        "summary": "Test finding without review level",
        "evidence_tier": 2
    }
    result = validate_finding(finding)
    # Should still validate and not error
    assert result["evidence_tier"] == 2
    assert "review_level" not in result  # Should not add one if not present


def test_validate_findings_with_mixed_review_levels():
    """Test that validate_findings handles multiple findings with different review_levels."""
    findings = [
        {"summary": "Quick review", "evidence_tier": 1, "review_level": "Quick"},
        {"summary": "Standard review", "evidence_tier": 2, "review_level": "Standard"},
        {"summary": "Deep review", "evidence_tier": 3, "review_level": "Deep"},
        {"summary": "Ultra review", "evidence_tier": 5, "review_level": "Ultra"},
    ]
    results = validate_findings(findings)
    assert len(results) == 4
    assert results[0]["review_level"] == "Quick"
    assert results[1]["review_level"] == "Standard"
    assert results[2]["review_level"] == "Deep"
    assert results[3]["review_level"] == "Ultra"


if __name__ == "__main__":
    tests = [
        test_review_level_field_accepted,
        test_all_review_levels_accepted,
        test_evidence_tier_validation_quick_level,
        test_evidence_tier_validation_standard_level,
        test_evidence_tier_validation_deep_level,
        test_evidence_tier_validation_ultra_level,
        test_backward_compatibility_no_review_level,
        test_validate_findings_with_mixed_review_levels,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
        except Exception as e:
            print(f"✗ {test.__name__}: {type(e).__name__}: {e}")
