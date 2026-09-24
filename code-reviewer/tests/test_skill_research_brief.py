"""
Test: SKILL.md and INTEROP.md document the `research-brief` invocation mode correctly.
"""

from pathlib import Path

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "code-reviewer" / "SKILL.md"
_INTEROP_PATH = Path(__file__).resolve().parent.parent / "INTEROP.md"


def read_skill_md():
    return _SKILL_PATH.read_text()


def read_interop_md():
    return _INTEROP_PATH.read_text()


def test_research_brief_mode_documented_as_invocation_mode():
    content = read_skill_md()
    assert "### `research-brief`" in content, \
        "research-brief not documented as an Invocation Mode"


def test_research_brief_output_section_exists():
    content = read_skill_md()
    assert "## Research Brief Output" in content, \
        "Research Brief Output section missing from SKILL.md"


def test_research_brief_has_no_decision_model_fields():
    content = read_skill_md()
    start = content.index("## Research Brief Output")
    end = content.index("## Combined Findings And Anti-Blur Rules")
    section = content[start:end]

    for field in ["`decision`", "`severity`", "`workflow_action`", "`confidence`"]:
        assert field in section, \
            f"Research Brief Output section should explicitly state {field} does not apply"


def test_research_brief_skips_review_state_files():
    content = read_skill_md()
    start = content.index("## Research Brief Output")
    end = content.index("## Combined Findings And Anti-Blur Rules")
    section = content[start:end]

    for artifact in ["REVIEW-STATE.md", "REVIEW-HISTORY.md", "TODO-LEDGER.md"]:
        assert artifact in section, \
            f"Research Brief Output section should state nothing is written to {artifact}"


def test_research_brief_still_uses_evidence_tiers():
    content = read_skill_md()
    start = content.index("## Research Brief Output")
    end = content.index("## Combined Findings And Anti-Blur Rules")
    section = content[start:end]

    assert "tier-1" in section or "tier-" in section, \
        "Research Brief Output should still ground claims in the Evidence Tier Model"


def test_research_brief_guardrails_present():
    content = read_skill_md()
    guardrails = content[content.index("## Guardrails"):]
    assert "research-brief" in guardrails, \
        "Guardrails section should cover research-brief-specific rules"


def test_interop_mode_field_includes_research_brief():
    content = read_interop_md()
    assert "research-brief" in content, \
        "INTEROP.md's Mode field should list research-brief as a valid mode"


def test_interop_research_brief_contract_documented():
    content = read_interop_md()
    assert "research-brief` mode: a different contract" in content, \
        "INTEROP.md should explain research-brief's different (no-findings) return contract"


if __name__ == "__main__":
    tests = [
        test_research_brief_mode_documented_as_invocation_mode,
        test_research_brief_output_section_exists,
        test_research_brief_has_no_decision_model_fields,
        test_research_brief_skips_review_state_files,
        test_research_brief_still_uses_evidence_tiers,
        test_research_brief_guardrails_present,
        test_interop_mode_field_includes_research_brief,
        test_interop_research_brief_contract_documented,
    ]

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
