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
        self.assertIn("mark_chapter", msg)

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

    def test_hook_history_is_capped(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            old = [{"hook": "old", "i": i} for i in range(150)]
            feature_dir, md_path, json_path = self._seed(
                home, repo,
                {"current_phase": "Design", "workflow_status": "In Progress"},
                {"current_phase": "Tasks", "phase_state": "In Progress", "hook_history": old},
            )
            h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": md_path}, "cwd": repo},
                env_extra={"HOME": home},
            )
            with open(json_path) as fh:
                history = json.load(fh)["hook_history"]
            self.assertEqual(len(history), 100)
            self.assertEqual(history[-1]["hook"], "post_write_check/state_sync")
            self.assertEqual(history[0]["i"], 51)

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


WATCHED_RELPATHS = (
    "workflow-state.md",
    "requirements/requirements.md",
    "design/design.md",
    "tasks/tasks.md",
    "recap/recap.md",
    "direct-mode-state.json",
)


class PostWriteCheckPlanBoardTests(unittest.TestCase):
    """Slice 10: all five state files reach the Plan Board path; everything else exits fast."""

    def _feature(self, root):
        memory_dir = os.path.join(root, "sdd-memory", "proj")
        feature_dir = os.path.join(memory_dir, "spec", "2020-01-01-test-feature")
        h.seed_state_file(feature_dir, current_phase="Design", workflow_status="In Progress")
        h.seed_plan_board_url(memory_dir)
        return memory_dir, feature_dir

    def test_each_watched_file_reaches_plan_board_path(self):
        for rel in WATCHED_RELPATHS:
            with self.subTest(path=rel), h.temp_home() as root:
                _memory_dir, feature_dir = self._feature(root)
                path = h.seed_feature_artifact(feature_dir, rel) \
                    if rel != "workflow-state.md" else os.path.join(feature_dir, rel)
                msg, rc = h.run_hook_message(
                    "post_write_check.py",
                    {"tool_input": {"file_path": path}, "cwd": root},
                    env_extra={"HOME": root},
                )
                self.assertEqual(rc, 0)
                self.assertIsNotNone(msg)
                self.assertIn("Plan Board", msg)

    def test_direct_mode_state_gets_only_the_plan_board_reminder(self):
        with h.temp_home() as root:
            _memory_dir, feature_dir = self._feature(root)
            path = h.seed_feature_artifact(feature_dir, "tasks/tasks.md")
            h.seed_feature_artifact(feature_dir, "direct-mode-state.json")
            msg, rc = h.run_hook_message(
                "post_write_check.py",
                {"tool_input": {"file_path": os.path.join(feature_dir, "direct-mode-state.json")}, "cwd": root},
                env_extra={"HOME": root},
            )
            self.assertEqual(rc, 0)
            self.assertIn("Plan Board", msg)
            self.assertNotIn("mark_chapter", msg)

    def test_direct_mode_state_is_silent_without_a_plan_board(self):
        msg, rc = h.run_hook_message(
            "post_write_check.py",
            {"tool_input": {"file_path": "/some/feature/direct-mode-state.json"}},
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_unwatched_paths_in_feature_dir_are_silent(self):
        for rel in ("notes.md", "requirements/requirements.md.bak", "research/findings.md"):
            with self.subTest(path=rel), h.temp_home() as root:
                _memory_dir, feature_dir = self._feature(root)
                path = h.seed_feature_artifact(feature_dir, rel)
                msg, rc = h.run_hook_message(
                    "post_write_check.py",
                    {"tool_input": {"file_path": path}, "cwd": root},
                    env_extra={"HOME": root},
                )
                self.assertEqual(rc, 0)
                self.assertIsNone(msg)

    def test_existing_reminders_unchanged_without_plan_board_url(self):
        for rel in ("workflow-state.md", "tasks/tasks.md"):
            with self.subTest(path=rel):
                msg, rc = h.run_hook_message(
                    "post_write_check.py",
                    {"tool_input": {"file_path": f"/some/feature/{rel}"}},
                )
                self.assertEqual(rc, 0)
                self.assertIn("mark_chapter", msg)

    def test_unwatched_path_exits_before_any_file_read_or_plan_board_work(self):
        import builtins
        import io
        import sys
        from unittest import mock

        sys.path.insert(0, os.path.join(h.REPO_ROOT, "hooks"))
        try:
            import plan_board
            import post_write_check
        finally:
            sys.path.pop(0)

        def boom(*a, **k):
            raise AssertionError("heavy work on an unwatched path")

        payload = json.dumps({"tool_input": {"file_path": "/x/spec/f/src/app.py"}, "cwd": "/x"})
        with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
             mock.patch.object(builtins, "open", boom), \
             mock.patch.object(os.path, "isfile", boom), \
             mock.patch.object(plan_board, "build_doc", boom), \
             mock.patch.object(plan_board, "stale_features", boom), \
             mock.patch.object(plan_board, "board_url", boom), \
             mock.patch.object(plan_board, "memory_dir_for_state", boom):
            with self.assertRaises(SystemExit) as cm:
                post_write_check.main()
        self.assertEqual(cm.exception.code, 0)


class PostWriteCheckPlanBoardSyncTests(unittest.TestCase):
    """Slice 11: a watched write emits ONE merged message carrying the Plan Board sync reminder
    when the rebuilt record differs from the synced hash; silent otherwise. No process forks."""

    def _feature(self, root):
        memory_dir = os.path.join(root, "sdd-memory", "proj")
        feature_dir = os.path.join(memory_dir, "spec", "2020-01-01-test-feature")
        h.seed_state_file(feature_dir, current_phase="Design", workflow_status="In Progress")
        h.seed_plan_board_url(memory_dir)
        return memory_dir, feature_dir

    def _run(self, root, path):
        """Run main() in-process with subprocess.run/Popen raising; returns (stdout, exit code, seconds)."""
        import io
        import subprocess
        import sys
        import time
        from unittest import mock

        sys.path.insert(0, os.path.join(h.REPO_ROOT, "hooks"))
        try:
            import post_write_check
        finally:
            sys.path.pop(0)

        def no_fork(*a, **k):
            raise AssertionError("subprocess used on the PostToolUse hot path")

        payload = json.dumps({"tool_input": {"file_path": path}, "cwd": root})
        out = io.StringIO()
        start = time.monotonic()
        with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
             mock.patch.object(sys, "stdout", out), \
             mock.patch.object(subprocess, "run", no_fork), \
             mock.patch.object(subprocess, "Popen", no_fork):
            with self.assertRaises(SystemExit) as cm:
                post_write_check.main()
        return out.getvalue().strip(), cm.exception.code, time.monotonic() - start

    def _message(self, root, path):
        out, rc, _elapsed = self._run(root, path)
        self.assertEqual(rc, 0)
        self.assertTrue(out, "expected a systemMessage")
        return json.loads(out)["systemMessage"]  # whole stdout must be ONE JSON document

    def _temp_record(self, msg):
        import re
        m = re.search(r"(/\S+\.json)\b", msg)
        self.assertIsNotNone(m, "message must contain the temp file path")
        with open(m.group(1), "r", encoding="utf-8") as fh:
            return m.group(1), json.load(fh)

    def test_changed_record_emits_one_merged_message(self):
        with h.temp_home() as root:
            _memory_dir, feature_dir = self._feature(root)
            msg = self._message(root, os.path.join(feature_dir, "workflow-state.md"))
            self.assertIn("mark_chapter", msg)
            self.assertIn("Plan Board", msg)
            _path, doc = self._temp_record(msg)
            self.assertIn(doc["id"], msg)
            self.assertEqual(doc["slug"], "2020-01-01-test-feature")
            for needle in ("ArtifactData", "get", "set", "if_version", "mark-synced",
                           "never block"):
                self.assertIn(needle, msg)
            self.assertLess(msg.index("ArtifactData"), msg.index("if_version"))
            self.assertLess(msg.index("if_version"), msg.index("mark-synced"))
            low = msg.lower()
            self.assertIn("recap", low)
            self.assertIn("fail", low)

    def test_unchanged_hash_is_silent_about_plan_board(self):
        import sys
        sys.path.insert(0, os.path.join(h.REPO_ROOT, "hooks"))
        try:
            import plan_board as pb
        finally:
            sys.path.pop(0)
        with h.temp_home() as root:
            memory_dir, feature_dir = self._feature(root)
            state = os.path.join(feature_dir, "workflow-state.md")
            _p, doc = self._temp_record(self._message(root, state))
            pb.mark_synced(memory_dir, doc)
            msg = self._message(root, state)
            self.assertIn("mark_chapter", msg)
            self.assertNotIn("Plan Board", msg)
            self.assertNotIn("mark-synced", msg)

    def test_no_plan_board_file_is_silent(self):
        with h.temp_home() as root:
            memory_dir, feature_dir = self._feature(root)
            os.remove(os.path.join(memory_dir, "PLAN-BOARD.md"))
            msg = self._message(root, os.path.join(feature_dir, "workflow-state.md"))
            self.assertNotIn("Plan Board", msg)
            self.assertNotIn("mark-synced", msg)

    def test_non_https_url_is_silent(self):
        with h.temp_home() as root:
            memory_dir, feature_dir = self._feature(root)
            h.seed_plan_board_url(memory_dir, url="http://example.invalid/plan-board")
            msg = self._message(root, os.path.join(feature_dir, "workflow-state.md"))
            self.assertNotIn("Plan Board", msg)
            self.assertNotIn("mark-synced", msg)

    def test_sync_off_is_silent(self):
        with h.temp_home() as root:
            memory_dir, feature_dir = self._feature(root)
            with open(os.path.join(memory_dir, "PLAN-BOARD.md"), "a", encoding="utf-8") as fh:
                fh.write("- Sync: off\n")
            msg = self._message(root, os.path.join(feature_dir, "workflow-state.md"))
            self.assertNotIn("Plan Board", msg)
            self.assertNotIn("mark-synced", msg)

    def test_latency_is_loosely_bounded(self):
        with h.temp_home() as root:
            _memory_dir, feature_dir = self._feature(root)
            _out, _rc, elapsed = self._run(root, os.path.join(feature_dir, "workflow-state.md"))
            self.assertLess(elapsed, 2.0)


class PostWriteCheckTempFileTests(unittest.TestCase):
    """Refactor F5: the record temp file name is deterministic per record id (overwritten, not piled up)."""
    _feature = PostWriteCheckPlanBoardSyncTests._feature
    _run = PostWriteCheckPlanBoardSyncTests._run
    _message = PostWriteCheckPlanBoardSyncTests._message
    _temp_record = PostWriteCheckPlanBoardSyncTests._temp_record

    def test_same_record_reuses_one_temp_path_and_overwrites_it(self):
        with h.temp_home() as root:
            _memory_dir, feature_dir = self._feature(root)
            state = os.path.join(feature_dir, "workflow-state.md")
            first_path, first = self._temp_record(self._message(root, state))
            h.seed_state_file(feature_dir, current_phase="Design", workflow_status="Paused")
            second_path, second = self._temp_record(self._message(root, state))
            self.assertEqual(first_path, second_path)
            self.assertTrue(os.path.isabs(second_path) and second_path.endswith(".json"))
            self.assertNotRegex(second_path, r"\s")
            self.assertIn(first["id"], os.path.basename(second_path))
            self.assertEqual(second["status"], "Paused")


if __name__ == "__main__":
    unittest.main()
