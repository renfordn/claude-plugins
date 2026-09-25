"""
Test: code an agent wrote is reviewed by a different context, never by its author.

Pins the three-path independent review (spawned agent → headless script → labelled
self-review) and that agent-TDD requests reviews instead of running them itself.
"""

import os
import re
import subprocess
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent
_REPO = _PLUGIN.parent
_AGENT = _PLUGIN / "agents" / "code-reviewer.md"
_VERIFIER = _PLUGIN / "agents" / "finding-verifier.md"
_CROSS = _PLUGIN / "agents" / "cross-file-reviewer.md"
_SCRIPT = _PLUGIN / "scripts" / "review_headless.sh"
_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _frontmatter_tools(path: Path) -> set:
    match = re.search(r"^tools:\s*(.+)$", path.read_text(), re.M)
    assert match, f"{path.name} has no tools: line"
    return {t.strip() for t in match.group(1).split(",")}


def test_reviewer_and_verifier_agents_are_read_only():
    for agent in (_AGENT, _VERIFIER, _CROSS):
        tools = _frontmatter_tools(agent)
        assert not tools & _EDIT_TOOLS, f"{agent.name} can edit files: {tools & _EDIT_TOOLS}"
        assert "Agent" not in tools


def test_verifier_returns_marker_and_all_three_outcomes():
    text = _VERIFIER.read_text()
    assert "<!--FINDING-VERIFIER-REPORT-->" in text
    for outcome in ("upheld", "refuted", "downgraded"):
        assert f"`{outcome}`" in text


def test_interop_verify_pass_rules():
    text = (_PLUGIN / "INTEROP.md").read_text()
    section = re.search(r"### Verify pass.*?(?=\n## |\Z)", text, re.S).group(0)
    assert "code-reviewer:finding-verifier" in section
    assert "--agent finding-verifier" in section
    assert "No self-verification" in section
    assert "leave `verdict`" in section


def test_skill_only_sets_verdict_after_verify_pass():
    skill = (_PLUGIN / "skills" / "code-reviewer" / "SKILL.md").read_text()
    row = next(line for line in skill.splitlines() if line.startswith("| `verdict`"))
    assert "verify pass" in row and "Omit" in row


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


def test_headless_script_rejects_path_like_agent_names():
    result = subprocess.run([str(_SCRIPT), "--agent", "../README", "x"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "bad agent name" in result.stderr


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
