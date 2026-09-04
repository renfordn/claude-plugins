"""Tests for hooks/tdd_stop.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS_DIR)
import tdd_state  # noqa: E402

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "tdd_stop.py")


def _run(cwd, slices=None):
    if slices is not None:
        tdd_state.write_tdd_progress(cwd, {"slices": slices})
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"cwd": cwd}),
        capture_output=True,
        text=True,
    )
    msg = None
    if result.stdout.strip():
        try:
            msg = json.loads(result.stdout.strip()).get("systemMessage")
        except (json.JSONDecodeError, AttributeError):
            pass
    return msg, result.returncode


class StopHookTests(unittest.TestCase):
    def test_no_progress_file_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run(tmp)
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

    def test_no_pending_slices_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [{"id": 1, "description": "done", "status": "refactor_complete"}]
            msg, rc = _run(tmp, slices=slices)
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

    def test_pending_slice_emits_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [{"id": 1, "description": "Add validation", "status": "green_pending_review"}]
            msg, rc = _run(tmp, slices=slices)
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("Add validation", msg)
            self.assertIn("review resume", msg)

    def test_multiple_pending_slices_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [
                {"id": 1, "description": "Slice A", "status": "green_pending_review"},
                {"id": 2, "description": "Slice B", "status": "green_pending_review"},
            ]
            msg, rc = _run(tmp, slices=slices)
            self.assertIn("Slice A", msg)
            self.assertIn("Slice B", msg)
            self.assertIn("2 slice(s)", msg)

    def test_writes_last_stop_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(tmp)
            path = os.path.join(tdd_state.tdd_memory_dir(tmp), "last-stop.json")
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                data = json.load(f)
            self.assertIn("timestamp", data)


if __name__ == "__main__":
    unittest.main()
