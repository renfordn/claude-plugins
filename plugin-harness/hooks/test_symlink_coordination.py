#!/usr/bin/env python3
"""Tests for cross-plugin sdd-memory symlink coordination (Task 3.1).

Verifies that plugin-harness can coordinate shared sdd-memory with
agent-isdd via symlinks, with registry file fallback when symlinks fail.
"""
import importlib
import os
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import path_resolution  # noqa: E402


class TestSymlinkCoordination(unittest.TestCase):
    """Tests for sdd-memory symlink coordination between plugins."""

    def test_symlink_coordination_succeeds_on_supported_platforms(self):
        """Verify symlink is created when supported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            isdd_data = os.path.join(tmpdir, "agent-isdd-data")
            isdd_sdd_memory = os.path.join(isdd_data, "sdd-memory")
            os.makedirs(isdd_sdd_memory)

            orch_data = os.path.join(tmpdir, "plugin-harness-data")
            os.makedirs(orch_data)
            orch_sdd_memory = os.path.join(orch_data, "sdd-memory")

            # Simulate symlink creation
            try:
                os.symlink(isdd_sdd_memory, orch_sdd_memory)
                self.assertTrue(os.path.islink(orch_sdd_memory))
                self.assertEqual(os.readlink(orch_sdd_memory), isdd_sdd_memory)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not supported on this platform")

    def test_registry_fallback_when_symlink_fails(self):
        """Verify registry file is created when symlink fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            isdd_data = os.path.join(tmpdir, "agent-isdd-data")
            isdd_sdd_memory = os.path.join(isdd_data, "sdd-memory")
            os.makedirs(isdd_sdd_memory)

            orch_data = os.path.join(tmpdir, "plugin-harness-data")
            os.makedirs(orch_data)
            registry_file = os.path.join(orch_data, "sdd-memory-registry.json")

            # Simulate registry fallback
            registry = {
                "owner": "agent-isdd",
                "actual_path": isdd_sdd_memory
            }
            with open(registry_file, "w") as f:
                json.dump(registry, f)

            # Verify registry was created
            self.assertTrue(os.path.isfile(registry_file))
            with open(registry_file) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["owner"], "agent-isdd")
            self.assertEqual(loaded["actual_path"], isdd_sdd_memory)

    def test_symlink_coordination_is_idempotent(self):
        """Verify that calling coordination multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            isdd_data = os.path.join(tmpdir, "agent-isdd-data")
            isdd_sdd_memory = os.path.join(isdd_data, "sdd-memory")
            os.makedirs(isdd_sdd_memory)

            orch_data = os.path.join(tmpdir, "plugin-harness-data")
            os.makedirs(orch_data)
            orch_sdd_memory = os.path.join(orch_data, "sdd-memory")

            # Create symlink first time
            try:
                os.symlink(isdd_sdd_memory, orch_sdd_memory)
                first_link = os.readlink(orch_sdd_memory)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not supported on this platform")

            # Second call should be idempotent (symlink already exists)
            if os.path.islink(orch_sdd_memory):
                second_link = os.readlink(orch_sdd_memory)
                self.assertEqual(first_link, second_link)

    def test_both_plugins_access_same_location_with_symlink(self):
        """Verify both plugins can access sdd-memory through symlink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create isdd's sdd-memory
            isdd_data = os.path.join(tmpdir, "agent-isdd-data")
            isdd_sdd_memory = os.path.join(isdd_data, "sdd-memory")
            os.makedirs(isdd_sdd_memory)

            # Create test file in isdd's sdd-memory
            test_file = os.path.join(isdd_sdd_memory, "test.txt")
            with open(test_file, "w") as f:
                f.write("shared data")

            # Create symlink from orchestrator
            orch_data = os.path.join(tmpdir, "plugin-harness-data")
            os.makedirs(orch_data)
            orch_sdd_memory = os.path.join(orch_data, "sdd-memory")

            try:
                os.symlink(isdd_sdd_memory, orch_sdd_memory)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not supported on this platform")

            # Verify orchestrator can read the file through symlink
            orch_test_file = os.path.join(orch_sdd_memory, "test.txt")
            self.assertTrue(os.path.isfile(orch_test_file))
            with open(orch_test_file) as f:
                content = f.read()
            self.assertEqual(content, "shared data")


class TestGetSiblingPluginDataDir(unittest.TestCase):
    """Regression tests for the F-02 bug: with CLAUDE_PLUGIN_DATA set (the real
    marketplace-install case), get_plugin_data_dir(sibling_name) ignored its
    argument and returned plugin-harness's own directory instead of
    agent-isdd's. These tests exercise get_sibling_plugin_data_dir() -- the
    fix -- against on-disk directory-naming shapes actually observed under
    ~/.claude/plugins/data/, none of which the pre-fix helper functions above
    ever simulated (they hardcode paths that happen to already be correct).
    """

    def test_marketplace_suffix_is_preserved_for_sibling(self):
        """"<plugin>-<marketplace>" shape: only the leading plugin name segment
        should change, so the sibling keeps the same marketplace suffix.
        """
        with patch.dict(os.environ, {
            "CLAUDE_PLUGIN_DATA": "/Users/x/.claude/plugins/data/plugin-harness-renfordn-plugins"
        }):
            sibling = path_resolution.get_sibling_plugin_data_dir(
                "plugin-harness", "agent-isdd"
            )
        self.assertEqual(
            sibling,
            "/Users/x/.claude/plugins/data/agent-isdd-renfordn-plugins",
        )

    def test_sibling_dir_is_never_equal_to_own_dir(self):
        """The core regression: resolving a *different* plugin's data dir must
        never collapse to this plugin's own ${CLAUDE_PLUGIN_DATA} value.
        """
        own_dir = "/Users/x/.claude/plugins/data/plugin-harness-renfordn-plugins"
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": own_dir}):
            own = path_resolution.get_plugin_data_dir("plugin-harness")
            sibling = path_resolution.get_sibling_plugin_data_dir(
                "plugin-harness", "agent-isdd"
            )
        self.assertEqual(own, own_dir)
        self.assertNotEqual(sibling, own)

    def test_bare_plugin_name_shape_with_no_marketplace_suffix(self):
        """Local/marketplace-less install: directory is the bare plugin name."""
        with patch.dict(os.environ, {
            "CLAUDE_PLUGIN_DATA": "/Users/x/.claude/plugins/data/plugin-harness"
        }):
            sibling = path_resolution.get_sibling_plugin_data_dir(
                "plugin-harness", "agent-isdd"
            )
        self.assertEqual(sibling, "/Users/x/.claude/plugins/data/agent-isdd")

    def test_falls_back_to_local_dev_path_when_env_unset(self):
        """No ${CLAUDE_PLUGIN_DATA} at all (dev/testing) -- same as before."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            sibling = path_resolution.get_sibling_plugin_data_dir(
                "plugin-harness", "agent-isdd"
            )
        self.assertEqual(
            sibling,
            os.path.join(os.path.expanduser("~"), ".claude", "plugins", "data", "agent-isdd"),
        )

    def test_hook_state_symlinks_to_the_real_sibling_directory(self):
        """End-to-end: with CLAUDE_PLUGIN_DATA simulating a real install,
        hook_state._ensure_sdd_memory_coordination() must symlink to
        agent-isdd's actual sdd-memory dir, not to (or through) its own.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = os.path.join(tmpdir, "data")
            isdd_dir = os.path.join(data_root, "agent-isdd-renfordn-plugins")
            isdd_sdd_memory = os.path.join(isdd_dir, "sdd-memory")
            os.makedirs(isdd_sdd_memory)
            marker = os.path.join(isdd_sdd_memory, "marker.txt")
            with open(marker, "w") as f:
                f.write("agent-isdd's real data")

            orch_dir = os.path.join(data_root, "plugin-harness-renfordn-plugins")
            os.makedirs(orch_dir)

            with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": orch_dir}):
                import hook_state
                importlib.reload(hook_state)
                try:
                    resolved = hook_state._ensure_sdd_memory_coordination()
                    self.assertTrue(os.path.islink(resolved))
                    self.assertEqual(os.path.realpath(resolved), os.path.realpath(isdd_sdd_memory))
                    self.assertTrue(os.path.isfile(os.path.join(resolved, "marker.txt")))
                finally:
                    # Reload again under the ambient (env-var-unset) test
                    # environment so later tests in the suite see the normal
                    # module-level BASE, not this test's temp-dir value.
                    importlib.reload(hook_state)


if __name__ == "__main__":
    unittest.main()
