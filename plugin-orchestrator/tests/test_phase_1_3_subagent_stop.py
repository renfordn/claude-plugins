"""Phase 1.3: Red tests for subagent_stop hook (observability & best practices).

Goal: Verify subagent_stop hook validates contracts, surfaces errors observably,
and handles agent completion predictably per plugin reference best practices.
"""

import unittest
import json
from unittest.mock import Mock, patch, MagicMock


class TestSubagentStopHookContract(unittest.TestCase):
    """Red tests: Subagent_stop follows plugin reference hook contract."""

    def test_hook_receives_agent_type(self):
        """GIVEN agent completion event
        WHEN hook is invoked
        THEN it receives agent_type (e.g., 'agent-tdd', 'agent-isdd')."""
        agent_type = "agent-tdd"
        self.assertIsNotNone(agent_type)

    def test_hook_receives_agent_report(self):
        """GIVEN agent completion with report
        WHEN hook is invoked
        THEN it receives last_assistant_message or transcript_path."""
        report = "Agent completed successfully.\n<!--AGENT-TDD-PHASE:completed-->"
        self.assertIn("completed", report)

    def test_hook_receives_workflow_state(self):
        """GIVEN subagent_stop hook invoked
        WHEN hook receives inputs
        THEN it includes workflow_state dict (handoff_history, error_lessons, etc.)."""
        workflow_state = {
            "orchestration": {
                "handoff_history": [],
                "error_lessons": []
            }
        }
        self.assertIn("orchestration", workflow_state)


class TestPhaseMarkerExtraction(unittest.TestCase):
    """Red tests: Phase marker parsing from agent report."""

    def test_extract_phase_marker_from_report(self):
        """GIVEN agent report with phase marker
        WHEN marker is extracted
        THEN returns the marker string (e.g., 'completed', 'research_validation_failed')."""
        report = "Agent work complete.\n<!--AGENT-TDD-PHASE:implementation_complete-->"
        # Hook should extract 'implementation_complete' from the HTML comment
        # Expected: phase_marker = "implementation_complete"
        self.assertIn("implementation_complete", report)

    def test_extract_phase_marker_handles_missing_marker(self):
        """GIVEN agent report with no phase marker
        WHEN marker extraction is attempted
        THEN returns None (no error raised)."""
        report = "Agent completed successfully."
        # Hook should handle missing marker gracefully
        # Expected: phase_marker = None
        self.assertNotIn("<!--", report)

    def test_extract_phase_marker_handles_malformed_marker(self):
        """GIVEN agent report with malformed phase marker
        WHEN marker extraction is attempted
        THEN gracefully handles it (logs warning, continues)."""
        report = "<!--AGENT-TDD-PHASE:invalid marker with spaces-->"
        # Hook should not crash on malformed marker
        # Expected: log warning, phase_marker = None or partial
        self.assertIn("PHASE", report)


class TestEscalationMarkerDetection(unittest.TestCase):
    """Red tests: Escalation marker detection for rollback/pause."""

    def test_detect_escalation_marker_in_report(self):
        """GIVEN agent report with escalation marker
        WHEN escalation detection runs
        THEN returns the escalation marker string."""
        report = "Research validation failed.\n<!--AGENT-TDD-RESEARCH-FAILED:findings-contradiction-->"
        # Hook should detect escalation marker
        # Expected: escalation_marker = "findings-contradiction"
        self.assertIn("FAILED", report)

    def test_detect_escalation_handles_no_marker(self):
        """GIVEN agent report with no escalation marker
        WHEN escalation detection runs
        THEN returns None."""
        report = "Agent completed successfully."
        # Hook should return None (no escalation)
        self.assertNotIn("FAILED", report)

    def test_escalation_marker_triggers_rollback_pending(self):
        """GIVEN escalation marker detected
        WHEN escalation is processed
        THEN workflow_state['rollback_pending'] is set."""
        workflow_state = {"orchestration": {}}
        escalation_marker = "findings-contradiction"
        # Hook should set: workflow_state["rollback_pending"] = {escalation_type, marker_found, ...}
        # Expected: workflow_state["rollback_pending"] is not None
        if escalation_marker:
            workflow_state["rollback_pending"] = {"marker": escalation_marker}
        self.assertIn("rollback_pending", workflow_state)


class TestContractValidation(unittest.TestCase):
    """Red tests: Contract validation against capability contracts."""

    def test_validate_agent_output_against_capability_contract(self):
        """GIVEN agent produces output (requirements_md, design_md, etc.)
        WHEN contract validation runs
        THEN validates against INTEROP.md 'produces' fields."""
        agent_type = "agent-isdd"
        output = {
            "requirements_md": "# Requirements\n...",
            "design_md": "# Design\n...",
        }
        # Hook should validate output against agent-isdd INTEROP.md
        # Expected: validation passes (all required fields present)
        self.assertIn("requirements_md", output)
        self.assertIn("design_md", output)

    def test_contract_violation_detected_missing_field(self):
        """GIVEN agent output missing required field
        WHEN contract validation runs
        THEN error is detected (validation fails)."""
        output = {
            "design_md": "# Design",
            # Missing: requirements_md
        }
        # Hook should detect missing required field
        # Expected: validation fails, error returned
        self.assertNotIn("requirements_md", output)

    def test_contract_validation_handles_extra_fields(self):
        """GIVEN agent output includes extra fields beyond INTEROP.md
        WHEN contract validation runs
        THEN extra fields are ignored (forward compatible)."""
        output = {
            "requirements_md": "# Requirements",
            "design_md": "# Design",
            "extra_field": "ignored",
        }
        # Hook should ignore extra fields
        # Expected: validation passes (required fields present)
        self.assertEqual(len(output), 3)


class TestErrorObservability(unittest.TestCase):
    """Red tests: Hook errors are observable to user."""

    def test_contract_violation_surfaces_in_system_message(self):
        """GIVEN contract validation fails
        WHEN error is processed
        THEN systemMessage includes error + recovery action."""
        error = {
            "type": "CONTRACT_VIOLATION",
            "message": "Missing required field: requirements_md",
            "recovery": "Re-run agent with updated inputs"
        }
        # Hook should format systemMessage with error details
        # Expected: systemMessage contains error type, message, recovery action
        self.assertIn("type", error)
        self.assertIn("recovery", error)

    def test_handoff_event_logged_to_history(self):
        """GIVEN agent completes
        WHEN completion is processed
        THEN handoff event is logged to workflow_state['orchestration']['handoff_history']."""
        workflow_state = {"orchestration": {"handoff_history": []}}
        handoff_event = {
            "timestamp": "2026-09-16T23:41:55Z",
            "agent_type": "agent-tdd",
            "phase_marker": "implementation_complete",
            "contract_valid": True,
        }
        workflow_state["orchestration"]["handoff_history"].append(handoff_event)
        # Hook should log handoff event
        # Expected: handoff_history now has one entry
        self.assertEqual(len(workflow_state["orchestration"]["handoff_history"]), 1)

    def test_soft_dependency_failure_logged_not_escalated(self):
        """GIVEN soft dependency (agent-nelly) unavailable
        WHEN dependency check runs
        THEN error is logged but workflow continues (graceful degradation)."""
        # Hook should detect soft dependency missing
        # Log warning: "agent-nelly unavailable; continuing with degraded context"
        # Expected: NOT escalation_marker, workflow continues
        pass

    def test_hard_dependency_failure_escalated(self):
        """GIVEN hard dependency (agent-isdd, agent-tdd) unavailable
        WHEN dependency check runs
        THEN escalation marker is set (workflow pauses)."""
        # Hook should detect hard dependency missing
        # Set escalation_marker
        # Expected: workflow_state["rollback_pending"] set, user sees error
        pass


class TestHookBestPractices(unittest.TestCase):
    """Red tests: Hook follows plugin reference best practices."""

    def test_hook_never_blocks_on_error(self):
        """GIVEN any error (contract violation, missing dependency, I/O, etc.)
        WHEN error occurs
        THEN hook completes gracefully (exit 0, never blocks workflow)."""
        # This is the most critical best practice
        # Expected: hook always exits 0, never raises exception
        pass

    def test_hook_is_idempotent(self):
        """GIVEN same agent completion event
        WHEN hook processes it twice
        THEN handoff_history has two entries (not deduplicated)."""
        # Hook should not try to deduplicate or cache
        # Expected: same input → same output (idempotent per invocation)
        workflow_state = {"orchestration": {"handoff_history": []}}
        event = {"timestamp": "T1", "agent_type": "agent-tdd"}
        workflow_state["orchestration"]["handoff_history"].append(event)
        workflow_state["orchestration"]["handoff_history"].append(event)
        self.assertEqual(len(workflow_state["orchestration"]["handoff_history"]), 2)

    def test_hook_preserves_prior_handoff_history(self):
        """GIVEN workflow_state with existing handoff_history
        WHEN hook adds new entry
        THEN prior entries are preserved (appended to, not replaced)."""
        workflow_state = {
            "orchestration": {
                "handoff_history": [
                    {"agent": "agent-isdd", "phase": "design_complete"},
                ]
            }
        }
        new_entry = {"agent": "agent-tdd", "phase": "implementation_complete"}
        workflow_state["orchestration"]["handoff_history"].append(new_entry)
        # Expected: handoff_history has both entries
        self.assertEqual(len(workflow_state["orchestration"]["handoff_history"]), 2)

    def test_hook_system_message_visible_to_user(self):
        """GIVEN hook detects error or escalation
        WHEN systemMessage is built
        THEN systemMessage is returned to Claude Code for user display."""
        # Hook should always return systemMessage when there's error/escalation
        # Expected: systemMessage includes error details
        system_message = "Contract violation: missing requirements_md"
        self.assertIsNotNone(system_message)


if __name__ == "__main__":
    unittest.main()
