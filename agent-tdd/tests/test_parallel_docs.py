"""Slice 2H: parallel slice delivery is documented and always-loaded text did not grow."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# description lengths at base 9e68c0f, frozen so the test needs no git history
BASE_LENGTHS = {"agents/test-strategist.md": 1073, "skills/test-budget/SKILL.md": 708}
NEW_CMD_DESC_BUDGET = 110


def _desc(text):
    fm = text.split("---", 2)[1]
    lines = fm.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"description:\s*(.*)$", ln)
        if not m:
            continue
        val = m.group(1).strip()
        if val in (">", ">-", "|"):
            out = []
            for nxt in lines[i + 1:]:
                if nxt.startswith((" ", "\t")):
                    out.append(nxt.strip())
                else:
                    break
            return " ".join(out)
        return val
    raise AssertionError("no description")


def test_agent_tdd_documents_parallel_and_slice_id():
    text = (ROOT / "agents" / "agent-TDD.md").read_text()
    assert "Parallel:" in text
    assert "<!--SLICE-ID:" in text
    assert len(text.splitlines()) < 300


def test_schema_has_optional_parallel_fields():
    schema = json.loads((ROOT / "references" / "slice-spec.schema.json").read_text())
    props = schema["properties"]
    for f in ("sliceId", "ownedFiles", "baseCommit"):
        assert f in props and f not in schema["required"]
    assert props["ownedFiles"]["type"] == "array"


def test_interop_short_and_links_parallel_paths():
    text = (ROOT / "INTEROP.md").read_text()
    assert len(text.splitlines()) < 400
    assert "references/parallel-delivery.md" in text
    assert "commands/tdd-parallel.md" in text
    assert "sliceId" in text or "Slice id" in text


def test_tasks_format_documents_parallel():
    text = (ROOT / "references" / "tasks-format.md").read_text()
    assert "<!--SLICE-ID" in text and "validation" in text


def test_changelog_unreleased_mentions_parallel():
    text = (ROOT / "CHANGELOG.md").read_text()
    unreleased = text.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert "parallel slice delivery" in unreleased.lower()
    assert "tdd-parallel" in (ROOT / "README.md").read_text()


def test_descriptions_trimmed_enough_to_offset_new_command():
    rels = ("agents/test-strategist.md", "skills/test-budget/SKILL.md")
    saved = sum(BASE_LENGTHS[r] - len(_desc((ROOT / r).read_text())) for r in rels)
    assert saved >= NEW_CMD_DESC_BUDGET, saved
    s = _desc((ROOT / rels[0]).read_text())
    for p in ("do I need a test for this?", "why is the test suite so slow?", "we have too many tests"):
        assert p in s
    b = _desc((ROOT / rels[1]).read_text())
    for p in ("test bloat", "slow pipeline", "consolidating tests", "should this be an e2e test"):
        assert p in b
