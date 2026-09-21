"""Tests for hooks/resolve_nelly_request.py: the CLI that writes a resolved
nelly request back to workflow-state.json on behalf of the main session."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

from hook_state import load_workflow_state, save_workflow_state  # noqa: E402
import resolve_nelly_request as cli  # noqa: E402


class TestResolveRequest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self.tmpdir.name, "workflow-state.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _seed_pending(self, kind="workaround_lookup", query=None):
        query = query if query is not None else {"error_type": "known_issue"}
        state = {
            "orchestration": {
                "pending_nelly_requests": [
                    {
                        "id": "req-1",
                        "kind": kind,
                        "requested_at": "2026-09-14T00:00:00Z",
                        "status": "pending",
                        "query": query,
                        "result": None,
                        "resolved_at": None,
                    }
                ]
            }
        }
        save_workflow_state(self.state_path, state)
        return state

    def test_resolve_writes_result_and_marks_resolved(self):
        self._seed_pending()

        exit_code = cli.resolve_request(
            self.state_path, "req-1", json.dumps({"workaround": {"action": "retry"}})
        )

        self.assertEqual(exit_code, 0)
        state = load_workflow_state(self.state_path)
        entry = state["orchestration"]["pending_nelly_requests"][0]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["result"], {"workaround": {"action": "retry"}})
        self.assertIsNotNone(entry["resolved_at"])

    def test_resolve_unknown_id_fails(self):
        self._seed_pending()

        exit_code = cli.resolve_request(self.state_path, "no-such-id", "{}")

        self.assertEqual(exit_code, 1)

    def test_resolve_invalid_json_fails(self):
        self._seed_pending()

        exit_code = cli.resolve_request(self.state_path, "req-1", "{not json")

        self.assertEqual(exit_code, 1)
        state = load_workflow_state(self.state_path)
        entry = state["orchestration"]["pending_nelly_requests"][0]
        self.assertEqual(entry["status"], "pending")  # untouched

    def test_resolve_expired_request_fails(self):
        state = self._seed_pending()
        state["orchestration"]["pending_nelly_requests"][0]["status"] = "expired"
        save_workflow_state(self.state_path, state)

        exit_code = cli.resolve_request(self.state_path, "req-1", "{}")

        self.assertEqual(exit_code, 1)

    def test_list_on_empty_state_succeeds(self):
        save_workflow_state(self.state_path, {})
        exit_code = cli.list_requests(self.state_path)
        self.assertEqual(exit_code, 0)

    def test_list_with_entries_succeeds(self):
        self._seed_pending()
        exit_code = cli.list_requests(self.state_path)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
