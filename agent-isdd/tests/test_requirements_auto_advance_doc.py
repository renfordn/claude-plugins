"""Slice 24: requirements-agent / requirements-gate auto-advance doc contract."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/requirements-agent/SKILL.md"
GATE = ROOT / "skills/spec-driven-development/references/requirements-gate.md"


def front(p):
    return p.read_text().split("---", 2)[1]


def test_frontmatter_user_invocable_false_and_no_internal_prefix():
    fm = front(SKILL)
    assert re.search(r"^user-invocable:\s*false\s*$", fm, re.M)
    assert "disable-model-invocation" not in fm
    desc = re.search(r"^description:\s*(.*)$", fm, re.M).group(1)
    assert "[Internal" not in desc
    assert "EARS" in desc and "Requirements Gate" in desc


def test_fast_track_pointer_retargeted():
    t = SKILL.read_text()
    assert "Fast Track\" section" not in t
    assert "Fast Track\" §" not in t
    assert t.count("spec-driven-development/references/fast-track.md") >= 2


def test_gate_auto_advances_unless_open_gaps():
    t = GATE.read_text()
    assert re.search(r"advance[^\n]*without (a )?(user )?confirmation", t, re.I | re.S)
    assert "Open Gaps" in t
    assert "AskUserQuestion" in t


def test_skill_auto_advance_documented():
    t = SKILL.read_text()
    assert "Open Gaps" in t
    assert re.search(r"without (a )?(user )?confirmation", t, re.I)


def test_no_unconditional_confirmation_pause_and_state_approved():
    for p in (SKILL, GATE):
        t = p.read_text()
        assert not re.search(r"pause for (user )?confirmation", t, re.I), p.name
    s = SKILL.read_text()
    assert "Invoked by /isdd" in front(SKILL)
    assert "set `State: Approved`" in s
