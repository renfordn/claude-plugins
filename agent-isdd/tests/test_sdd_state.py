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

                env = h._hook_env({"HOME": home})
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
                env = h._hook_env({"HOME": home})
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


class CompleteFeatureDiscoveryTests(unittest.TestCase):
    """find_state_files/active_state_file must skip `Workflow Status: Complete` features.

    Regression (2026-09-24): discovery picked the newest-mtime workflow-state.md regardless of
    status, so a finished feature stayed "active" forever and hooks kept writing into it.
    """

    def _run(self, home, project_root, expr):
        import subprocess
        result = subprocess.run(
            ["python3", "-c",
             f"import sys; sys.path.insert(0, {h.HOOKS_DIR!r}); "
             f"import sdd_state; print({expr})"],
            capture_output=True, text=True, env=h._hook_env({"HOME": home}),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def _seed(self, home, project_root, slug, status, mtime_offset=0):
        import time
        path = h.seed_state_file(h.feature_spec_dir(home, project_root, slug), workflow_status=status)
        t = time.time() + mtime_offset
        os.utime(path, (t, t))
        return path

    def test_all_complete_means_no_active_state(self):
        import tempfile
        with h.temp_home() as home, tempfile.TemporaryDirectory() as root:
            self._seed(home, root, "done", "Complete")
            self.assertEqual(self._run(home, root, f"sdd_state.active_state_file({root!r})"), "None")
            self.assertEqual(self._run(home, root, f"sdd_state.find_state_files({root!r})"), "[]")

    def test_newer_complete_skipped_for_older_in_progress(self):
        import tempfile
        with h.temp_home() as home, tempfile.TemporaryDirectory() as root:
            wip = self._seed(home, root, "wip", "In Progress", mtime_offset=-100)
            self._seed(home, root, "done", "Complete")
            self.assertEqual(self._run(home, root, f"sdd_state.active_state_file({root!r})"), wip)

    def test_non_complete_statuses_keep_newest_first_order(self):
        import tempfile
        with h.temp_home() as home, tempfile.TemporaryDirectory() as root:
            older = self._seed(home, root, "older", "In Progress", mtime_offset=-100)
            newer = self._seed(home, root, "newer", "Awaiting Implementation Request")
            self.assertEqual(
                self._run(home, root, f"sdd_state.find_state_files({root!r})"), repr([newer, older])
            )


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


class TestAuthorPendingTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, h.HOOKS_DIR)
        import importlib
        self.sdd_state = importlib.import_module("sdd_state")

    def _write_json(self, path, data):
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_write_then_read_round_trip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Implementation"})
            slices = [{"name": "Slice 3: Auth token refresh", "files": ["src/auth.py"]}]
            self.sdd_state.write_test_author_pending(path, slices, "2026-09-16T00:00:00")
            pending = self.sdd_state.parse_state_json(path).get("test_author_pending")
            self.assertEqual(pending["slices"], slices)
            self.assertEqual(pending["detected_at"], "2026-09-16T00:00:00")
            # other fields preserved
            self.assertEqual(
                self.sdd_state.parse_state_json(path).get("current_phase"), "Implementation"
            )

    def test_clear_removes_field(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Implementation"})
            self.sdd_state.write_test_author_pending(
                path, [{"name": "Slice 1", "files": []}], "2026-09-16T00:00:00"
            )
            self.sdd_state.clear_test_author_pending(path)
            self.assertNotIn(
                "test_author_pending", self.sdd_state.parse_state_json(path)
            )

    def test_clear_is_noop_when_file_missing(self):
        # must not raise
        self.sdd_state.clear_test_author_pending("/nonexistent/workflow-state.json")

    def test_write_creates_file_if_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self.sdd_state.write_test_author_pending(
                path, [{"name": "Slice 1", "files": []}], "2026-09-16T00:00:00"
            )
            pending = self.sdd_state.parse_state_json(path).get("test_author_pending")
            self.assertIsNotNone(pending)


class Release2ContractTests(unittest.TestCase):
    def setUp(self):
        import sdd_state
        self.s = sdd_state

    def test_simulate_write_variants(self):
        s = self.s
        self.assertEqual(s.simulate_write("Write", {"content": "new"}, "old"), "new")
        self.assertEqual(s.simulate_write("Edit", {"old_string": "a", "new_string": "b"}, "axx"), "bxx")
        self.assertEqual(s.simulate_write(
            "Edit", {"old_string": "a", "new_string": "b", "replace_all": True}, "aaa"), "bbb")
        self.assertEqual(s.simulate_write("MultiEdit", {"edits": [
            {"old_string": "a", "new_string": "b"}, {"old_string": "b", "new_string": "c"}]}, "a"), "c")

    def test_reviewed_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "workflow-state.json")
            self.assertEqual(self.s.read_reviewed(p), {})
            self.s.write_state_json(p, {"keep": 1})
            self.s.mark_reviewed(p, "2")
            self.assertEqual(self.s.read_reviewed(p), {"2": True})
            self.assertEqual(self.s.parse_state_json(p)["keep"], 1)

    def test_baseline_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "workflow-state.json")
            self.assertIsNone(self.s.read_baseline(p))
            self.s.write_baseline(p, "main", "abc", ["a.py"])
            self.assertEqual(self.s.read_baseline(p),
                             {"branch": "main", "head": "abc", "dirty_files": ["a.py"]})

    def test_bare_fields_include_release2(self):
        for f in ("risk", "risk reason", "implementation mode", "approval hash"):
            self.assertIn(f, self.s.BARE_FIELDS)

    def test_detect_stall(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for rel, state in (("requirements/requirements.md", "Approved"),
                               ("design/design.md", "Approved")):
                os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(d, "requirements/requirements.md"), "w") as fh:
                fh.write("- State: Approved\n")
            # requirements approved, design.md missing -> stalled
            self.assertTrue(self.s.detect_stall({"current phase": "Requirements"}, d))
            with open(os.path.join(d, "design/design.md"), "w") as fh:
                fh.write("- State: Approved\n")
            # design approved, no tasks.md -> NOT a stall
            self.assertFalse(self.s.detect_stall({"current phase": "Design"}, d))
            self.assertFalse(self.s.detect_stall({"current phase": "Requirements"}, d))


class Release2ReviewFixTests(unittest.TestCase):
    def setUp(self):
        import sdd_state
        self.s = sdd_state

    def test_simulate_write_edge_cases(self):
        s = self.s
        e = {"old_string": "", "new_string": "hello"}
        self.assertEqual(s.simulate_write("Edit", e, ""), "hello")
        self.assertEqual(s.simulate_write("Edit", e, None), "hello")
        self.assertEqual(s.simulate_write("Edit", {"old_string": "zz", "new_string": "y"}, "abc"), "abc")
        self.assertEqual(s.simulate_write("Edit", {"old_string": "a", "new_string": "b"}, "aXa"), "aXa")
        self.assertEqual(s.simulate_write("Bogus", {}, "keep"), "keep")
        self.assertEqual(s.simulate_write("MultiEdit", {"edits": [
            {"old_string": "a", "new_string": "b"}, {"old_string": "zz", "new_string": "c"}]}, "a"), "a")

    def test_detect_stall_shape_and_false_cases(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "requirements"))
            req = os.path.join(d, "requirements/requirements.md")
            with open(req, "w") as fh:
                fh.write("- State: Draft\n")
            self.assertIs(self.s.detect_stall({"current phase": "Requirements"}, d), False)
            with open(req, "w") as fh:
                fh.write("- State: Approved\n")
            self.assertEqual(self.s.detect_stall({"current phase": "Requirements"}, d),
                             ("Requirements", "Design"))
            self.assertIs(self.s.detect_stall({"current phase": "Tasks"}, d), False)
            self.assertIs(self.s.detect_stall({"current phase": "Implementation"}, d), False)
            self.assertIs(self.s.detect_stall({}, d), False)

    def test_review_fallback_bare_field(self):
        self.assertIn("review fallback", self.s.BARE_FIELDS)

    def test_update_json_non_dict_and_mode(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.json")
            with open(p, "w") as fh:
                fh.write("[1,2]")
            os.chmod(p, 0o600)
            out = self.s.update_json(p, lambda x: dict(x, a=1))
            self.assertEqual(out, {"a": 1})
            self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)
            self.assertEqual([f for f in os.listdir(d) if f.startswith(".tmp-")], [])

    def test_update_json_concurrent_processes_lose_nothing(self):
        import subprocess
        import tempfile
        hooks = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
        code = ("import sys; sys.path.insert(0, %r); import sdd_state as s; "
                "k=sys.argv[2]; s.update_json(sys.argv[1], lambda d: dict(d, **{k: 1}))" % hooks)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.json")
            procs = [subprocess.Popen([sys.executable, "-c", code, p, "k%d" % i]) for i in range(12)]
            for pr in procs:
                self.assertEqual(pr.wait(timeout=60), 0)
            self.assertEqual(sorted(self.s.parse_state_json(p)), sorted("k%d" % i for i in range(12)))

    def test_writers_route_through_update_json(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.json")
            for call in (lambda: self.s.mark_reviewed(p, "1"),
                         lambda: self.s.write_baseline(p, "b", "h", []),
                         lambda: self.s.write_rollback_pending(p, "t", "r", "s"),
                         lambda: self.s.write_test_author_pending(p, [], "now"),
                         lambda: self.s.write_state_json(p, {"x": 1})):
                with mock.patch.object(self.s, "update_json", wraps=self.s.update_json) as m:
                    call()
                    self.assertTrue(m.called)


if __name__ == "__main__":
    unittest.main()
