"""Tests for PendingNellyRequestQueue: async hand-off for hook-side nelly requests."""

import unittest
from datetime import datetime, timedelta, timezone

from orchestrator.nelly_pending import PendingNellyRequestQueue, PENDING_REQUEST_TTL_SECONDS


class TestEnqueue(unittest.TestCase):
    def setUp(self):
        self.queue = PendingNellyRequestQueue()
        self.workflow_state = {}

    def test_enqueue_creates_pending_entry(self):
        query = {"error_type": "known_issue", "source_plugin": "agent-tdd", "target_plugin": "orchestrator"}
        request_id = self.queue.enqueue(self.workflow_state, "workaround_lookup", query)

        entries = self.workflow_state["orchestration"]["pending_nelly_requests"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["id"], request_id)
        self.assertEqual(entry["kind"], "workaround_lookup")
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["query"], query)
        self.assertIsNone(entry["result"])
        self.assertIsNone(entry["resolved_at"])

    def test_enqueue_dedupes_equivalent_pending_request(self):
        query = {"task_description": "implement X", "intent_hash": "abc", "design_hash": "def"}
        first_id = self.queue.enqueue(self.workflow_state, "brief_fetch", query)
        second_id = self.queue.enqueue(self.workflow_state, "brief_fetch", query)

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(self.workflow_state["orchestration"]["pending_nelly_requests"]), 1)

    def test_enqueue_does_not_dedupe_different_queries(self):
        self.queue.enqueue(self.workflow_state, "brief_fetch", {"task_description": "A"})
        self.queue.enqueue(self.workflow_state, "brief_fetch", {"task_description": "B"})

        self.assertEqual(len(self.workflow_state["orchestration"]["pending_nelly_requests"]), 2)

    def test_enqueue_rejects_invalid_kind(self):
        with self.assertRaises(ValueError):
            self.queue.enqueue(self.workflow_state, "not_a_real_kind", {})


class TestFindResolved(unittest.TestCase):
    def setUp(self):
        self.queue = PendingNellyRequestQueue()
        self.workflow_state = {}

    def test_returns_none_when_nothing_pending(self):
        result = self.queue.find_resolved(self.workflow_state, "workaround_lookup", {"x": 1})
        self.assertIsNone(result)

    def test_returns_none_while_still_pending(self):
        query = {"x": 1}
        self.queue.enqueue(self.workflow_state, "workaround_lookup", query)

        result = self.queue.find_resolved(self.workflow_state, "workaround_lookup", query)
        self.assertIsNone(result)

    def test_returns_result_once_resolved(self):
        query = {"error_type": "known_issue", "source_plugin": "agent-tdd", "target_plugin": "orchestrator"}
        self.queue.enqueue(self.workflow_state, "workaround_lookup", query)

        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        entry["status"] = "resolved"
        entry["result"] = {"workaround": {"action": "retry_with_flag"}}

        result = self.queue.find_resolved(self.workflow_state, "workaround_lookup", query)
        self.assertEqual(result, {"workaround": {"action": "retry_with_flag"}})

    def test_does_not_match_different_query(self):
        query = {"error_type": "known_issue", "source_plugin": "agent-tdd"}
        self.queue.enqueue(self.workflow_state, "workaround_lookup", query)
        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        entry["status"] = "resolved"
        entry["result"] = {"workaround": None}

        other_query = {"error_type": "known_issue", "source_plugin": "code-reviewer"}
        result = self.queue.find_resolved(self.workflow_state, "workaround_lookup", other_query)
        self.assertIsNone(result)

    def test_expired_resolved_entry_is_not_matched(self):
        query = {"x": 1}
        self.queue.enqueue(self.workflow_state, "workaround_lookup", query)
        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        entry["status"] = "resolved"
        entry["result"] = {"workaround": {"action": "x"}}
        stale = datetime.now(timezone.utc) - timedelta(seconds=PENDING_REQUEST_TTL_SECONDS + 60)
        entry["requested_at"] = stale.isoformat().replace("+00:00", "Z")

        result = self.queue.find_resolved(self.workflow_state, "workaround_lookup", query)
        self.assertIsNone(result)
        self.assertEqual(entry["status"], "expired")


class TestExpireStale(unittest.TestCase):
    def setUp(self):
        self.queue = PendingNellyRequestQueue()
        self.workflow_state = {}

    def test_fresh_pending_entry_not_expired(self):
        self.queue.enqueue(self.workflow_state, "brief_fetch", {"task_description": "x"})
        self.queue.expire_stale(self.workflow_state)

        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        self.assertEqual(entry["status"], "pending")

    def test_old_pending_entry_expires(self):
        self.queue.enqueue(self.workflow_state, "brief_fetch", {"task_description": "x"})
        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        stale = datetime.now(timezone.utc) - timedelta(seconds=PENDING_REQUEST_TTL_SECONDS + 1)
        entry["requested_at"] = stale.isoformat().replace("+00:00", "Z")

        self.queue.expire_stale(self.workflow_state)
        self.assertEqual(entry["status"], "expired")

    def test_enqueue_after_expiry_creates_new_entry_not_dedupe(self):
        query = {"task_description": "x"}
        first_id = self.queue.enqueue(self.workflow_state, "brief_fetch", query)
        entry = self.workflow_state["orchestration"]["pending_nelly_requests"][0]
        stale = datetime.now(timezone.utc) - timedelta(seconds=PENDING_REQUEST_TTL_SECONDS + 1)
        entry["requested_at"] = stale.isoformat().replace("+00:00", "Z")

        second_id = self.queue.enqueue(self.workflow_state, "brief_fetch", query)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(self.workflow_state["orchestration"]["pending_nelly_requests"]), 2)


if __name__ == "__main__":
    unittest.main()
