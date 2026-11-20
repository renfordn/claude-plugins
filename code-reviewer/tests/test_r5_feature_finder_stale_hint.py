import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def test_stale_or_inferred_hint_is_lead_only():
    with open(os.path.join(ROOT, "skills", "feature-finder", "SKILL.md"), encoding="utf-8") as f:
        s = f.read()
    assert "marked stale, or with basis inferred or unknown, is a lead only" in s
