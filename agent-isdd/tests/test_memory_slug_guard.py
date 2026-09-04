"""Tests for hooks/memory_slug_guard.py.

Originally ported from the live verification run during the Doc Consistency Auditor feature
(2026-07-31), which itself replayed the real memory-orchestrator slug-computation incident from
earlier that session. Rewritten to use temp_home()-derived paths (2026-08-09) after the first
real CI run caught the original hardcoded-/Users/jay.nelson/-paths version: it only worked by
accident on a machine where HOME happened to match, and silently passed for the wrong reason on
GitHub's runner (HOME=/home/runner) instead of actually exercising the slug-matching logic.
"""
import os
import unittest

import hook_test_utils as h

CWD = "/some/project/path"  # arbitrary — project_slug(cwd) is a pure string transform of this


class MemorySlugGuardTests(unittest.TestCase):
    def test_wrong_slug_is_denied(self):
        with h.temp_home() as home:
            correct_slug = h.project_slug_for(CWD)
            wrong_path = os.path.join(
                home, ".claude", "sdd-memory", correct_slug + "-WRONG", "PROJECT-MEMORY.md"
            )
            decision, rc = h.run_hook(
                "memory_slug_guard.py",
                {"tool_input": {"file_path": wrong_path}, "cwd": CWD},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn(correct_slug, decision["permissionDecisionReason"])

    def test_correct_slug_is_noop(self):
        with h.temp_home() as home:
            correct_slug = h.project_slug_for(CWD)
            path = os.path.join(home, ".claude", "sdd-memory", correct_slug, "PROJECT-MEMORY.md")
            decision, rc = h.run_hook(
                "memory_slug_guard.py",
                {"tool_input": {"file_path": path}, "cwd": CWD},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_global_dir_is_noop(self):
        with h.temp_home() as home:
            path = os.path.join(home, ".claude", "sdd-memory", "global", "GLOBAL-MEMORY.md")
            decision, rc = h.run_hook(
                "memory_slug_guard.py",
                {"tool_input": {"file_path": path}, "cwd": CWD},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_unrelated_path_is_noop(self):
        with h.temp_home() as home:
            decision, rc = h.run_hook(
                "memory_slug_guard.py",
                {"tool_input": {"file_path": f"{h.REPO_ROOT}/hooks/gate_check.py"}, "cwd": CWD},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_sdd_gate_off_bypasses(self):
        with h.temp_home() as home:
            correct_slug = h.project_slug_for(CWD)
            wrong_path = os.path.join(
                home, ".claude", "sdd-memory", correct_slug + "-WRONG", "PROJECT-MEMORY.md"
            )
            decision, rc = h.run_hook(
                "memory_slug_guard.py",
                {"tool_input": {"file_path": wrong_path}, "cwd": CWD},
                env_extra={"HOME": home, "SDD_GATE": "off"},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
