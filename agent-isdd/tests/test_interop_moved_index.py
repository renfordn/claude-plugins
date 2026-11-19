"""Citations of agent-isdd INTEROP.md sections that moved to references/interop-*.md still resolve."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = open(os.path.join(ROOT, "INTEROP.md"), encoding="utf-8").read()
REFS = {n: open(os.path.join(ROOT, "references", n), encoding="utf-8").read()
        for n in ("interop-agent-tdd.md", "interop-reviewers.md")}
CITED = {
    "interop-agent-tdd.md": ["Fallback — Direct Implementation", "Test-Author Gate", "Code-Review Gate",
                             "Design Spec completeness gate", "Agent-tdd Design Spec workflow (pointer)",
                             "file_summaries", "Parallel handoff"],
    "interop-reviewers.md": ["← agent-tdd / code-reviewer (rollback request)", "→ code-reviewer (review gate)",
                             "Strategic Review Placement via Review Levels", "Review tracking"],
}


def test_moved_sections_indexed_and_present():
    assert "## Moved sections" in INDEX
    for ref, names in CITED.items():
        assert f"references/{ref}" in INDEX
        for name in names:
            assert name in INDEX, name
            assert name in REFS[ref], (ref, name)
