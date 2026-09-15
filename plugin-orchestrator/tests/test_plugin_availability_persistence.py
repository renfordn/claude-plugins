"""Tests for real plugin-availability detection + persistence in subagent_stop.py.

orchestrator.hooks.subagent_stop.check_plugin_availability was previously a stub that always
returned True. These tests cover the real hard/soft-dependency detection and the
ErrorLogger-backed persistence of plugin_unavailable errors for hard dependencies only.
"""

import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.hooks.subagent_stop import check_plugin_availability


class TestCheckPluginAvailabilityRealDetection(unittest.TestCase):
    """check_plugin_availability(plugin_name) should reflect real hard/soft dependency state."""

    def test_hard_dependency_unavailable_returns_false(self):
        result = check_plugin_availability("agent-tdd")
        self.assertFalse(result)

    def test_soft_dependency_unavailable_returns_false(self):
        result = check_plugin_availability("agent-nelly")
        self.assertFalse(result)

    def test_unknown_plugin_returns_false(self):
        result = check_plugin_availability("not-a-real-plugin")
        self.assertFalse(result)


class TestCheckPluginAvailabilityPersistence(unittest.TestCase):
    """Persistence of plugin_unavailable errors is gated on hard-dependency status."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base_path = self.tmpdir.name
        self.project_slug = "test-project"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _registry_path(self):
        return Path(self.base_path) / self.project_slug / "error-registry.json"

    def test_hard_dependency_unavailable_persists_error(self):
        check_plugin_availability(
            "agent-tdd",
            error_registry_base_path=self.base_path,
            project_slug=self.project_slug,
        )

        registry_path = self._registry_path()
        self.assertTrue(registry_path.exists())
        with open(registry_path) as f:
            registry = json.load(f)

        self.assertEqual(len(registry["errors"]), 1)
        error = registry["errors"][0]
        self.assertEqual(error["error_type"], "plugin_unavailable")
        self.assertEqual(error["severity"], "high")
        self.assertEqual(error["source_plugin"], "agent-tdd")

    def test_soft_dependency_unavailable_does_not_persist(self):
        check_plugin_availability(
            "agent-nelly",
            error_registry_base_path=self.base_path,
            project_slug=self.project_slug,
        )

        self.assertFalse(self._registry_path().exists())

    def test_missing_path_params_no_op_persistence_no_raise(self):
        try:
            result = check_plugin_availability("agent-tdd")
        except Exception as e:
            self.fail(f"check_plugin_availability should not raise without path params: {e}")

        self.assertFalse(result)
        self.assertFalse(self._registry_path().exists())


if __name__ == "__main__":
    unittest.main()
