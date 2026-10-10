"""Plugin manifest and hooks.json registration."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def test_plugin_manifest():
    m = load(".claude-plugin", "plugin.json")
    assert m["name"] == "monday-sync" and m["version"] == "0.3.4"
    assert m["author"] == {"name": "jay"} and m["description"]


def commands(event, matcher=None):
    groups = load("hooks", "hooks.json")["hooks"][event]
    return [h["command"] for g in groups if matcher is None or g.get("matcher") == matcher
            for h in g["hooks"] if h["type"] == "command"]


def test_hooks_json_registers_flag_sync_and_session_start():
    assert commands("PostToolUse", "Write|Edit|MultiEdit|Bash") == [
        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/flag_sync.py"']
    assert commands("SessionStart") == ['python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"']


def test_every_hook_command_points_at_an_existing_script():
    hooks = load("hooks", "hooks.json")["hooks"]
    for groups in hooks.values():
        for g in groups:
            for h in g["hooks"]:
                rel = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"]+)", h["command"]).group(1)
                assert os.path.isfile(os.path.join(ROOT, rel)), rel


def test_descriptions_are_short():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    m = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    assert len(m["description"]) <= 200
    for f in (root / "skills").glob("*/SKILL.md"):
        d = re.search(r'^description: "(.*)"$', f.read_text(), re.M).group(1)
        assert len(d) <= 400, f
