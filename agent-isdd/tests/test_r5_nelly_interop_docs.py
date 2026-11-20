import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def test_interop_notes_stale_and_basis():
    with open(os.path.join(ROOT, "INTEROP.md"), encoding="utf-8") as f:
        s = f.read()
    assert "`stale` and `basis`" in s
    assert "a lead to recheck" in s and "never evidence" in s
