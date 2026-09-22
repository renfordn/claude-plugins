"""Slice 8: final rename verification + README/CHANGELOG success-criteria checks.

This is the "official" automated check named in design.md's Validation
Strategy ("Rename verification: git grep -i plugin-orchestrator ... returns
zero hits after the rename lands") and requirements.md's Success Criteria
(README no longer states the plugin is not standalone; CHANGELOG documents
the rename as a breaking change with migration instructions).

Reuses test_plugin_harness_rename_sweep.py's git-grep helper (same
exclusions: historical CHANGELOG.md entries) rather than duplicating the
grep logic, so there is exactly one source of truth for "is the rename
done."
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "shared"))

from test_plugin_harness_rename_sweep import _tracked_files_with_old_name  # noqa: E402

README_PATH = REPO_ROOT / "plugin-harness" / "README.md"
CHANGELOG_PATH = REPO_ROOT / "plugin-harness" / "CHANGELOG.md"


def test_git_grep_returns_zero_hits_for_old_plugin_name():
    remaining = _tracked_files_with_old_name()
    assert remaining == [], (
        f"git grep -i plugin-orchestrator (excluding CHANGELOG.md history and the "
        f"documented env-var fallback exception) must return zero hits. Remaining: {remaining}"
    )


def test_readme_no_longer_states_not_standalone():
    content = README_PATH.read_text()
    assert "not a standalone, general-purpose harness" not in content
    assert "only activates inside an active" not in content.replace("`agent-isdd`", "agent-isdd")
    assert "only activates *inside an active" not in content


def test_readme_documents_standalone_as_supported_and_tested():
    content = README_PATH.read_text()
    assert "Standalone mode" in content
    assert "tested" in content.lower()


def test_changelog_documents_rename_as_breaking_change_with_migration_note():
    content = CHANGELOG_PATH.read_text()
    assert "Breaking" in content
    assert "plugin-orchestrator" in content  # legitimate: naming the old plugin in the entry itself
    assert "plugin-harness" in content
    assert "reinstall" in content.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
