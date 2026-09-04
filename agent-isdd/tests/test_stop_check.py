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
        return os.path.join(home, ".claude", "sdd-memory", slug, "last-stop.json")

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


if __name__ == "__main__":
    unittest.main()
