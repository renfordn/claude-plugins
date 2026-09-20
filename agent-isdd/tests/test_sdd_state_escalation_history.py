"""Tests for sdd_state.py's escalation_history helpers (write_escalation_outcome,
read_escalation_pending, clear_escalation_pending) -- mirrors RollbackPendingTests in
test_sdd_state.py but for the append-only escalation_history list.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import hook_test_utils as h  # noqa: E402


class EscalationHistoryTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, h.HOOKS_DIR)
        import importlib
        self.sdd_state = importlib.import_module("sdd_state")

    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_read_escalation_pending_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"current_phase": "Implementation"})
            self.assertIsNone(self.sdd_state.read_escalation_pending(path))

    def test_read_escalation_pending_returns_dict_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            pending = {"reason": "r", "from_model": "haiku", "to_model": "sonnet",
                       "detected_at": "2026-09-19T00:00:00"}
            self._write_json(path, {"escalation_pending": pending})
            self.assertEqual(self.sdd_state.read_escalation_pending(path), pending)

    def test_write_escalation_outcome_appends_and_clears_pending(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            pending = {"reason": "r", "from_model": "haiku", "to_model": "sonnet",
                       "detected_at": "2026-09-19T00:00:00"}
            self._write_json(path, {"current_phase": "Implementation", "escalation_pending": pending})
            entry = dict(pending, outcome="succeeded", resolved_at="2026-09-19T01:00:00")
            self.sdd_state.write_escalation_outcome(path, entry)

            data = self.sdd_state.parse_state_json(path)
            self.assertNotIn("escalation_pending", data)
            self.assertEqual(data["escalation_history"], [entry])
            self.assertEqual(data.get("current_phase"), "Implementation")

    def test_write_escalation_outcome_appends_without_clobbering_prior_entries(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            first_entry = {"reason": "r1", "outcome": "failed"}
            self._write_json(path, {"escalation_history": [first_entry]})
            second_entry = {"reason": "r2", "outcome": "succeeded"}
            self.sdd_state.write_escalation_outcome(path, second_entry)

            data = self.sdd_state.parse_state_json(path)
            self.assertEqual(data["escalation_history"], [first_entry, second_entry])

    def test_write_escalation_outcome_creates_file_if_missing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            entry = {"reason": "r", "outcome": "ambiguous"}
            self.sdd_state.write_escalation_outcome(path, entry)
            data = self.sdd_state.parse_state_json(path)
            self.assertEqual(data["escalation_history"], [entry])

    def test_clear_escalation_pending_removes_field(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "workflow-state.json")
            self._write_json(path, {"escalation_pending": {"reason": "r"}})
            self.sdd_state.clear_escalation_pending(path)
            self.assertIsNone(self.sdd_state.read_escalation_pending(path))

    def test_clear_escalation_pending_is_noop_when_missing(self):
        # must not raise
        self.sdd_state.clear_escalation_pending("/nonexistent/workflow-state.json")


if __name__ == "__main__":
    unittest.main()
