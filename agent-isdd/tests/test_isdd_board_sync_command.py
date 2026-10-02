"""commands/isdd-board-sync.md -- the drift-repair command for the Plan Board."""
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "commands", "isdd-board-sync.md")


def _text():
    with open(PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def test_command_has_frontmatter_and_stays_small():
    text = _text()
    assert text.startswith("---\ndescription: ")
    assert text.count("\n") <= 400


def test_command_drives_verify_resync_and_confirmed_prune():
    low = _text().lower()
    for needle in ("plan_board_sync.py", "verify", "resync", "prune", "arifactdata list".replace("arif", "artif"),
                   "artifactdata batch", "mark", "--board-json", "--confirm"):
        assert needle.lower() in low, needle
    assert "never block" in low
    assert "confirm" in low and "before" in low  # asks the user before pruning
