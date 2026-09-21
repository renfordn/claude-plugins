#!/usr/bin/env python3
"""Per-plugin copy of shared/path_resolution.py, from the Claude-Plugins monorepo.

Duplicated deliberately, not imported cross-directory: a marketplace-installed plugin package
contains only this plugin's own subdirectory, never the monorepo's sibling shared/ folder --
`sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))` resolved
fine inside the dev checkout but raised ModuleNotFoundError for every real install (found
2026-09-16, affected every plugin depending on it since the ${CLAUDE_PLUGIN_DATA} migration).
Keep this file's content in sync with shared/path_resolution.py and the other plugins' copies
if you change the resolution logic -- shared/ remains the canonical source for whole-repo
testing (see shared/test_path_resolution.py), this is the one that actually ships.
"""
import os


def get_plugin_data_dir(plugin_name: str) -> str:
    """Resolve plugin data directory using ${CLAUDE_PLUGIN_DATA} env var.

    Args:
        plugin_name: Name of the plugin (e.g., "agent-nelly")

    Returns:
        Absolute path to plugin data directory. Never None.

    Behavior:
        - If CLAUDE_PLUGIN_DATA env var is set (Claude Code runtime): returns that path
        - If unset (local dev/testing): returns ~/.claude/plugins/data/{plugin_name}/

    The returned path may not exist; caller is responsible for creation. The env var
    is set by Claude Code to ensure data persists across updates and is cleaned on uninstall.
    """
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        # Fallback: local development or testing when Claude Code doesn't set env var
        data_dir = os.path.join(
            os.path.expanduser("~"),
            ".claude",
            "plugins",
            "data",
            plugin_name
        )
    return data_dir


def get_legacy_subdir_path(plugin_data_dir: str, legacy_name: str) -> str:
    """Join plugin data directory with legacy subdir name.

    Args:
        plugin_data_dir: Base plugin data directory (from get_plugin_data_dir)
        legacy_name: Legacy subdir name (e.g., "agent-nelly-memory")

    Returns:
        Joined absolute path: {plugin_data_dir}/{legacy_name}/

    Example:
        data_dir = get_plugin_data_dir("agent-nelly")
        memory_path = get_legacy_subdir_path(data_dir, "agent-nelly-memory")
        # memory_path = ~/.claude/plugins/data/agent-nelly/agent-nelly-memory/
    """
    return os.path.join(plugin_data_dir, legacy_name)


def get_sibling_plugin_data_dir(own_plugin_name: str, sibling_plugin_name: str) -> str:
    """Resolve ANOTHER installed plugin's data directory from this plugin's own hook process.

    This is plugin-orchestrator-specific (not part of the other plugins' copies of this
    file) because it's the only plugin whose hooks need to read/write a sibling
    plugin's data dir at all (agent-isdd's sdd-memory/ -- see hooks/hook_state.py).

    ${CLAUDE_PLUGIN_DATA} is set by Claude Code to *this running plugin's own* data
    directory only -- there is no env var exposing a sibling plugin's directory.
    Calling get_plugin_data_dir(sibling_plugin_name) does NOT resolve the sibling: that
    function ignores the name it's given whenever ${CLAUDE_PLUGIN_DATA} is set and
    just returns the env var's value, so every "sibling" lookup silently pointed at
    plugin-orchestrator's own (empty) directory instead of agent-isdd's (found
    2026-09-21 -- before_continue/subagent_stop always saw "no active SDD workflow"
    in a real marketplace install, even though tests passed with the env var unset).

    Real on-disk directory names under ~/.claude/plugins/data/ are
    "<plugin-name>-<marketplace>" (e.g. "agent-isdd-renfordn-plugins",
    "plugin-orchestrator-renfordn-plugins") for a marketplace install, or bare
    "<plugin-name>" for a marketplace-less/local install. This derives the
    sibling's directory by substituting `sibling_plugin_name` for
    `own_plugin_name` as the leading path segment of ${CLAUDE_PLUGIN_DATA},
    preserving whatever marketplace suffix and parent directory this install
    actually uses -- so it stays correct across marketplaces, project-scope
    installs, and local dev, without hardcoding "-renfordn-plugins" anywhere.

    Falls back to get_plugin_data_dir(sibling_plugin_name) -- the same
    local dev/testing path used before this function existed -- when
    ${CLAUDE_PLUGIN_DATA} is unset, or when `own_plugin_name` doesn't actually
    prefix-match this plugin's own resolved directory name (an unexpected
    shape we can't safely rewrite; better to fall back than guess wrong).

    Args:
        own_plugin_name: This running plugin's name (e.g. "plugin-orchestrator").
        sibling_plugin_name: The other plugin's name (e.g. "agent-isdd").

    Returns:
        Absolute path to the sibling plugin's data directory. Never None.
    """
    own_data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not own_data_dir:
        return get_plugin_data_dir(sibling_plugin_name)

    parent = os.path.dirname(own_data_dir)
    basename = os.path.basename(own_data_dir)

    if basename == own_plugin_name:
        sibling_basename = sibling_plugin_name
    elif basename.startswith(own_plugin_name + "-"):
        suffix = basename[len(own_plugin_name):]  # e.g. "-renfordn-plugins"
        sibling_basename = sibling_plugin_name + suffix
    else:
        return get_plugin_data_dir(sibling_plugin_name)

    return os.path.join(parent, sibling_basename)
