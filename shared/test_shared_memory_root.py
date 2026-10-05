#!/usr/bin/env python3
"""Tests for the shared memory root option (userConfig `shared_memory_root`) in path_resolution."""
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from path_resolution import (  # noqa: E402
    SHARED_MEMORY_ROOT_ENV, PluginDataDirUnavailable, ensure_shared_root_scaffold,
    get_memory_root, get_shared_memory_root,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPIES = [
    "shared/path_resolution.py",
    "agent-isdd/hooks/path_resolution.py",
    "agent-nelly/hooks/path_resolution.py",
    "agent-tdd/hooks/path_resolution.py",
]
_BLOCK_RE = re.compile(
    r"# --- shared memory root .*?# --- end shared memory root ---", re.S
)


class SharedMemoryRootTests(unittest.TestCase):
    def test_env_var_name_matches_userconfig_key(self):
        # Claude Code exports userConfig KEY as CLAUDE_PLUGIN_OPTION_<KEY uppercased>.
        self.assertEqual(SHARED_MEMORY_ROOT_ENV, "CLAUDE_PLUGIN_OPTION_" + "shared_memory_root".upper())

    def test_unset_empty_and_placeholder_mean_not_configured(self):
        for value in (None, "", "   ", "${user_config.shared_memory_root}"):
            with self.subTest(value=value):
                env = {} if value is None else {SHARED_MEMORY_ROOT_ENV: value}
                with patch.dict(os.environ, env, clear=False):
                    if value is None:
                        os.environ.pop(SHARED_MEMORY_ROOT_ENV, None)
                    self.assertIsNone(get_shared_memory_root())

    def test_absolute_root_is_normalised(self):
        with patch.dict(os.environ, {SHARED_MEMORY_ROOT_ENV: "/srv/mem/../memory/"}):
            self.assertEqual(get_shared_memory_root(), "/srv/memory")

    def test_tilde_and_env_vars_expand(self):
        with patch.dict(os.environ, {SHARED_MEMORY_ROOT_ENV: "~/mem", "HOME": "/home/u"}):
            self.assertEqual(get_shared_memory_root(), "/home/u/mem")
        with patch.dict(os.environ, {SHARED_MEMORY_ROOT_ENV: "$MEMBASE/x", "MEMBASE": "/data"}):
            self.assertEqual(get_shared_memory_root(), "/data/x")

    def test_relative_root_fails_clearly(self):
        with patch.dict(os.environ, {SHARED_MEMORY_ROOT_ENV: "relative/mem"}):
            with self.assertRaises(PluginDataDirUnavailable) as ctx:
                get_shared_memory_root()
            self.assertIn("absolute", str(ctx.exception))

    def test_memory_root_prefers_shared_root(self):
        with patch.dict(os.environ, {SHARED_MEMORY_ROOT_ENV: "/shared", "CLAUDE_PLUGIN_DATA": "/data/p"}):
            self.assertEqual(get_memory_root("agent-nelly"), "/shared")

    def test_memory_root_falls_back_to_plugin_data(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/data/p"}):
            os.environ.pop(SHARED_MEMORY_ROOT_ENV, None)
            self.assertEqual(get_memory_root("agent-nelly"), "/data/p")

    def test_memory_root_with_neither_set_raises(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SHARED_MEMORY_ROOT_ENV, None)
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            with self.assertRaises(PluginDataDirUnavailable):
                get_memory_root("agent-isdd")

    def _settings(self, plugin_configs):
        import json
        tmp = tempfile.mkdtemp(prefix="claude-config-")
        with open(os.path.join(tmp, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": plugin_configs}, fh)
        return tmp

    def _unset_env(self, **extra):
        env = patch.dict(os.environ, extra)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(SHARED_MEMORY_ROOT_ENV, None)

    def test_settings_fallback_when_own_option_unset(self):
        # The @synced identity was never configured, but @inline was: the root must still resolve.
        cfg = self._settings({"agent-nelly@inline": {"options": {"shared_memory_root": "/srv/mem"}}})
        self._unset_env(CLAUDE_CONFIG_DIR=cfg)
        self.assertEqual(get_shared_memory_root(), "/srv/mem")

    def test_settings_fallback_covers_placeholder_and_other_plugins(self):
        cfg = self._settings({"agent-isdd@x": {"options": {"shared_memory_root": "/srv/mem"}}})
        self._unset_env(CLAUDE_CONFIG_DIR=cfg, **{SHARED_MEMORY_ROOT_ENV: "${user_config.shared_memory_root}"})
        self.assertEqual(get_shared_memory_root(), "/srv/mem")

    def test_env_beats_settings_and_unrelated_plugins_are_ignored(self):
        cfg = self._settings({"focus-ux@inline": {"options": {"shared_memory_root": "/other"}}})
        self._unset_env(CLAUDE_CONFIG_DIR=cfg)
        self.assertIsNone(get_shared_memory_root())
        os.environ[SHARED_MEMORY_ROOT_ENV] = "/own"
        cfg2 = self._settings({"agent-nelly@inline": {"options": {"shared_memory_root": "/srv/mem"}}})
        os.environ["CLAUDE_CONFIG_DIR"] = cfg2
        self.assertEqual(get_shared_memory_root(), "/own")

    def test_malformed_settings_mean_not_configured(self):
        tmp = tempfile.mkdtemp(prefix="claude-config-")
        with open(os.path.join(tmp, "settings.json"), "w") as fh:
            fh.write("{not json")
        self._unset_env(CLAUDE_CONFIG_DIR=tmp)
        self.assertIsNone(get_shared_memory_root())

    def test_scaffold_creates_git_files_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "shared")
            ensure_shared_root_scaffold(root)
            with open(os.path.join(root, ".gitignore")) as fh:
                self.assertIn("nelly-index.json", fh.read())
            with open(os.path.join(root, ".gitattributes")) as fh:
                self.assertIn("MEMORY.md merge=union", fh.read())

            with open(os.path.join(root, ".gitignore"), "w") as fh:
                fh.write("mine\n")
            ensure_shared_root_scaffold(root)
            with open(os.path.join(root, ".gitignore")) as fh:
                self.assertEqual(fh.read(), "mine\n")

    def test_shared_root_block_identical_in_every_copy(self):
        blocks = {}
        for rel in COPIES:
            with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as fh:
                m = _BLOCK_RE.search(fh.read())
            self.assertIsNotNone(m, f"{rel} is missing the shared memory root block")
            blocks[rel] = m.group(0)
        canonical = blocks["shared/path_resolution.py"]
        for rel, block in blocks.items():
            with self.subTest(copy=rel):
                self.assertEqual(block, canonical, f"{rel}'s shared memory root block drifted")


if __name__ == "__main__":
    unittest.main()
