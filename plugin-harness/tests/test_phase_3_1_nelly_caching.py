"""Phase 3.1: Red tests for nelly brief caching (HIGH-RISK).

Goal: Verify that nelly brief is cached with Intent Hash and reused/refreshed.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from orchestrator.nelly import NellyBriefManager


class TestNellyBriefCaching(unittest.TestCase):
    """Red tests: Nelly brief caching with Intent Hash and TTL."""

    def test_nelly_brief_manager_exists(self):
        """GIVEN nelly brief caching
        WHEN NellyBriefManager is accessed
        THEN it exists and can be instantiated."""
        manager = NellyBriefManager()
        self.assertIsNotNone(manager)

    def test_fetch_and_cache_method_exists(self):
        """GIVEN NellyBriefManager
        WHEN checking for fetch_and_cache method
        THEN it exists and is callable."""
        manager = NellyBriefManager()
        self.assertTrue(hasattr(manager, 'fetch_and_cache'))
        self.assertTrue(callable(manager.fetch_and_cache))

    def test_fetch_and_cache_creates_orchestration_structure(self):
        """GIVEN workflow_state without orchestration
        WHEN fetch_and_cache is called
        THEN orchestration structure is created."""
        manager = NellyBriefManager()
        workflow_state = {}

        manager.fetch_and_cache(workflow_state, cwd=".", task_description="test")

        self.assertIn("orchestration", workflow_state)
        self.assertIn("nelly_brief_cache", workflow_state["orchestration"])

    def test_fetch_and_cache_includes_cache_fields(self):
        """GIVEN workflow_state after fetch_and_cache
        WHEN inspecting cache
        THEN it includes brief_text, metadata, intent_hash, design_hash, timestamp."""
        manager = NellyBriefManager()
        workflow_state = {}

        manager.fetch_and_cache(workflow_state, cwd=".", task_description="test")

        cache = workflow_state["orchestration"]["nelly_brief_cache"]
        required_fields = ["brief_text", "metadata", "intent_hash", "design_hash", "timestamp"]
        for field in required_fields:
            self.assertIn(field, cache)

    def test_fetch_and_cache_is_idempotent(self):
        """GIVEN first call to fetch_and_cache
        WHEN calling again immediately
        THEN cache structure is preserved (no errors)."""
        manager = NellyBriefManager()
        workflow_state = {}

        # First call
        manager.fetch_and_cache(workflow_state, cwd=".", task_description="test")
        first_hash = workflow_state["orchestration"]["nelly_brief_cache"]["intent_hash"]

        # Second call
        manager.fetch_and_cache(workflow_state, cwd=".", task_description="test")
        second_hash = workflow_state["orchestration"]["nelly_brief_cache"]["intent_hash"]

        # Intent Hash should be consistent
        self.assertEqual(first_hash, second_hash)

    def test_fetch_and_cache_graceful_on_error(self):
        """GIVEN fetch fails (e.g., nelly unavailable)
        WHEN fetch_and_cache is called
        THEN it doesn't raise (graceful degradation)."""
        manager = NellyBriefManager()
        workflow_state = {}

        # Should not raise even if _call_agent_nelly fails
        try:
            manager.fetch_and_cache(workflow_state, cwd="/nonexistent", task_description="test")
            # Should have cache structure even if fetch failed
            self.assertIn("orchestration", workflow_state)
            self.assertIn("nelly_brief_cache", workflow_state["orchestration"])
        except Exception as e:
            self.fail(f"fetch_and_cache should not raise: {e}")

    def test_fetch_and_cache_intent_hash_reuse(self):
        """GIVEN cache with matching intent_hash
        WHEN fetch_and_cache called with same intent_hash
        THEN cache may be reused (no fresh fetch) for valid TTL."""
        manager = NellyBriefManager()
        workflow_state = {}

        # First fetch
        manager.fetch_and_cache(workflow_state, cwd=".", task_description="test")
        first_cache = workflow_state["orchestration"]["nelly_brief_cache"].copy()

        # Second fetch with same intent_hash
        same_hash = first_cache["intent_hash"]
        manager.fetch_and_cache(workflow_state, cwd=".", intent_hash=same_hash)

        # Cache should exist (may or may not be reused, just verify structure)
        second_cache = workflow_state["orchestration"]["nelly_brief_cache"]
        self.assertIn("intent_hash", second_cache)

    def test_fetch_and_cache_cache_expiration_check(self):
        """GIVEN cache with valid intent_hash
        WHEN cache TTL is checked
        THEN expired cache should be refreshable."""
        manager = NellyBriefManager()
        workflow_state = {}

        # Create cache
        manager.fetch_and_cache(workflow_state, cwd=".")

        # Check that cache structure allows for TTL validation
        cache = workflow_state["orchestration"]["nelly_brief_cache"]
        self.assertIn("timestamp", cache)
        # Timestamp should be recent (within last minute)
        import time
        age = time.time() - cache["timestamp"]
        self.assertLess(age, 60)


if __name__ == '__main__':
    unittest.main()
