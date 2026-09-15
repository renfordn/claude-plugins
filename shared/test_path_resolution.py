#!/usr/bin/env python3
"""Tests for shared path resolution utility."""
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

# Import the module we're testing
import sys
sys.path.insert(0, os.path.dirname(__file__))
from path_resolution import get_plugin_data_dir, get_legacy_subdir_path


class TestPathResolution(unittest.TestCase):
    """Tests for plugin data directory resolution."""

    def test_get_plugin_data_dir_respects_env_var(self):
        """Test that get_plugin_data_dir uses CLAUDE_PLUGIN_DATA env var when set."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data/agent-nelly"}):
            result = get_plugin_data_dir("agent-nelly")
            self.assertEqual(result, "/test/plugins/data/agent-nelly")

    def test_get_plugin_data_dir_fallback_when_env_unset(self):
        """Test that get_plugin_data_dir falls back to default when env var unset."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove CLAUDE_PLUGIN_DATA if it exists
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            result = get_plugin_data_dir("agent-nelly")

            # Should contain the expected path
            self.assertIn(".claude", result)
            self.assertIn("plugins", result)
            self.assertIn("data", result)
            self.assertIn("agent-nelly", result)

            # Should be an absolute path
            self.assertTrue(os.path.isabs(result))

    def test_get_plugin_data_dir_returns_absolute_path(self):
        """Test that get_plugin_data_dir always returns an absolute path."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data"}):
            result = get_plugin_data_dir("agent-tdd")
            self.assertTrue(os.path.isabs(result))

    def test_get_plugin_data_dir_never_returns_none(self):
        """Test that get_plugin_data_dir never returns None."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            result = get_plugin_data_dir("agent-isdd")
            self.assertIsNotNone(result)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

    def test_get_legacy_subdir_path_joins_correctly(self):
        """Test that get_legacy_subdir_path joins plugin dir with legacy subdir."""
        plugin_dir = "/test/plugins/data/agent-nelly"
        legacy_name = "agent-nelly-memory"
        result = get_legacy_subdir_path(plugin_dir, legacy_name)

        expected = os.path.join(plugin_dir, legacy_name)
        self.assertEqual(result, expected)

    def test_get_legacy_subdir_path_with_different_plugins(self):
        """Test get_legacy_subdir_path with different plugin/subdir combinations."""
        test_cases = [
            ("/data/agent-nelly", "agent-nelly-memory", "/data/agent-nelly/agent-nelly-memory"),
            ("/data/agent-tdd", "agent-tdd-state", "/data/agent-tdd/agent-tdd-state"),
            ("/data/agent-isdd", "sdd-memory", "/data/agent-isdd/sdd-memory"),
        ]

        for plugin_dir, legacy_name, expected in test_cases:
            with self.subTest(plugin_dir=plugin_dir, legacy_name=legacy_name):
                result = get_legacy_subdir_path(plugin_dir, legacy_name)
                self.assertEqual(result, expected)

    def test_fallback_path_structure(self):
        """Test that fallback path follows ~/.claude/plugins/data/<plugin-name>/ structure."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            result = get_plugin_data_dir("test-plugin")

            # Should match pattern: .../.claude/plugins/data/test-plugin
            parts = result.split(os.sep)
            self.assertIn(".claude", parts)
            # Find .claude and verify structure
            claude_idx = parts.index(".claude")
            self.assertEqual(parts[claude_idx + 1], "plugins")
            self.assertEqual(parts[claude_idx + 2], "data")
            self.assertEqual(parts[claude_idx + 3], "test-plugin")


if __name__ == "__main__":
    unittest.main()
