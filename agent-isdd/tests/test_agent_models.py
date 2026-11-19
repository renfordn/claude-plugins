"""Slice 10: agent frontmatter declares explicit model and effort (R0b)."""
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parent.parent / "agents"

# name -> (allowed models, effort)
EXPECTED = {
    "research-consolidator": ({"opus"}, "high"),
    "spec-reviewer": ({"opus"}, "high"),
    "plan-reviewer-tier1": ({"opus", "sonnet"}, "medium"),  # sonnet flip: slice 33
    "plan-reviewer-tier2": ({"opus"}, "high"),
    "plan-reviewer-tier3": ({"opus"}, "xhigh"),
}


def _frontmatter(name):
    text = (AGENTS / f"{name}.md").read_text()
    assert text.startswith("---\n")
    block = text.split("\n---\n", 1)[0]
    fm = {}
    for line in block.splitlines()[1:]:
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, block


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_model_and_effort(name):
    models, effort = EXPECTED[name]
    fm, block = _frontmatter(name)
    assert fm.get("model") in models
    assert fm.get("effort") == effort
    assert "Use this agent when" in block
