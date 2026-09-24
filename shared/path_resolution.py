#!/usr/bin/env python3
"""Shared path resolution utility for Claude-Plugins.

Provides centralized env var-based plugin data directory resolution
that all plugins can use or reference.

Canonical source for whole-repo testing (see test_path_resolution.py); the per-plugin copies
(e.g. agent-isdd/hooks/path_resolution.py) are what actually ships and what real hooks execute
-- keep them in sync with this file if you change the resolution logic.

Identity-split hazard (found 2026-09-24 in agent-isdd, debugging a false commit-gate denial):
Claude Code can load the SAME plugin under more than one identity in the same install -- e.g. a
monorepo's local checkout as `<plugin>@inline` versus a marketplace install as
`<plugin>@<marketplace>` (see ~/.claude.json's `pluginUsage` map). Each identity gets its OWN
`${CLAUDE_PLUGIN_DATA}` injected into ITS registered hook subprocesses -- real hook invocations
for a given session consistently see whichever identity's env var is wired up, so every
registered hook agrees with every other registered hook within one session. The env var is
NEVER injected into a plain manual subprocess (e.g. a Bash tool call running a hook script
directly instead of going through the actual hook chain), so get_plugin_data_dir() raises
PluginDataDirUnavailable there rather than guessing a path that may not match whichever
identity's hooks are actually registered this session. See agent-isdd/hooks/path_resolution.py's docstring for the full
writeup and the "never invoke hooks/*.py directly" rule this implies for every plugin's hooks,
not just agent-isdd's.
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
