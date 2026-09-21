"""Tests for INTEROP parse-failure persistence in CapabilityMap._load_plugin.

Previously, a failure to load/parse a plugin's INTEROP.md only reached
logger.debug with no persistent trail. These tests cover the additional
ErrorLogger-backed persistence of an interop_parse_failure error, gated on
optional error_registry_base_path/project_slug constructor params.
"""

import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.interop_parser import CapabilityMap


class TestInteropParseFailurePersistence(unittest.TestCase):
    """A genuine INTEROP.md parse failure persists interop_parse_failure when
    error_registry_base_path/project_slug are supplied, and no-ops otherwise."""

    def setUp(self):
        self.tmp_plugin_dir = tempfile.TemporaryDirectory()
        # Make agent-isdd/INTEROP.md a directory instead of a file, so
        # read_text() raises IsADirectoryError inside _load_plugin's try block --
        # a genuine parse-failure trigger, not a mock.
        broken_path = Path(self.tmp_plugin_dir.name) / "agent-isdd" / "INTEROP.md"
        broken_path.mkdir(parents=True)

        self.tmp_registry_dir = tempfile.TemporaryDirectory()
        self.base_path = self.tmp_registry_dir.name
        self.project_slug = "test-project"

    def tearDown(self):
        self.tmp_plugin_dir.cleanup()
        self.tmp_registry_dir.cleanup()

    def _registry_path(self):
        return Path(self.base_path) / self.project_slug / "error-registry.json"

    def test_parse_failure_persists_with_path_params(self):
        CapabilityMap(
            self.tmp_plugin_dir.name,
            error_registry_base_path=self.base_path,
            project_slug=self.project_slug,
        )

        registry_path = self._registry_path()
        self.assertTrue(registry_path.exists())
        with open(registry_path) as f:
            registry = json.load(f)

        matches = [e for e in registry["errors"] if e["error_type"] == "interop_parse_failure"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["severity"], "medium")
        self.assertEqual(matches[0]["source_plugin"], "agent-isdd")

    def test_parse_failure_falls_back_to_empty_plugin_info(self):
        cap_map = CapabilityMap(
            self.tmp_plugin_dir.name,
            error_registry_base_path=self.base_path,
            project_slug=self.project_slug,
        )

        plugin = cap_map.get_plugin("agent-isdd")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "agent-isdd")
        self.assertEqual(plugin.capabilities, [])

    def test_parse_failure_omits_persistence_without_path_params(self):
        try:
            CapabilityMap(self.tmp_plugin_dir.name)
        except Exception as e:
            self.fail(f"CapabilityMap should not raise without path params: {e}")

        self.assertFalse(self._registry_path().exists())


if __name__ == "__main__":
    unittest.main()
