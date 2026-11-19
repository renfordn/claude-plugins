"""Tests for hooks/stop_check.py.

New test design (no prior ad-hoc coverage this session). Never blocks; writes a best-effort
last-stop.json marker whenever a state file exists, and additionally prints a reminder only
when workflow status looks blocked/awaiting/needs-confirm.
"""
import json
import os
import subprocess
import time
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

    def _stop(self, home, repo, **extra):
        payload = dict({"cwd": repo, "hook_event_name": "Stop"}, **extra)
        r = subprocess.run(["python3", os.path.join(h.HOOKS_DIR, "stop_check.py")],
                           input=json.dumps(payload), capture_output=True, text=True,
                           env=h._hook_env({"HOME": home}), timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else {}

    def _seed_approved_requirements(self, feature_dir):
        h.seed_feature_artifact(feature_dir, "requirements/requirements.md", "# Req\n\n- State: Approved\n")

    def _seed_high_risk_tasks(self, feature_dir):
        h.seed_feature_artifact(
            feature_dir, "tasks/tasks.md",
            "# Tasks\n\n## Slice 1: x\n\n**Risk Tier:** high-risk\n")

    def test_requirements_approved_with_no_design_blocks_as_a_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Requirements",
                              workflow_status="In Progress")
            self._seed_approved_requirements(fd)
            out = self._stop(home, repo)
            self.assertEqual(out.get("decision"), "block")
            self.assertIn("stalled", out["reason"].lower())
            self.assertIn("Design", out["reason"])

    def test_stall_does_not_block_when_stop_hook_active(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Requirements",
                              workflow_status="In Progress")
            self._seed_approved_requirements(fd)
            self.assertIsNone(self._stop(home, repo, stop_hook_active=True).get("decision"))

    def test_design_approved_with_no_tasks_file_is_not_a_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Design",
                              workflow_status="In Progress")
            self._seed_approved_design(fd)
            self.assertEqual(self._stop(home, repo), {})

    def test_complete_with_unreviewed_high_risk_slice_blocks(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Implementation",
                              workflow_status="Complete")
            self._seed_high_risk_tasks(fd)
            out = self._stop(home, repo)
            self.assertEqual(out.get("decision"), "block")
            self.assertIn("1", out["reason"])
            self.assertIn("review", out["reason"].lower())
            self.assertIsNone(self._stop(home, repo, stop_hook_active=True).get("decision"))

    def test_backstop_blocks_once_per_change_and_rearms(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Implementation",
                              workflow_status="Complete")
            self._seed_high_risk_tasks(fd)
            self.assertEqual(self._stop(home, repo).get("decision"), "block")
            self.assertEqual(self._stop(home, repo), {})
            h.seed_feature_artifact(
                fd, "tasks/tasks.md",
                "# Tasks\n\n## Slice 1: x\n\n**Risk Tier:** high-risk\n\n"
                "## Slice 2: y\n\n**Risk Tier:** high-risk\n")
            self.assertEqual(self._stop(home, repo).get("decision"), "block")

    def test_stall_blocks_once_per_change_and_rearms(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            state = h.seed_state_file(fd, title="My Feature", current_phase="Requirements",
                                      workflow_status="In Progress")
            self._seed_approved_requirements(fd)
            self.assertEqual(self._stop(home, repo).get("decision"), "block")
            self.assertEqual(self._stop(home, repo), {})
            h.seed_state_file(fd, title="My Feature", current_phase="Requirements",
                              workflow_status="In Progress Again")
            self.assertEqual(self._stop(home, repo).get("decision"), "block")

    def test_aged_complete_feature_is_ignored(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            state = h.seed_state_file(fd, title="Old", current_phase="Implementation",
                                      workflow_status="Complete")
            self._seed_high_risk_tasks(fd)
            old = time.time() - 3 * 86400
            os.utime(state, (old, old))
            self.assertEqual(self._stop(home, repo), {})

    def test_every_recent_complete_feature_is_listed(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            for slug, title in (("2020-01-01-a", "Alpha"), ("2020-01-02-b", "Beta")):
                fd = h.feature_spec_dir(home, repo, slug)
                h.seed_state_file(fd, title=title, current_phase="Implementation",
                                  workflow_status="Complete")
                self._seed_high_risk_tasks(fd)
            reason = self._stop(home, repo)["reason"]
            self.assertIn("Alpha", reason)
            self.assertIn("Beta", reason)

    def test_paused_active_feature_still_gets_backstop_block(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="Paused One", current_phase="Design",
                              workflow_status="Blocked", pause_reason="waiting", next_action="ask")
            done = h.feature_spec_dir(home, repo, "2020-01-02-done-feature")
            h.seed_state_file(done, title="Done Feature", current_phase="Implementation",
                              workflow_status="Complete")
            self._seed_high_risk_tasks(done)
            out = self._stop(home, repo)
            self.assertEqual(out.get("decision"), "block")
            self.assertIn("Done Feature", out["reason"])
            out2 = self._stop(home, repo)
            self.assertIn("paused", out2.get("systemMessage", ""))

    def test_complete_with_review_fallback_does_not_block(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Implementation",
                              workflow_status="Complete",
                              review_fallback="Accepted via AskUserQuestion: all: no reviewer")
            self._seed_high_risk_tasks(fd)
            self.assertEqual(self._stop(home, repo), {})

    def test_backstop_and_stall_merge_into_one_block(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd = h.feature_spec_dir(home, repo)
            h.seed_state_file(fd, title="My Feature", current_phase="Requirements",
                              workflow_status="In Progress")
            self._seed_approved_requirements(fd)
            done = h.feature_spec_dir(home, repo, "2020-01-02-done-feature")
            h.seed_state_file(done, title="Done Feature", current_phase="Implementation",
                              workflow_status="Complete")
            self._seed_high_risk_tasks(done)
            r = subprocess.run(["python3", os.path.join(h.HOOKS_DIR, "stop_check.py")],
                               input=json.dumps({"cwd": repo}), capture_output=True, text=True,
                               env=h._hook_env({"HOME": home}), timeout=10)
            self.assertEqual(len(r.stdout.strip().splitlines()), 1)
            reason = json.loads(r.stdout)["reason"]
            self.assertIn("stalled", reason.lower())
            self.assertIn("review", reason.lower())

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
