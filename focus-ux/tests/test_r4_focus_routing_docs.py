"""Release 4 docs: focus-ux routes text 'how code works' questions to feature-finder."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENTENCE = "text answers to \"where is / what calls / how does X work\" go to `code-reviewer:feature-finder`"


def test_interop_routes_text_answers_to_feature_finder():
    assert SENTENCE in (ROOT / "INTEROP.md").read_text()


def test_readme_routes_text_answers_to_feature_finder():
    assert SENTENCE in (ROOT / "README.md").read_text()


def test_code_brief_description_routes_text_questions_to_feature_finder():
    skill = ROOT.parent / "code-reviewer" / "skills" / "code-brief" / "SKILL.md"
    if not skill.exists():
        return
    desc = [l for l in skill.read_text().splitlines() if l.startswith("description:")][0]
    assert "feature-finder" in desc
