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


class PluginDataDirUnavailable(RuntimeError):
    """CLAUDE_PLUGIN_DATA is not set, so this process can't know its plugin's data directory."""


def get_plugin_data_dir(plugin_name: str) -> str:
    """Resolve the plugin data directory from ${CLAUDE_PLUGIN_DATA}.

    Args:
        plugin_name: Name of the plugin (e.g., "agent-nelly"), used only in the error message.

    Returns:
        The value of CLAUDE_PLUGIN_DATA. The directory may not exist yet; the caller creates it.

    Raises:
        PluginDataDirUnavailable: CLAUDE_PLUGIN_DATA is unset or empty.

    Claude Code sets CLAUDE_PLUGIN_DATA for hook subprocesses and substitutes
    ${CLAUDE_PLUGIN_DATA} in skill/command content. There is deliberately no fallback: the real
    directory is ~/.claude/plugins/data/<plugin>-<marketplace>/ (per install identity), so any
    guessed path can silently read or write the wrong identity's state. A script run by hand
    must be given the variable explicitly, e.g.
    `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py"`
    from skill/command content. Tests set it to a temp dir.
    """
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        raise PluginDataDirUnavailable(
            f"{plugin_name}: CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code "
            f"(hook, or a skill/command that passes CLAUDE_PLUGIN_DATA=\"${{CLAUDE_PLUGIN_DATA}}\"), "
            f"or set CLAUDE_PLUGIN_DATA to this plugin's data directory yourself."
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
        # memory_path = ${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/
    """
    return os.path.join(plugin_data_dir, legacy_name)
