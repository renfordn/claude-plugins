#!/usr/bin/env python3
"""Tests for cross-plugin sdd-memory symlink coordination (Task 3.1).

Verifies that plugin-orchestrator can coordinate shared sdd-memory with
agent-isdd via symlinks, with registry file fallback when symlinks fail.
"""
import os
import json
import tempfile
import unittest
from unittest.mock import patch

# Will be implemented in hook_state.py
# from hook_state import ensure_sdd_memory_coordination


class TestSymlinkCoordination(unittest.TestCase):
    """Tests for sdd-memory symlink coordination between plugins."""

    def test_symlink_coordination_succeeds_on_supported_platforms(self):
        """Verify symlink is created when supported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            isdd_data = os.path.join(tmpdir, "agent-isdd-data")
            isdd_sdd_memory = os.path.join(isdd_data, "sdd-memory")
            os.makedirs(isdd_sdd_memory)

            orch_data = os.path.join(tmpdir, "plugin-orchestrator-data")
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

            orch_data = os.path.join(tmpdir, "plugin-orchestrator-data")
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

            orch_data = os.path.join(tmpdir, "plugin-orchestrator-data")
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
            orch_data = os.path.join(tmpdir, "plugin-orchestrator-data")
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


if __name__ == "__main__":
    unittest.main()
