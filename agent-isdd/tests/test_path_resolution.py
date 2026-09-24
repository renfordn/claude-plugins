"""Tests for hooks/path_resolution.py.

Added 2026-09-24 alongside the identity-split-hazard fix (see path_resolution.py's own
docstring, and shared/test_path_resolution.py for the canonical whole-repo copy of these same
cases). get_plugin_data_dir() is a plain function (no stdin payload), so these import the
module directly via importlib rather than spawning a subprocess -- mirrors test_sdd_memory.py's
_load_sdd_memory_module() pattern for the same reason.
"""
import contextlib
import importlib.util
import io
import os
import unittest
from unittest.mock import patch

import hook_test_utils as h


def _load_path_resolution_module():
    path = os.path.join(h.HOOKS_DIR, "path_resolution.py")
    spec = importlib.util.spec_from_file_location("path_resolution_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GetPluginDataDirTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_path_resolution_module()

    def test_respects_env_var_when_set(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data/agent-isdd-inline"}):
            result = self.module.get_plugin_data_dir("agent-isdd")
            self.assertEqual(result, "/test/plugins/data/agent-isdd-inline")

    def test_raises_when_env_var_unset(self):
        """No guessed fallback: a guess can point at the wrong install identity's data dir."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            with self.assertRaises(self.module.PluginDataDirUnavailable) as ctx:
                self.module.get_plugin_data_dir("agent-isdd")
            self.assertIn("CLAUDE_PLUGIN_DATA", str(ctx.exception))
            self.assertIn("agent-isdd", str(ctx.exception))

    def test_raises_when_env_var_empty(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": ""}):
            with self.assertRaises(self.module.PluginDataDirUnavailable):
                self.module.get_plugin_data_dir("agent-isdd")

    def test_nothing_on_stdout_when_env_var_unset(self):
        """A hook's stdout is reserved for its JSON output -- the failure must never land there."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            captured_out = io.StringIO()
            with contextlib.redirect_stdout(captured_out):
                with self.assertRaises(self.module.PluginDataDirUnavailable):
                    self.module.get_plugin_data_dir("agent-isdd")
            self.assertEqual(captured_out.getvalue(), "")

    def test_no_warning_when_env_var_set(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugins/data/agent-isdd"}):
            captured_err = io.StringIO()
            with contextlib.redirect_stderr(captured_err):
                self.module.get_plugin_data_dir("agent-isdd")
            self.assertEqual(captured_err.getvalue(), "")


class GetLegacySubdirPathTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_path_resolution_module()

    def test_joins_plugin_dir_with_legacy_subdir(self):
        result = self.module.get_legacy_subdir_path("/data/agent-isdd", "sdd-memory")
        self.assertEqual(result, os.path.join("/data/agent-isdd", "sdd-memory"))


if __name__ == "__main__":
    unittest.main()
