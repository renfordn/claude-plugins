"""
Test: the `claude plugin eval` suite under evals/ stays well-formed and its fixtures honest.

Running the suite itself needs the claude CLI and costs tokens, so CI only checks structure.
Fixtures are inline in each prompt.md with line numbers: `context.add_dirs` didn't mount
anything in Claude Code 2.1.282, so the child never saw a separate fixture file.
"""

import re
from pathlib import Path

_EVALS = Path(__file__).resolve().parent.parent / "evals"
_CASES = sorted(p for p in _EVALS.iterdir() if p.is_dir() and p.name != "results")


def _numbered_fixture(case: Path) -> dict:
    block = re.search(r"```python\n(.*?)```", (case / "prompt.md").read_text(), re.S)
    assert block, f"{case.name} prompt has no inline fixture"
    return {int(m.group(1)): m.group(2) for m in re.finditer(r"^\s*(\d+)  (.*)$", block.group(1), re.M)}


def test_suite_has_planted_bug_and_clean_cases():
    names = {c.name for c in _CASES}
    assert "clean-no-false-positive" in names
    assert len(names) >= 4


def test_each_case_is_complete():
    for case in _CASES:
        assert _numbered_fixture(case), case.name
        assert any((case / "graders").glob("*.md")), f"{case.name} has no graders"


def test_cited_line_holds_code():
    for case in _CASES:
        grader = case / "graders" / "cites-line.md"
        if not grader.exists():
            continue
        line = int(re.search(r"pattern: '[\w\\.]+:(\d+)", grader.read_text()).group(1))
        assert _numbered_fixture(case).get(line, "").strip(), f"{case.name} cites a missing/blank line"
