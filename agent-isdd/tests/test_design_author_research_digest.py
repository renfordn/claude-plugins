"""Slice 13 (R10): design-author looks up agent-nelly research digests before research and
sends one digest per topic after it; agent-isdd INTEROP documents the digest request schema."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "design-author" / "SKILL.md").read_text(encoding="utf-8")
INTEROP = (ROOT / "INTEROP.md").read_text(encoding="utf-8")


def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


REFS = ROOT / "skills" / "design-author" / "references"


def _ref(name):
    return (REFS / name).read_text(encoding="utf-8")


# Moved situational text lives in references/; each needle is asserted in the file it lives in.
STEP1 = _between(SKILL, "1. `agent-nelly:agent-nelly`", "2. **[Phase 2+3]** `research-consolidator`")
STEP2 = _between(SKILL, "2. **[Phase 2+3]** `research-consolidator`", "3. **Independent verification**")
LOOKUP = _ref("nelly-cache-lookup.md")
PERSIST = _ref("nelly-persistence.md")


def test_step1_looks_up_digests_and_uses_fresh_and_stale_results():
    assert "references/nelly-cache-lookup.md" in STEP1 and "`research digest lookup`" in STEP1
    assert "**[Research Digest Cache]**" in LOOKUP
    assert "`research digest lookup`" in LOOKUP
    assert "`fresh`" in LOOKUP and "`stale`" in LOOKUP
    assert "`changed`" in LOOKUP


def test_step2_sends_one_digest_per_topic_and_splits_over_30_files():
    assert "references/nelly-persistence.md" in STEP2 and "`research digest`" in STEP2
    assert "`research digest`" in PERSIST
    assert "30" in PERSIST
    assert "top-level directory" in PERSIST


def test_interop_documents_digest_request_schema():
    sec = _between(INTEROP, "## → agent-nelly (memory)", "\n## → ")
    assert "Research Digest Cache" in sec
    for key in ('"topic"', '"summary"', '"paths"'):
        assert key in sec, key
    assert "`research digest lookup`" in sec


def test_changelog_documents_research_digest():
    # Documented once, permanently -- under [Unreleased] before a release dates it under the
    # plugin.json version current at ship time, and under that version's own section forever
    # after (not necessarily the *current* plugin.json version, which moves on with later,
    # unrelated releases).
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "research digest" in changelog.lower()
