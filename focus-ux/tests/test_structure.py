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


def test_output_style_is_forced_and_keeps_coding_instructions():
    fm = _frontmatter(ROOT / "output-styles" / "focus.md")
    assert fm["name"].strip() == "Focus"
    assert fm["force-for-plugin"].strip() == "true"
    assert fm["keep-coding-instructions"].strip() == "true"


def test_output_style_stays_lean():
    # Output styles sit in every request's system prompt; keep the cost small.
    assert len((ROOT / "output-styles" / "focus.md").read_text().split()) < 700


def test_skill_frontmatter_and_references():
    skill = ROOT / "skills" / "visual-brief" / "SKILL.md"
    fm = _frontmatter(skill)
    assert fm["name"].strip() == "visual-brief"
    assert len(fm["description"]) <= 1024
    for ref in re.findall(r"`(references/[\w./-]+)`", skill.read_text()):
        assert (skill.parent / ref).exists(), ref
