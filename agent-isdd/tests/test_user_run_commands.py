"""Commands with disable-model-invocation are framed as user-run wherever the model is told about them."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["skills/spec-driven-development/references/continue-protocol.md", "hooks/session_start.py"]


def test_disabled_commands_are_asked_of_the_user():
    for rel in FILES:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert not re.search(r"\b(Run|using) `/isdd-(rewind|board-sync)", text), rel
        for m in re.finditer(r"`/isdd-(rewind|board-sync)", text):
            window = text[max(0, m.start() - 60):m.start()]
            assert "ask the user" in window.lower(), (rel, window)
