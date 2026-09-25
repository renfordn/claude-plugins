"""
Test: the `claude plugin eval` suite under evals/ stays well-formed and its fixtures honest.

Running the suite itself needs the claude CLI and costs tokens, so CI only checks structure.
Single-file fixtures are inline in each prompt.md with line numbers: `context.add_dirs` didn't
mount anything in Claude Code 2.1.282, so the child never saw a separate fixture file.
Multi-file PR cases use case.yaml + scaffold.sh instead (run with `--scaffold`).
"""

import os
import re
import subprocess
from pathlib import Path

_EVALS = Path(__file__).resolve().parent.parent / "evals"
_CASES = sorted(p for p in _EVALS.iterdir() if p.is_dir() and p.name != "results")
_SCAFFOLD_CASES = [c for c in _CASES if (c / "case.yaml").exists()]
_INLINE_CASES = [c for c in _CASES if c not in _SCAFFOLD_CASES]


def _numbered_fixture(case: Path) -> dict:
    block = re.search(r"```python\n(.*?)```", (case / "prompt.md").read_text(), re.S)
    assert block, f"{case.name} prompt has no inline fixture"
    return {int(m.group(1)): m.group(2) for m in re.finditer(r"^\s*(\d+)  (.*)$", block.group(1), re.M)}


def test_suite_has_planted_bug_and_clean_cases():
    names = {c.name for c in _CASES}
    assert "clean-no-false-positive" in names
    assert len(names) >= 4


def test_each_case_is_complete():
    for case in _INLINE_CASES:
        assert _numbered_fixture(case), case.name
        assert any((case / "graders").glob("*.md")), f"{case.name} has no graders"


def test_scaffolded_cases_are_complete():
    """case.yaml cases build a real git repo (a PR branch against main) with scaffold.sh."""
    assert _SCAFFOLD_CASES, "expected at least one scaffolded multi-file case"
    for case in _SCAFFOLD_CASES:
        spec = (case / "case.yaml").read_text()
        assert re.search(r"^\s+scaffold_script:\s*scaffold\.sh$", spec, re.M), case.name
        assert (case / "scaffold.sh").is_file(), case.name
        assert re.search(r"^\s+- name: \S+", spec, re.M), f"{case.name} has no graders"


def test_scaffolds_build_a_pr_branch(tmp_path):
    for case in _SCAFFOLD_CASES:
        work = tmp_path / case.name
        work.mkdir()
        env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["bash", str(case / "scaffold.sh")], cwd=work, env=env, check=True)
        assert (work / "PR.diff").read_text().startswith("diff --git"), case.name
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=work, env=env,
                                capture_output=True, text=True).stdout.strip()
        assert branch == "feature", case.name


def test_cited_line_holds_code():
    for case in _INLINE_CASES:
        grader = case / "graders" / "cites-line.md"
        if not grader.exists():
            continue
        line = int(re.search(r"pattern: '[\w\\.]+:(\d+)", grader.read_text()).group(1))
        assert _numbered_fixture(case).get(line, "").strip(), f"{case.name} cites a missing/blank line"
