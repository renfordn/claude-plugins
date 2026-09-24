#!/usr/bin/env python3
"""Tests for shared path resolution utility."""
import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

# Import the module we're testing
import sys
sys.path.insert(0, os.path.dirname(__file__))
from path_resolution import PluginDataDirUnavailable, get_plugin_data_dir, get_legacy_subdir_path


class TestPathResolution(unittest.TestCase):
    """Tests for plugin data directory resolution."""

    def test_get_plugin_data_dir_respects_env_var(self):
        """Test that get_plugin_data_dir uses CLAUDE_PLUGIN_DATA env var when set."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data/agent-nelly"}):
            result = get_plugin_data_dir("agent-nelly")
            self.assertEqual(result, "/test/plugins/data/agent-nelly")

    def test_get_plugin_data_dir_raises_when_env_unset(self):
        """No guessed fallback: a guess can point at the wrong install identity's data dir."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            with self.assertRaises(PluginDataDirUnavailable) as ctx:
                get_plugin_data_dir("agent-nelly")
            self.assertIn("CLAUDE_PLUGIN_DATA", str(ctx.exception))
            self.assertIn("agent-nelly", str(ctx.exception))

    def test_get_plugin_data_dir_returns_absolute_path(self):
        """Test that get_plugin_data_dir always returns an absolute path."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data"}):
            result = get_plugin_data_dir("agent-tdd")
            self.assertTrue(os.path.isabs(result))

    def test_get_plugin_data_dir_raises_when_env_empty(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": ""}):
            with self.assertRaises(PluginDataDirUnavailable):
                get_plugin_data_dir("agent-isdd")

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

    def test_nothing_on_stdout_when_env_var_unset(self):
        """A hook's stdout is reserved for its JSON output -- the failure must never land there."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            captured_out = io.StringIO()
            with contextlib.redirect_stdout(captured_out):
                with self.assertRaises(PluginDataDirUnavailable):
                    get_plugin_data_dir("agent-isdd")
            self.assertEqual(captured_out.getvalue(), "")

    def test_no_warning_when_env_var_set(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data/agent-isdd"}):
            captured_err = io.StringIO()
            with contextlib.redirect_stderr(captured_err):
                get_plugin_data_dir("agent-isdd")
            self.assertEqual(captured_err.getvalue(), "")



if __name__ == "__main__":
    unittest.main()
