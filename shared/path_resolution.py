#!/usr/bin/env python3
"""Shared path resolution utility for Claude-Plugins.

Provides centralized env var-based plugin data directory resolution
that all plugins can use or reference.
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
