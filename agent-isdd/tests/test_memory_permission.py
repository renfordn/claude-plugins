"""Tests for hooks/memory_permission.py.

Ported from the live verification run during the Global Cross-Project Memory Tier feature
(2026-07-30, Phase 2).
"""
import os
import unittest

import hook_test_utils as h


class MemoryPermissionTests(unittest.TestCase):
    def test_allows_write_under_spec_dir(self):
        """Regression guard: per-feature spec/ state stays auto-approved."""
        with h.temp_home() as home:
            cwd = "/some/project/path"
            slug = h.project_slug_for(cwd)
            path = os.path.join(
                home, ".claude", "sdd-memory", slug, "spec", "2020-01-01-feature",
                "workflow-state.md",
            )
            decision, rc = h.run_hook(
                "memory_permission.py",
                {"tool_input": {"file_path": path}, "cwd": cwd},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "allow")

    def test_does_not_allow_central_project_memory_file(self):
        """Phase 3: central memory files are no longer sdd's domain to auto-approve."""
        with h.temp_home() as home:
            cwd = "/some/project/path"
            slug = h.project_slug_for(cwd)
            path = os.path.join(home, ".claude", "sdd-memory", slug, "PROJECT-MEMORY.md")
            decision, rc = h.run_hook(
                "memory_permission.py",
                {"tool_input": {"file_path": path}, "cwd": cwd},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_does_not_allow_global_dir(self):
        """Phase 3: the global/ tier is no longer sdd's domain to auto-approve."""
        with h.temp_home() as home:
            cwd = "/some/project/path"
            path = os.path.join(home, ".claude", "sdd-memory", "global", "GLOBAL-MEMORY.md")
            decision, rc = h.run_hook(
                "memory_permission.py",
                {"tool_input": {"file_path": path}, "cwd": cwd},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_unrelated_path_is_noop(self):
        with h.temp_home() as home:
            cwd = "/some/project/path"
            decision, rc = h.run_hook(
                "memory_permission.py",
                {"tool_input": {"file_path": f"{cwd}/hooks/gate_check.py"}, "cwd": cwd},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
