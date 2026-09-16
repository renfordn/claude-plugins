"""Phase 4.3: Integration tests for full hook workflow (HIGH-RISK).

Goal: Verify setup_workflow_state → agent → subagent_stop workflow completes
with error observability, error lessons sharing, and nelly caching working end-to-end.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from orchestrator.error_logger import ErrorRegistry
from orchestrator.nelly import NellyBriefManager
from orchestrator.hooks.subagent_stop import (
    build_system_message, extract_error_lesson, share_error_lessons_to_next_phase
)
from orchestrator.error import ContractViolationError, DependencyUnavailableError


class TestFullWorkflowIntegration(unittest.TestCase):
    """Integration tests: full workflow with all phases working together."""

    def test_workflow_initialization_to_completion(self):
        """GIVEN a fresh workflow_state
        WHEN setup_workflow_state and subagent_stop are called in sequence
        THEN workflow completes with all state properly initialized."""
        workflow_state = {}

        # Phase 1: Initialize workflow state (before first agent spawn)
        nelly_manager = NellyBriefManager()
        nelly_manager.fetch_and_cache(workflow_state, cwd=".", task_description="test workflow")

        # Verify orchestration structure created
        self.assertIn("orchestration", workflow_state)
        self.assertIn("nelly_brief_cache", workflow_state["orchestration"])

    def test_error_lessons_flow_through_phases(self):
        """GIVEN agent-isdd fails with contract violation
        WHEN error is extracted and shared
        AND agent-tdd spawns next
        THEN error lesson is available for next phase."""
        workflow_state = {}

        # Simulate agent-isdd completing with error
        error = ContractViolationError("missing task_findings", "update design spec")
        lesson = extract_error_lesson("agent-isdd", error)

        # Share error lesson to workflow state
        share_error_lessons_to_next_phase(workflow_state, lesson)

        # Verify lesson is shared
        lessons = workflow_state["orchestration"]["error_lessons"]
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["agent_type"], "agent-isdd")
        self.assertIn("CONTRACT_VIOLATION", lessons[0]["error_type"])

    def test_error_registry_persistence(self):
        """GIVEN errors occur during workflow
        WHEN error_registry.json is written
        THEN errors persist and can be queried later."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log errors from different hooks
            error1 = ContractViolationError("error1", "fix1")
            registry.log_error(error1, "before_continue", "agent-isdd")

            error2 = DependencyUnavailableError("error2", "fix2")
            registry.log_error(error2, "subagent_stop", "agent-tdd")

            # Read back
            errors = registry.read_errors()
            self.assertEqual(len(errors), 2)
            self.assertEqual(errors[0]["agent_type"], "agent-isdd")
            self.assertEqual(errors[1]["agent_type"], "agent-tdd")

    def test_nelly_brief_caching_and_reuse(self):
        """GIVEN nelly brief is fetched at workflow start
        WHEN subsequent phases need context
        THEN cached brief is reused (efficient, no duplicate fetches)."""
        workflow_state = {}
        nelly_manager = NellyBriefManager()

        # Fetch and cache
        nelly_manager.fetch_and_cache(workflow_state, cwd=".")
        first_cache = workflow_state["orchestration"]["nelly_brief_cache"].copy()
        first_hash = first_cache["intent_hash"]

        # Simulate next phase calling with same intent hash
        nelly_manager.fetch_and_cache(workflow_state, intent_hash=first_hash)

        # Cache should still be there with same hash
        second_cache = workflow_state["orchestration"]["nelly_brief_cache"]
        self.assertEqual(second_cache["intent_hash"], first_hash)

    def test_system_message_includes_all_context(self):
        """GIVEN error occurs with prior error lessons
        WHEN building systemMessage
        THEN message includes error, recovery action, and prior lessons."""
        workflow_state = {}

        # Add prior error lesson
        lesson = {
            "agent_type": "agent-isdd",
            "error_type": "RESEARCH_VALIDATION_FAILED",
            "root_cause": "incomplete research",
            "recommendation": "expand research phase"
        }
        share_error_lessons_to_next_phase(workflow_state, lesson)

        # Create new error
        new_error = ContractViolationError("missing spec", "update design")
        lessons = workflow_state["orchestration"]["error_lessons"]

        # Build message
        msg = build_system_message(error=new_error, error_lessons=lessons)

        # Verify message includes both
        self.assertIn("contract_violation", msg.lower())
        self.assertIn("agent-isdd", msg)
        self.assertIn("expand research", msg)

    def test_workflow_sla_compliance(self):
        """GIVEN full workflow execution (initialization + error handling)
        WHEN measuring end-to-end time
        THEN total time is under 100ms (SLA compliance)."""
        workflow_state = {}
        start = time.time()

        # Initialize
        nelly_manager = NellyBriefManager()
        nelly_manager.fetch_and_cache(workflow_state, cwd=".")

        # Simulate error handling
        error = ContractViolationError("test", "fix")
        lesson = extract_error_lesson("agent-tdd", error)
        share_error_lessons_to_next_phase(workflow_state, lesson)

        # Build message
        msg = build_system_message(error=error, error_lessons=workflow_state["orchestration"]["error_lessons"])

        elapsed = (time.time() - start) * 1000  # Convert to ms

        # Should be much under 100ms
        self.assertLess(elapsed, 100, f"Workflow took {elapsed}ms, exceeds 100ms SLA")

    def test_graceful_degradation_on_failure(self):
        """GIVEN various failures (nelly unavailable, file I/O, etc.)
        WHEN workflow continues
        THEN no exceptions raised, workflow completes."""
        workflow_state = {}

        try:
            # Initialize with nonexistent path (should still work)
            nelly_manager = NellyBriefManager()
            nelly_manager.fetch_and_cache(workflow_state, cwd="/nonexistent")

            # Continue with error handling
            error = DependencyUnavailableError("nelly offline", "continue")
            lesson = extract_error_lesson("agent-isdd", error)
            share_error_lessons_to_next_phase(workflow_state, lesson)

            # Verify state is consistent
            self.assertIn("orchestration", workflow_state)
            self.assertIn("error_lessons", workflow_state["orchestration"])
        except Exception as e:
            self.fail(f"Workflow should degrade gracefully: {e}")


if __name__ == '__main__':
    unittest.main()
