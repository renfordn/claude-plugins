"""Tests for hooks/sdd_state.py.

Ported from the live verification run during the Agent Responsibility Cleanup feature
(2026-07-30, Phase 1) -- the regression this feature's Phase 1 fixed: find_state_files/
active_state_file must resolve under memory_dir(root)/spec/*/, not the stale root/spec/*/.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import hook_test_utils as h


class SddStateTests(unittest.TestCase):
    def test_active_state_file_resolves_under_memory_dir_not_root(self):
        with h.temp_home() as home:
            import tempfile
            with tempfile.TemporaryDirectory() as project_root:
                # OLD, wrong location: <root>/spec/<slug>/workflow-state.md
                old_wrong = os.path.join(project_root, "spec", "old-wrong-location", "workflow-state.md")
                os.makedirs(os.path.dirname(old_wrong))
                with open(old_wrong, "w") as fh:
                    fh.write("- Title: Wrong\n")

                # CORRECT location: <memory_dir(root)>/spec/<slug>/workflow-state.md
                correct_dir = h.feature_spec_dir(home, project_root, "correct-location")
                correct_path = os.path.join(correct_dir, "workflow-state.md")
                with open(correct_path, "w") as fh:
                    fh.write("- Title: Correct\n")

                env = dict(os.environ)
                env["HOME"] = home
                import subprocess
                result = subprocess.run(
                    ["python3", "-c",
                     f"import sys; sys.path.insert(0, {h.HOOKS_DIR!r}); "
                     f"import sdd_state; print(sdd_state.active_state_file({project_root!r}))"],
                    capture_output=True, text=True, env=env,
                )
                self.assertIn(correct_path, result.stdout)
                self.assertNotIn(old_wrong, result.stdout)

    def test_parse_state_extracts_dash_fields(self):
        with h.temp_home() as home:
            import tempfile
            with tempfile.TemporaryDirectory() as project_root:
                feature_dir = h.feature_spec_dir(home, project_root)
                path = h.seed_state_file(
                    feature_dir,
                    title="My Feature",
                    current_phase="Design",
                    workflow_status="In Progress",
                    implementation_requested="No",
                )
                env = dict(os.environ)
                env["HOME"] = home
                import subprocess
                result = subprocess.run(
                    ["python3", "-c",
                     f"import sys; sys.path.insert(0, {h.HOOKS_DIR!r}); "
                     f"import sdd_state, json; print(json.dumps(sdd_state.parse_state({path!r})))"],
                    capture_output=True, text=True, env=env,
                )
                import json
                fields = json.loads(result.stdout)
                self.assertEqual(fields.get("title"), "My Feature")
                self.assertEqual(fields.get("current phase"), "Design")
                self.assertEqual(fields.get("implementation requested"), "No")

    def test_is_pre_implementation_true_when_not_requested(self):
        sys.path.insert(0, h.HOOKS_DIR)
        import importlib
        sdd_state = importlib.import_module("sdd_state")
        self.assertTrue(sdd_state.is_pre_implementation({"implementation requested": "No"}))
        self.assertFalse(sdd_state.is_pre_implementation({"implementation requested": "Yes"}))
        self.assertFalse(sdd_state.is_pre_implementation({"workflow status": "Complete"}))


class ParseStateJsonTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, h.HOOKS_DIR)
        import importlib
        self.sdd_state = importlib.import_module("sdd_state")

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(self.sdd_state.parse_state_json("/nonexistent/workflow-state.json"), {})

    def test_malformed_json_returns_empty_dict(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not valid json")
            self.assertEqual(self.sdd_state.parse_state_json(path), {})

    def test_valid_json_parses(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Tasks"}, fh)
            fields = self.sdd_state.parse_state_json(path)
            self.assertEqual(fields.get("current_phase"), "Tasks")


class RollbackPendingTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, h.HOOKS_DIR)
        import importlib
        self.sdd_state = importlib.import_module("sdd_state")

    def _write_json(self, path, data):
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_read_returns_none_when_no_field(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Tasks"})
            self.assertIsNone(self.sdd_state.read_rollback_pending(path))

    def test_write_then_read_round_trip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Tasks"})
            self.sdd_state.write_rollback_pending(path, "Design", "task was wrong", "agent-tdd")
            pending = self.sdd_state.read_rollback_pending(path)
            self.assertEqual(pending.get("target"), "Design")
            self.assertEqual(pending.get("reason"), "task was wrong")
            self.assertEqual(pending.get("source"), "agent-tdd")
            # other fields preserved
            fields = self.sdd_state.parse_state_json(path)
            self.assertEqual(fields.get("current_phase"), "Tasks")

    def test_clear_removes_field(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Tasks"})
            self.sdd_state.write_rollback_pending(path, "Design", "reason", "agent-tdd")
            self.sdd_state.clear_rollback_pending(path)
            self.assertIsNone(self.sdd_state.read_rollback_pending(path))

    def test_write_creates_file_if_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self.sdd_state.write_rollback_pending(path, "Requirements", "reason", "code-reviewer")
            pending = self.sdd_state.read_rollback_pending(path)
            self.assertEqual(pending.get("target"), "Requirements")

    def test_clear_is_noop_when_file_missing(self):
        # must not raise
        self.sdd_state.clear_rollback_pending("/nonexistent/workflow-state.json")


if __name__ == "__main__":
    unittest.main()
