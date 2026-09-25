"""
Test: explaining code lives in its own `code-brief` skill, not as a mode of code-reviewer.
"""

from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent
_BRIEF_PATH = _PLUGIN / "skills" / "code-brief" / "SKILL.md"
_REVIEW_SKILL_PATH = _PLUGIN / "skills" / "code-reviewer" / "SKILL.md"
_INTEROP_PATH = _PLUGIN / "INTEROP.md"


def test_code_brief_skill_is_user_invocable_with_arguments():
    content = _BRIEF_PATH.read_text()
    assert "name: code-brief" in content
    assert "argument-hint:" in content
    assert "$ARGUMENTS" in content


def test_code_brief_has_no_decision_model_fields():
    guardrails = _BRIEF_PATH.read_text().split("## Guardrails", 1)[1]
    assert "ReportFindings" in guardrails
    for field in ("decision", "severity", "category", "workflow_action", "confidence"):
        assert f"`{field}`" in guardrails, f"code-brief guardrails should rule out {field}"


def test_code_brief_skips_review_state_files():
    content = _BRIEF_PATH.read_text()
    for artifact in ("REVIEW-STATE.md", "REVIEW-HISTORY.md", "TODO-LEDGER.md"):
        assert artifact in content, f"code-brief should state nothing is written to {artifact}"


def test_code_brief_still_uses_evidence_tiers():
    content = _BRIEF_PATH.read_text()
    for tier in ("tier-1", "tier-2", "tier-3", "tier-4", "tier-5"):
        assert tier in content
    assert "Unverified areas" in content


def test_code_brief_has_design_bar():
    assert "frontend-design" in _BRIEF_PATH.read_text()


def test_review_skill_no_longer_carries_research_brief():
    content = _REVIEW_SKILL_PATH.read_text()
    assert "research-brief" not in content
    assert "## Research Brief Output" not in content
    assert "code-brief" in content, "code-reviewer should point explainer requests at code-brief"


def test_no_command_shadows_the_skill():
    assert not (_PLUGIN / "commands" / "code-brief.md").exists()


def test_interop_documents_code_brief_contract():
    content = _INTEROP_PATH.read_text()
    assert "research-brief" not in content
    assert "## Explaining code: the `code-brief` skill" in content
