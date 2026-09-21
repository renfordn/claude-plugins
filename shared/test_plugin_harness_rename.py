"""
Pins the Slice 1 rename requirement: plugin-orchestrator -> plugin-harness.

Asserts:
  1. The plugin directory has moved (plugin-harness exists, plugin-orchestrator
     does not).
  2. None of the listed structural files still contain the literal strings
     "plugin-orchestrator" or "plugin_orchestrator" anywhere in their text.
  3. A handful of narrow semantic checks on the renamed marketplace/plugin/
     settings files, so the test can't be satisfied by an unrelated string
     replacement that happens to remove the old substring without producing
     correct new content.

This test is expected to FAIL until the rename (directory move + literal
reference updates across the monorepo) is performed.
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

OLD_NAME = "plugin-orchestrator"
OLD_MODULE_NAME = "plugin_orchestrator"

# Files that must contain zero references to the old plugin name, addressed
# at their NEW (post-rename) paths under plugin-harness/.
STRUCTURAL_FILES = [
    REPO_ROOT / "plugin-harness" / "hooks" / "hook_state.py",
    REPO_ROOT / "plugin-harness" / "mcp_server" / "server.py",
    REPO_ROOT / "plugin-harness" / "orchestrator" / "schema_extractor.py",
    REPO_ROOT / ".claude-plugin" / "marketplace.json",
    REPO_ROOT / "plugin-harness" / ".claude-plugin" / "marketplace.json",
    REPO_ROOT / "plugin-harness" / ".claude-plugin" / "plugin.json",
    REPO_ROOT / ".claude" / "settings.json",
    REPO_ROOT / ".githooks" / "pre-commit",
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / ".github" / "workflows" / "tests.yml",
    REPO_ROOT / "shared" / "test_plugin_packaging_self_containment.py",
    REPO_ROOT / "plugin-harness" / "tests" / "test_sibling_plugin_discovery.py",
    REPO_ROOT / "plugin-harness" / "hooks" / "test_symlink_coordination.py",
    REPO_ROOT / "plugin-harness" / "tests" / "test_interop_drift_integration.py",
    REPO_ROOT / "plugin-harness" / "tests" / "test_schema_extractor.py",
    REPO_ROOT / "tasks.md",
]


def test_plugin_harness_directory_exists_and_old_directory_is_gone():
    old_dir = REPO_ROOT / "plugin-orchestrator"
    new_dir = REPO_ROOT / "plugin-harness"
    assert new_dir.is_dir(), (
        f"Expected renamed plugin directory {new_dir} to exist; rename has "
        "not been performed yet."
    )
    assert not old_dir.exists(), (
        f"Expected old plugin directory {old_dir} to no longer exist after "
        "the rename (git mv), but it is still present."
    )


@pytest.mark.parametrize("file_path", STRUCTURAL_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_structural_file_has_no_old_plugin_name_references(file_path):
    assert file_path.exists(), (
        f"Expected structural file {file_path} to exist at its post-rename "
        "path; it was not found (rename not performed, or file not moved)."
    )
    content = file_path.read_text()
    assert OLD_NAME not in content, (
        f"{file_path} still contains the literal old plugin name "
        f"'{OLD_NAME}'."
    )
    assert OLD_MODULE_NAME not in content, (
        f"{file_path} still contains the literal old module-path name "
        f"'{OLD_MODULE_NAME}'."
    )


def test_root_marketplace_lists_plugin_harness_entry():
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert marketplace_path.exists(), f"{marketplace_path} not found."
    data = json.loads(marketplace_path.read_text())
    plugins = data.get("plugins", [])
    assert {"name": "plugin-harness", "source": "./plugin-harness"} in plugins, (
        "Root marketplace.json does not list a "
        '{"name": "plugin-harness", "source": "./plugin-harness"} entry. '
        f"Got plugins: {plugins!r}"
    )


def test_nested_plugin_json_name_is_plugin_harness():
    plugin_json_path = REPO_ROOT / "plugin-harness" / ".claude-plugin" / "plugin.json"
    assert plugin_json_path.exists(), f"{plugin_json_path} not found."
    data = json.loads(plugin_json_path.read_text())
    assert data.get("name") == "plugin-harness", (
        f"plugin.json 'name' field is {data.get('name')!r}, expected "
        "'plugin-harness'."
    )


def test_root_settings_enables_plugin_harness():
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    assert settings_path.exists(), f"{settings_path} not found."
    data = json.loads(settings_path.read_text())
    enabled_plugins = data.get("enabledPlugins", data.get("enabled_plugins", {}))
    assert enabled_plugins.get("plugin-harness@renfordn-plugins") is True, (
        "Root .claude/settings.json does not have "
        '"plugin-harness@renfordn-plugins": true in its enabled-plugins map. '
        f"Got: {enabled_plugins!r}"
    )
