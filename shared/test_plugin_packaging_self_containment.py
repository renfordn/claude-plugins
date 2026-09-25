#!/usr/bin/env python3
"""Regression test for the 2026-09-16 packaging bug: every plugin that used
path_resolution.py imported it from a monorepo-relative shared/ directory
(`os.path.join(os.path.dirname(__file__), '..', '..', 'shared')`), which only
resolves inside this dev checkout. A marketplace-installed plugin package contains
only that plugin's own subdirectory -- shared/ is never bundled -- so every one of
these hooks raised ModuleNotFoundError on a real fresh install, silently, since no
CI ever ran a plugin from outside the monorepo.

Fix: each consuming plugin now keeps its own copy of path_resolution.py inside its
own hooks/ directory (see that file's own docstring). This test copies each
plugin's hooks/ directory to an isolated tmp location -- deliberately excluding the
rest of the repo, including shared/ -- and confirms path_resolution still imports
from there. If a future edit reintroduces a `../../shared`-style cross-directory
import, this test fails the same way a fresh install would.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Plugin hooks dirs known to depend on path_resolution.py as of 2026-09-16.
PLUGIN_HOOKS_DIRS = [
    "agent-isdd/hooks",
    "agent-tdd/hooks",
    "agent-nelly/hooks",
]


class PluginPackagingSelfContainmentTests(unittest.TestCase):
    def test_each_plugin_hooks_dir_bundles_its_own_path_resolution(self):
        for rel_dir in PLUGIN_HOOKS_DIRS:
            with self.subTest(plugin=rel_dir):
                src = os.path.join(REPO_ROOT, rel_dir)
                path_resolution = os.path.join(src, "path_resolution.py")
                self.assertTrue(
                    os.path.isfile(path_resolution),
                    f"{rel_dir} has no local path_resolution.py -- it will "
                    f"ModuleNotFoundError on a real marketplace install, which "
                    f"never bundles the monorepo's shared/ directory.",
                )

    def test_each_plugin_hooks_dir_is_importable_in_isolation(self):
        """Copy each plugin's hooks/ dir alone to a tmp dir with no sibling shared/,
        and confirm path_resolution.py still imports -- the exact scenario a real
        fresh install produces."""
        for rel_dir in PLUGIN_HOOKS_DIRS:
            with self.subTest(plugin=rel_dir):
                src = os.path.join(REPO_ROOT, rel_dir)
                with tempfile.TemporaryDirectory() as tmp:
                    isolated_hooks = os.path.join(tmp, "hooks")
                    shutil.copytree(
                        src, isolated_hooks,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                    )
                    result = subprocess.run(
                        [sys.executable, "-c", "import path_resolution"],
                        cwd=isolated_hooks,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        f"{rel_dir}'s path_resolution.py failed to import in "
                        f"isolation (no shared/ present): {result.stderr}",
                    )


if __name__ == "__main__":
    unittest.main()
