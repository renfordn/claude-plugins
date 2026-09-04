"""Tests for hooks/session_start.py.

Ported from the live verification run during the Agent Responsibility Cleanup (Phase 1
integration proof) and Global Cross-Project Memory Tier (Phase 5) features.

Phase 3 of the Decouple Memory feature removed the PROJECT-MEMORY.md/GLOBAL-MEMORY.md
announcement block -- those central-memory files, and memory-orchestrator that owned them,
no longer exist; agent-nelly owns cross-feature memory now. This hook only announces
per-feature spec state and any active workflow.
"""
import os
import unittest

import hook_test_utils as h


class SessionStartTests(unittest.TestCase):
    def test_does_not_surface_project_memory_file(self):
        """Phase 3: PROJECT-MEMORY.md is no longer read/announced by this hook."""
        with h.temp_home() as home:
            cwd = "/tmp"
            slug = h.project_slug_for(cwd)
            mem_dir = os.path.join(home, ".claude", "sdd-memory", slug)
            os.makedirs(mem_dir)
            with open(os.path.join(mem_dir, "PROJECT-MEMORY.md"), "w") as fh:
                fh.write("## Goal\n\n- test-feature: some goal text\n")

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("some goal text", ctx)

    def test_does_not_surface_global_memory_file(self):
        """Phase 3: GLOBAL-MEMORY.md is no longer read/announced by this hook."""
        with h.temp_home() as home:
            cwd = "/tmp"
            global_dir = os.path.join(home, ".claude", "sdd-memory", "global")
            os.makedirs(global_dir)
            with open(os.path.join(global_dir, "GLOBAL-MEMORY.md"), "w") as fh:
                fh.write(
                    "---\n"
                    "name: some-fact\n"
                    "description: a short description\n"
                    "metadata:\n  type: feedback\n"
                    "---\n\n"
                    "This is the FULL BODY that should never appear in session_start output.\n"
                )

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("some-fact", ctx)
            self.assertNotIn("FULL BODY", ctx)

    def test_surfaces_active_workflow_banner(self):
        with h.temp_home() as home:
            cwd = "/tmp"
            feature_dir = h.feature_spec_dir(home, cwd)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
                next_action="Do the thing",
            )

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertIn("My Feature", ctx)
            self.assertIn("Design", ctx)

    def test_silent_sections_when_nothing_to_report(self):
        with h.temp_home() as home:
            decision, rc = h.run_hook(
                "session_start.py", {"cwd": "/tmp"}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("Active spec-driven-development workflow", ctx)


if __name__ == "__main__":
    unittest.main()
