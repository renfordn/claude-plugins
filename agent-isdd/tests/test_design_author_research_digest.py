"""Slice 13 (R10): design-author looks up agent-nelly research digests before research and
sends one digest per topic after it; agent-isdd INTEROP documents the digest request schema."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "design-author" / "SKILL.md").read_text(encoding="utf-8")
INTEROP = (ROOT / "INTEROP.md").read_text(encoding="utf-8")


def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


STEP1 = _between(SKILL, "1. `agent-nelly:agent-nelly`", "2. **[Phase 2+3]** `research-consolidator`")
STEP2 = _between(SKILL, "2. **[Phase 2+3]** `research-consolidator`", "3. **Independent verification**")


def test_step1_looks_up_digests_and_uses_fresh_and_stale_results():
    assert "**[Research Digest Cache]**" in STEP1
    assert "`research digest lookup`" in STEP1
    assert "`fresh`" in STEP1 and "`stale`" in STEP1
    assert "`changed`" in STEP1


def test_step2_sends_one_digest_per_topic_and_splits_over_30_files():
    assert "`research digest`" in STEP2
    assert "30" in STEP2
    assert "top-level directory" in STEP2


def test_interop_documents_digest_request_schema():
    sec = _between(INTEROP, "## → agent-nelly (memory)", "\n## → ")
    assert "Research Digest Cache" in sec
    for key in ('"topic"', '"summary"', '"paths"'):
        assert key in sec, key
    assert "`research digest lookup`" in sec


def test_changelog_unreleased_mentions_research_digest():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = _between(changelog, "## [Unreleased]", "\n## [")
    assert "research digest" in unreleased.lower()
