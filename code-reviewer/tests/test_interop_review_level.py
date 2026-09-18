"""
Test: INTEROP.md documents review_level parameter correctly.

Red Test — verify that review_level contract is documented in INTEROP.md.
"""


def read_interop_md():
    """Read the current INTEROP.md file."""
    with open("/Users/jay.nelson/Codebase/Claude-Plugins/code-reviewer/INTEROP.md", "r") as f:
        return f.read()


def test_review_level_parameter_in_contract():
    """Test that review_level parameter is documented in invocation contract."""
    content = read_interop_md()
    assert "review_level" in content, "review_level parameter not documented in INTEROP.md contract"


def test_capability_detection_substring_preserved():
    """Test that capability-detection substring is preserved."""
    content = read_interop_md()
    # Must have at least one of these substrings for plugin-orchestrator detection
    has_substring = ("Integrating Code Reviewer" in content) or ("code-reviewer INTEROP" in content)
    assert has_substring, "Capability-detection substring ('Integrating Code Reviewer' or 'code-reviewer INTEROP') not found in INTEROP.md"


def test_evidence_tier_orthogonality_documented():
    """Test that Evidence Tier orthogonality is documented."""
    content = read_interop_md()
    # Should document that review_level and Evidence Tier are independent
    assert "orthogonal" in content.lower() or "independent" in content.lower(), \
        "Evidence Tier orthogonality not clearly documented"


def test_review_level_parameter_section_exists():
    """Test that invocation contract section mentions review_level clearly."""
    content = read_interop_md()
    # Should have dedicated section or mention in invocation instructions
    assert "Invocation" in content and "review_level" in content, \
        "review_level not mentioned in invocation instructions"


def test_graceful_degradation_documented():
    """Test that graceful degradation is documented."""
    content = read_interop_md()
    assert "degrad" in content.lower() or "unavailable" in content, \
        "Graceful degradation not documented"


if __name__ == "__main__":
    tests = [
        test_review_level_parameter_in_contract,
        test_capability_detection_substring_preserved,
        test_evidence_tier_orthogonality_documented,
        test_review_level_parameter_section_exists,
        test_graceful_degradation_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
