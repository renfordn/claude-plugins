"""Structure checks for follow-through: manifests parse and match, and the skill carries the
frontmatter Claude Code reads."""
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
    assert manifest["name"] == "follow-through"
    listed = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())["plugins"]
    assert {"name": "follow-through", "source": "./follow-through"} in listed


def test_skill_frontmatter():
    skill = ROOT / "skills" / "follow-through" / "SKILL.md"
    fm = _frontmatter(skill)
    assert fm["name"].strip() == "follow-through"
    assert len(fm["description"]) <= 1024


def test_skill_references_exist():
    skill = ROOT / "skills" / "follow-through" / "SKILL.md"
    for ref in re.findall(r"`(references/[\w./-]+)`", skill.read_text()):
        assert (skill.parent / ref).exists(), ref
