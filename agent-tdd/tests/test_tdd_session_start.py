"""Tests for hooks/tdd_session_start.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS_DIR)
import tdd_state  # noqa: E402

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "tdd_session_start.py")


def _run(cwd, slices=None):
    if slices is not None:
        tdd_state.write_tdd_progress(cwd, {"slices": slices})
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"cwd": cwd}),
        capture_output=True,
        text=True,
    )
    out = None
    if result.stdout.strip():
        try:
            out = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pass
    return out, result.returncode


class SessionStartOutputTests(unittest.TestCase):
    def test_output_uses_hook_specific_output_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, rc = _run(tmp)
            self.assertEqual(rc, 0)
            self.assertIsNotNone(out)
            self.assertIn("hookSpecificOutput", out)
            envelope = out["hookSpecificOutput"]
            self.assertEqual(envelope["hookEventName"], "SessionStart")
            self.assertIn("additionalContext", envelope)

    def test_no_pending_slices_includes_state_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, rc = _run(tmp)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertIn("agent-TDD state", ctx)
            self.assertNotIn("awaiting review", ctx)

    def test_pending_slices_listed_in_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [
                {"id": 1, "description": "Add caching layer", "status": "green_pending_review"},
            ]
            out, rc = _run(tmp, slices=slices)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Add caching layer", ctx)
            self.assertIn("awaiting review resume", ctx)

    def test_multiple_pending_slices_all_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [
                {"id": 1, "description": "Slice A", "status": "green_pending_review"},
                {"id": 2, "description": "Slice B", "status": "green_pending_review"},
            ]
            out, rc = _run(tmp, slices=slices)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Slice A", ctx)
            self.assertIn("Slice B", ctx)
            self.assertIn("2", ctx)

    def test_completed_slices_not_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            slices = [
                {"id": 1, "description": "Done slice", "status": "refactor_complete"},
            ]
            out, rc = _run(tmp, slices=slices)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertNotIn("Done slice", ctx)
            self.assertNotIn("awaiting review", ctx)

    def test_malformed_payload_still_outputs_valid_json(self):
        result = subprocess.run(
            [sys.executable, HOOK],
            input="not json",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout.strip())
        self.assertIn("hookSpecificOutput", out)


if __name__ == "__main__":
    unittest.main()
