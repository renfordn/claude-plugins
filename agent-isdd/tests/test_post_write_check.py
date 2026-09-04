"""Tests for hooks/post_write_check.py.

Merges the coverage that used to live in tests/test_phase_task_sync.py and
tests/test_state_consistency_check.py, whose targets (hooks/phase_task_sync.py and
hooks/state_consistency_check.py) were folded into this hook (see CHANGELOG.md) and
then deleted -- they were no longer registered in hooks/hooks.json, so those test
files were exercising dead code.
"""
import json
import os
import unittest

import hook_test_utils as h


class PostWriteCheckReminderTests(unittest.TestCase):
    """Coverage for the systemMessage reminder, formerly phase_task_sync.py's job."""

    def test_workflow_state_md_triggers_reminder(self):
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "/some/feature/workflow-state.md"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNotNone(msg)
        self.assertIn("agent-ux:ux-agent", msg)

    def test_tasks_tasks_md_triggers_reminder(self):
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "/some/feature/tasks/tasks.md"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNotNone(msg)

    def test_non_matching_path_is_silent(self):
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "/some/feature/requirements/requirements.md"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_backslash_path_still_matches(self):
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "C:\\some\\feature\\workflow-state.md"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNotNone(msg)

    def test_missing_tool_input_is_silent(self):
        msg, rc = h.run_hook_message("post_write_check.py", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_malformed_json_does_not_crash(self):
        import subprocess
        result = subprocess.run(
            ["python3", "hooks/post_write_check.py"],
            input="not json{{{",
            capture_output=True,
            text=True,
            cwd=h.REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_sanity_a_path_using_the_watched_suffix_as_a_substring_not_suffix_does_not_match(self):
        # e.g. "workflow-state.md.bak" must NOT match -- endswith, not "contains".
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "/some/feature/workflow-state.md.bak"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)


class PostWriteCheckJsonSyncTests(unittest.TestCase):
    """Coverage for the workflow-state.json sync, formerly state_consistency_check.py's job.

    The sync is silent (no systemMessage on its own), so these tests read
    workflow-state.json directly rather than asserting on the hook's stdout.
    """

    def _seed(self, home, repo, md_fields, json_fields):
        feature_dir = h.feature_spec_dir(home, repo)
        md_path = h.seed_state_file(feature_dir, **md_fields)
        json_path = os.path.join(feature_dir, "workflow-state.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_fields, fh)
        return feature_dir, md_path, json_path

    def test_consistent_state_is_noop(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir, md_path, json_path = self._seed(
                home, repo,
                {"current_phase": "Tasks", "workflow_status": "In Progress"},
                {"current_phase": "Tasks", "phase_state": "In Progress"},
            )
            with open(json_path) as fh:
                before = fh.read()
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}, "cwd": repo},
                env_extra={"HOME": home},
            )
            with open(json_path) as fh:
                self.assertEqual(fh.read(), before)

    def test_drift_is_synced_toward_md_silently(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir, md_path, json_path = self._seed(
                home, repo,
                {"current_phase": "Design", "workflow_status": "In Progress"},
                {"current_phase": "Tasks", "phase_state": "In Progress"},
            )
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}, "cwd": repo},
                env_extra={"HOME": home},
            )

            with open(json_path) as fh:
                synced = json.load(fh)
            self.assertEqual(synced["current_phase"], "Design")
            self.assertIn("hook_history", synced)
            last = synced["hook_history"][-1]
            self.assertEqual(last["hook"], "post_write_check/state_sync")
            self.assertEqual(last["outcome"], "Synced")
            self.assertIn("current_phase", last.get("fields", []))

            # No recap.md written — routine operation does not need a model reminder.
            recap_path = os.path.join(feature_dir, "recap", "recap.md")
            self.assertFalse(os.path.isfile(recap_path))

    def test_missing_json_sibling_is_noop_no_crash(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            md_path = h.seed_state_file(feature_dir, current_phase="Design")
            msg, rc = h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)  # still fires the UI reminder even with no JSON sibling

    def test_missing_md_file_is_noop_no_crash(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            msg, rc = h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": os.path.join(home, "workflow-state.md")}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)


class PostWriteCheckRootStateTests(unittest.TestCase):
    """Coverage for the additive .sdd-state.json dual-write at the project root."""

    def test_root_state_written_alongside_memory_dir_json(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            md_path = h.seed_state_file(
                feature_dir, current_phase="Design", workflow_status="In Progress"
            )
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}, "cwd": repo},
                env_extra={"HOME": home},
            )

            root_path = os.path.join(repo, ".sdd-state.json")
            self.assertTrue(os.path.isfile(root_path))
            with open(root_path) as fh:
                root_state = json.load(fh)
            self.assertEqual(root_state["current_phase"], "Design")
            self.assertEqual(root_state["phase_state"], "In Progress")
            self.assertIn("last_updated", root_state)

            # existing memory-dir workflow-state.json write is untouched by this addition
            memory_json_path = os.path.join(feature_dir, "workflow-state.json")
            self.assertFalse(os.path.isfile(memory_json_path))

    def test_root_state_skipped_without_cwd(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            md_path = h.seed_state_file(feature_dir, current_phase="Design")
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}},
                env_extra={"HOME": home},
            )
            self.assertFalse(os.path.isfile(os.path.join(repo, ".sdd-state.json")))

    def test_root_state_not_written_for_tasks_md(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": "/some/feature/tasks/tasks.md"}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertFalse(os.path.isfile(os.path.join(repo, ".sdd-state.json")))


if __name__ == "__main__":
    unittest.main()
