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

    def test_fallback_when_env_var_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            result = self.module.get_plugin_data_dir("agent-isdd")
            self.assertTrue(os.path.isabs(result))
            self.assertIn("agent-isdd", result)
            self.assertIn(os.path.join(".claude", "plugins", "data"), result)

    def test_never_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            result = self.module.get_plugin_data_dir("agent-isdd")
            self.assertIsNotNone(result)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

    def test_warns_on_stderr_when_env_var_unset(self):
        """Identity-split-hazard fix: the fallback must be loud, not silent -- see
        path_resolution.py's module docstring. Warning goes to stderr (never stdout, which
        every hook uses for its JSON decision) and names both the env var and the plugin."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            captured_err = io.StringIO()
            with contextlib.redirect_stderr(captured_err):
                self.module.get_plugin_data_dir("agent-isdd")
            warning = captured_err.getvalue()
            self.assertIn("CLAUDE_PLUGIN_DATA", warning)
            self.assertIn("agent-isdd", warning)

    def test_no_warning_on_stdout_when_env_var_unset(self):
        """A hook's stdout is reserved for its JSON hookSpecificOutput/systemMessage -- the
        warning must never land there, or it would corrupt every caller's JSON parsing."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            captured_out = io.StringIO()
            with contextlib.redirect_stdout(captured_out):
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
