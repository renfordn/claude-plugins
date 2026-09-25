"""design-author/SKILL.md must name agent-nelly's persisted summary type as `file-summary`
(hyphen) -- the underscore spelling is what left the summary cache without hits (R9)."""
from pathlib import Path

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "design-author" / "SKILL.md"


def test_skill_does_not_name_underscore_file_summary_type():
    content = _SKILL_PATH.read_text()
    assert 'type: "file_summary"' not in content


def test_skill_outputs_name_hyphenated_file_summary_type():
    content = _SKILL_PATH.read_text()
    assert 'file_summaries ready for agent-nelly persistence (type: "file-summary")' in content
