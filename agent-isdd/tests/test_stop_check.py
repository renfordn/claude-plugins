"""Tests for hooks/stop_check.py.

New test design (no prior ad-hoc coverage this session). Never blocks; writes a best-effort
last-stop.json marker whenever a state file exists, and additionally prints a reminder only
when workflow status looks blocked/awaiting/needs-confirm.
"""
import os
import unittest

import hook_test_utils as h


class StopCheckTests(unittest.TestCase):
    def _marker_path(self, home, cwd):
        slug = h.project_slug_for(cwd)
        return os.path.join(home, ".claude", "plugins", "data", "agent-isdd", "sdd-memory", slug, "last-stop.json")

    def test_no_active_state_is_silent_and_writes_nothing(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            self.assertFalse(os.path.exists(self._marker_path(home, repo)))

    def test_blocked_status_prints_reminder_and_writes_marker(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                workflow_status="Blocked",
                pause_reason="waiting on user",
                next_action="answer the question",
            )
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("My Feature", msg)
            self.assertIn("waiting on user", msg)
            self.assertTrue(os.path.exists(self._marker_path(home, repo)))

    def test_awaiting_confirmation_status_prints_reminder(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                workflow_status="Awaiting Confirmation",
            )
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)

    def test_normal_in_progress_status_writes_marker_but_no_reminder(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                workflow_status="In Progress",
            )
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            self.assertTrue(os.path.exists(self._marker_path(home, repo)))

    def _seed_approved_design(self, feature_dir):
        design_dir = os.path.join(feature_dir, "design")
        os.makedirs(design_dir, exist_ok=True)
        with open(os.path.join(design_dir, "design.md"), "w", encoding="utf-8") as fh:
            fh.write("# Design\n\n- State: Approved\n")

    def test_design_approved_with_no_tasks_file_is_a_real_stall(self):
        """Reproduces the actual production stall: the orchestrator provided guidance at
        the Design->Tasks boundary and ended its turn. Workflow Status stays 'In Progress'
        here (per workflow-manager's own contract, 'Complete' is reserved for final
        handoff/completion, never for an individual phase) -- design.md's own
        `State: Approved` is the real per-phase completion signal."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            self._seed_approved_design(feature_dir)
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg, "expected a stall reminder, got none")
            self.assertIn("stalled", msg.lower())
            self.assertIn("Tasks", msg)

    def test_design_approved_with_tasks_file_present_is_not_a_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            self._seed_approved_design(feature_dir)
            tasks_dir = os.path.join(feature_dir, "tasks")
            os.makedirs(tasks_dir, exist_ok=True)
            with open(os.path.join(tasks_dir, "tasks.md"), "w", encoding="utf-8") as fh:
                fh.write("# Tasks\n")
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

    def test_design_still_draft_is_not_a_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            design_dir = os.path.join(feature_dir, "design")
            os.makedirs(design_dir, exist_ok=True)
            with open(os.path.join(design_dir, "design.md"), "w", encoding="utf-8") as fh:
                fh.write("# Design\n\n- State: Draft\n")
            msg, rc = h.run_hook_message(
                "stop_check.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
