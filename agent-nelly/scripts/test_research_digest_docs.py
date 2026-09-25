"""Slice 12: agent-nelly documents the `research digest` / `research digest lookup` request
fields (agent spec + consumer-facing INTEROP)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = (ROOT / "agents" / "agent-nelly.md").read_text(encoding="utf-8")
INTEROP = (ROOT / "INTEROP.md").read_text(encoding="utf-8")


def _section(text, heading, next_prefix):
    start = text.index(heading)
    end = text.find(next_prefix, start + len(heading))
    return text[start:end if end != -1 else None]


def test_agent_spec_has_research_digest_section_after_summary_cache():
    assert AGENT.index("### File & Folder Summary Cache") < AGENT.index("### Research Digest Cache")


def test_agent_spec_section_documents_fields_commands_limits_and_status():
    sec = _section(AGENT, "### Research Digest Cache", "\n### ")
    for needle in ("`research digest`", "`research digest lookup`",
                   "scripts/research_digest.py\" write", "scripts/research_digest.py\" lookup",
                   "2,000", "30", "`fresh`", "`stale`", "`changed`", "exit code 2"):
        assert needle in sec, needle


def test_interop_has_consumer_section_with_fields_and_output_keys():
    sec = _section(INTEROP, "## Research Digest Cache", "\n## ")
    for needle in ("`research digest`", "`research digest lookup`", "`topic`", "`summary`",
                   "`paths`", "`status`", "`changed`", "`source`"):
        assert needle in sec, needle


def test_changelog_documents_research_digest():
    # The entry lives under [Unreleased] until a release dates it under the plugin.json version.
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    unreleased = _section(changelog, "## [Unreleased]", "\n## [")
    released = _section(changelog, f"## [{version}]", "\n## [") if f"## [{version}]" in changelog else ""
    assert "research digest" in (unreleased + released).lower()
