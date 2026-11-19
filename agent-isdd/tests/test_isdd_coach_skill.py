"""isdd-coach skill: coaches user-led Implementation Mode."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "isdd-coach" / "SKILL.md"


def _text():
    assert SKILL.exists(), "skills/isdd-coach/SKILL.md missing"
    return SKILL.read_text()


def _fm():
    return _text().split("---", 2)[1]


def _desc():
    m = re.search(r"^description:\s*(.+)$", _fm(), re.M)
    assert m
    return m.group(1).strip().strip('"')


def test_frontmatter():
    fm = _fm()
    assert re.search(r"^name:\s*isdd-coach\s*$", fm, re.M)
    assert re.search(r"^user-invocable:\s*false\s*$", fm, re.M)
    d = _desc()
    assert "Invoked by /isdd" in d
    assert len(d) <= 50


def test_line_budget():
    assert len(_text().splitlines()) <= 130


def test_slice_spec_fields_named():
    t = _text()
    for f in ("taskDescription", "acceptanceCriteria", "riskTier", "dataContractsAndInterfaces"):
        assert f in t, f


def test_never_writes_production_code_and_tests_on_request():
    t = _text()
    assert "never writes production code" in t.lower() or "never write production code" in t.lower()
    assert "user_led_guard" in t
    assert re.search(r"tests?\b.{0,40}(only )?(when|if) the user asks", t, re.I | re.S)


def test_tdd_check_and_review_scope():
    t = _text()
    assert "tdd_check.py" in t
    assert "Review scope: slice=" in t
    assert "code-reviewer" in t
    assert "R3" in t and "complete_guard" in t


def test_mode_change_needs_user():
    t = _text()
    assert re.search(r"never change `?Implementation Mode`?[^.]*without the user", t, re.I)


def test_preflight_and_reviewer_agent():
    t = _text()
    assert "## Before you start" in t
    pre = t.split("## Before you start", 1)[1].split("\n## ", 1)[0]
    assert "/isdd" in pre and "AskUserQuestion" in pre
    assert "Implementation Mode: user" in pre
    assert "user_led_guard" in pre and "review tracking" in pre
    assert "code-reviewer:code-reviewer" in t
    assert "SubagentStop" in t and "inline" in t
