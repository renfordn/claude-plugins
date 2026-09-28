"""Structure checks for focus-ux: manifests parse, the output style and skill carry the
frontmatter Claude Code reads, and every reference the skill names exists."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent


def _frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    assert m, f"{path} has no frontmatter"
    return dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)


def test_manifest_and_marketplace_listing():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "focus-ux"
    listed = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())["plugins"]
    assert {"name": "focus-ux", "source": "./focus-ux"} in listed


def test_manifest_no_longer_claims_no_hooks():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert "no agents or hooks" not in manifest["description"].lower()


def test_first_class_no_longer_declares_hooks_absent():
    fc_path = ROOT / ".claude-plugin" / "first-class.json"
    fc = json.loads(fc_path.read_text())
    assert "hooks" not in fc.get("declared_absent", [])


def test_hooks_json_registers_optin_and_push_hooks():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())

    def _commands(event):
        return [h["command"] for group in hooks["hooks"][event] for h in group["hooks"]]

    optin_cmds = _commands("UserPromptSubmit")
    assert any("checkpoint_optin.py" in c for c in optin_cmds)
    stop_cmds = _commands("Stop")
    assert any("checkpoint_push.py" in c for c in stop_cmds)

    for event in ("UserPromptSubmit", "Stop"):
        for group in hooks["hooks"][event]:
            for h in group["hooks"]:
                assert h["type"] == "command"
                assert "${CLAUDE_PLUGIN_ROOT}" in h["command"]
                name = h["command"].rsplit("/", 1)[-1].rstrip('"')
                assert (ROOT / "hooks" / name).is_file(), name


def test_output_style_is_forced_and_keeps_coding_instructions():
    fm = _frontmatter(ROOT / "output-styles" / "focus.md")
    assert fm["name"].strip() == "Focus"
    assert fm["force-for-plugin"].strip() == "true"
    assert fm["keep-coding-instructions"].strip() == "true"


def test_output_style_stays_lean():
    # Output styles sit in every request's system prompt; keep the cost small.
    assert len((ROOT / "output-styles" / "focus.md").read_text().split()) < 700


def test_interop_documents_checkpoint_push_contracts():
    text = (ROOT / "INTEROP.md").read_text()
    assert "has no agents, hooks" not in text
    for token in ("[checkpoint-push]", "FOCUS_UX_CHECKPOINT_PUSH",
                  "<!--CHECKPOINT:", "<!--CHECKPOINT-PUSHED:"):
        assert token in text, token


def test_skill_frontmatter_and_references():
    skill = ROOT / "skills" / "visual-brief" / "SKILL.md"
    fm = _frontmatter(skill)
    assert fm["name"].strip() == "visual-brief"
    assert len(fm["description"]) <= 1024
    for ref in re.findall(r"`(references/[\w./-]+)`", skill.read_text()):
        assert (skill.parent / ref).exists(), ref


def test_hooks_json_registers_render_path_hint_on_session_start():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    cmds = [h["command"] for g in hooks["hooks"]["SessionStart"] for h in g["hooks"]]
    assert any("render_path_hint.py" in c and "${CLAUDE_PLUGIN_ROOT}" in c for c in cmds)


def test_output_style_names_the_session_line_not_an_unexpanded_variable():
    """${CLAUDE_PLUGIN_ROOT} is not expanded inside output-style text, so the style must point at
    the SessionStart line that carries the resolved path, and say what to do when it is absent."""
    text = (ROOT / "output-styles" / "focus.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "focus-ux render script:" in text
    assert "hand-draft" in text
