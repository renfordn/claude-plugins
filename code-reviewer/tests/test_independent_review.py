"""
Test: code an agent wrote is reviewed by a different context, never by its author.

Pins the three-path independent review (spawned agent → headless script → labelled
self-review) and that agent-TDD requests reviews instead of running them itself.
"""

import os
import re
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent
_REPO = _PLUGIN.parent
_AGENT = _PLUGIN / "agents" / "code-reviewer.md"
_SCRIPT = _PLUGIN / "scripts" / "review_headless.sh"
_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _frontmatter_tools(path: Path) -> set:
    match = re.search(r"^tools:\s*(.+)$", path.read_text(), re.M)
    assert match, f"{path.name} has no tools: line"
    return {t.strip() for t in match.group(1).split(",")}


def test_reviewer_agent_is_read_only():
    tools = _frontmatter_tools(_AGENT)
    assert not tools & _EDIT_TOOLS, f"reviewer agent can edit files: {tools & _EDIT_TOOLS}"
    assert "Agent" not in tools


def test_reviewer_agent_returns_marker_and_payload():
    text = _AGENT.read_text()
    assert "<!--CODE-REVIEWER-REPORT-->" in text
    assert "skills/code-reviewer/SKILL.md" in text


def test_headless_script_is_executable_and_read_only():
    assert os.access(_SCRIPT, os.X_OK)
    text = _SCRIPT.read_text()
    assert "claude -p" in text
    disallowed = re.search(r"--disallowedTools\s+(.+)", text).group(1).split()
    assert _EDIT_TOOLS <= set(disallowed)


def test_interop_documents_all_three_paths_in_order():
    text = (_PLUGIN / "INTEROP.md").read_text()
    section = re.search(r"## Independent review.*?(?=\n## |\Z)", text, re.S).group(0)
    spawn = section.index("code-reviewer:code-reviewer")
    headless = section.index("review_headless.sh")
    self_review = section.index("self-reviewed")
    assert spawn < headless < self_review


def test_agent_tdd_never_invokes_reviewer_itself():
    text = (_REPO / "agent-tdd" / "agents" / "agent-TDD.md").read_text()
    assert not re.search(r"[Ii]nvoke `?/code-reviewer", text)
    assert not re.search(r"^/code-reviewer ", text, re.M)
    assert "Review Request" in text
