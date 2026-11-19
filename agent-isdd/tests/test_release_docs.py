"""Release 2 is recorded under CHANGELOG [Unreleased] and the README documents the user-facing changes."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _unreleased():
    """Release 2 entries live under [0.6.0]."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return text.split("## [0.6.0]", 1)[1].split("\n## [", 1)[0]


def test_changelog_unreleased_groups_and_items():
    body = _unreleased()
    for heading in ("### Added", "### Changed", "### Fixed", "### Known limits"):
        assert heading in body, heading
    low = body.lower()
    for term in (
        "pre_write_dispatch", "state_guard", "complete_guard", "user_led_guard",
        "approval hash", "refreeze", "baseline", "resume_context", "research_cache",
        "review_tracking", "isdd-coach", "risk-depth", "evals", "parallel: on",
        "tdd-parallel", "alphanumeric", "user-invocable", "interop", "isdd-pickup",
        "/isdd-rewind", "/isdd-board-sync", "effort", "description budget",
        "bash writes", "agent-writable", "downgrade",
    ):
        assert term.lower() in low, term


def test_plugin_version_matches_newest_changelog_heading():
    version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    after = changelog.split("## [Unreleased]", 1)[1]
    assert re.search(r"^## \[(\d+\.\d+\.\d+)\]", after, re.M).group(1) == version


def test_readme_documents_user_facing_changes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for term in (
        "Risk", "elevated", "Implementation Mode", "isdd-coach", "Parallel: on",
        "approval.py", "AskUserQuestion", "/isdd-rewind", "/isdd-board-sync",
    ):
        assert term in readme, term
