"""Pin for implementation-handoff.md intro phrase (split from test_isdd_ref_pointers.py)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def test_handoff_intro_preserved():
    sdd_dir = SKILLS / "spec-driven-development"
    ref = (sdd_dir / "references" / "implementation-handoff.md").read_text(encoding="utf-8")
    assert "serial run is a single, one-directional handoff" in " ".join(ref.split())
    assert "tdd-parallel lead" in " ".join(ref.split())
