"""
Test: agent-tdd SKILL.md documents Review-Level Strategy.

Red Test — verify that Review-Level Strategy section is comprehensive.
"""


def read_agent_tdd_skill():
    """Read the agent-tdd SKILL.md file."""
    with open("/Users/jay.nelson/Codebase/Claude-Plugins/agent-tdd/SKILL.md", "r") as f:
        return f.read()


def test_review_level_strategy_section_exists():
    """Test that Review-Level Strategy section exists."""
    content = read_agent_tdd_skill()
    assert "Review-Level Strategy" in content, \
        "Review-Level Strategy section not found in agent-tdd SKILL.md"


def test_all_four_checkpoints_documented():
    """Test that all 4 review checkpoints are documented."""
    content = read_agent_tdd_skill()
    checkpoints = ["Red", "Green", "Refactor", "Coherence"]
    for checkpoint in checkpoints:
        assert checkpoint in content, f"Checkpoint '{checkpoint}' not documented"


def test_quick_standard_deep_levels_documented():
    """Test that Quick, Standard, Deep levels are documented."""
    content = read_agent_tdd_skill()
    levels = ["Quick", "Standard", "Deep", "Ultra"]
    for level in levels:
        assert level in content, f"Review level '{level}' not documented"


def test_auto_detection_logic_documented():
    """Test that auto-detection logic is documented."""
    content = read_agent_tdd_skill()
    assert "Auto-Detection Logic" in content or "auto-detect" in content.lower(), \
        "Auto-Detection Logic section not found"


def test_finding_flow_documented():
    """Test that finding flow to ralph loops is documented."""
    content = read_agent_tdd_skill()
    assert "ralph loop" in content.lower() or "Ralph Loops" in content, \
        "Finding flow to ralph loops not documented"


def test_high_risk_deep_mapping_clear():
    """Test that high-risk → Deep mapping is clear."""
    content = read_agent_tdd_skill()
    assert ("high_risk" in content and "Deep" in content) or \
           ("high-risk" in content and "Deep" in content), \
        "High-risk to Deep mapping not clear"


def test_coherence_review_ultra_condition_documented():
    """Test that coherence review Ultra condition (>50% high-risk) is documented."""
    content = read_agent_tdd_skill()
    assert "50%" in content or "0.5" in content or "majority" in content.lower(), \
        "Coherence review high-risk percentage threshold not documented"


if __name__ == "__main__":
    tests = [
        test_review_level_strategy_section_exists,
        test_all_four_checkpoints_documented,
        test_quick_standard_deep_levels_documented,
        test_auto_detection_logic_documented,
        test_finding_flow_documented,
        test_high_risk_deep_mapping_clear,
        test_coherence_review_ultra_condition_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
