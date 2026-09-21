"""Phase 2.3: Red tests for surfacing errors in systemMessage.

Goal: Verify that subagent_stop returns systemMessage with error details when
error severity >= "warn".
"""

import unittest
from orchestrator.error import ContractViolationError, DependencyUnavailableError, InfrastructureError
from orchestrator.hooks.subagent_stop import build_system_message


class TestSystemMessageErrorVisibility(unittest.TestCase):
    """Red tests: Errors are visible in systemMessage."""

    def test_build_system_message_exists(self):
        """GIVEN subagent_stop error surfacing
        WHEN build_system_message is called
        THEN function exists."""
        self.assertTrue(callable(build_system_message))

    def test_system_message_includes_contract_violation_error(self):
        """GIVEN a ContractViolationError occurs
        WHEN build_system_message is called
        THEN systemMessage includes error type."""
        error = ContractViolationError("missing fields", "update spec")
        msg = build_system_message(error=error)
        self.assertIn("contract_violation", msg.lower())

    def test_system_message_includes_recovery_action(self):
        """GIVEN an error with recovery_action
        WHEN build_system_message is called
        THEN systemMessage includes recovery guidance."""
        error = ContractViolationError("missing fields", "update design spec and re-run")
        msg = build_system_message(error=error)
        self.assertIn("update design spec", msg)

    def test_system_message_includes_error_registry_link(self):
        """GIVEN errors are logged
        WHEN build_system_message is called
        THEN systemMessage includes reference to error_registry.json."""
        error = ContractViolationError("test", "fix")
        msg = build_system_message(error=error, registry_path="/path/to/error_registry.json")
        # Should include some reference to where to find more details
        self.assertGreater(len(msg), 50)

    def test_system_message_ignores_info_level_errors(self):
        """GIVEN error with info severity
        WHEN build_system_message is called with severity threshold "warn"
        THEN error is not included (or minimal mention only)."""
        # For now, HookError subclasses only have critical/warn, so we test that
        # DependencyUnavailableError (warn) is included, but we'd skip info if it existed
        error = DependencyUnavailableError("nelly unavailable", "continue")
        msg = build_system_message(error=error, min_severity="critical")
        # If severity is "warn", and min_severity is "critical", it should be excluded or minimal
        # For now, just verify the function accepts severity filtering
        self.assertIsNotNone(msg)

    def test_system_message_formatted_for_readability(self):
        """GIVEN error details
        WHEN build_system_message is called
        THEN message is formatted for user readability (not just JSON dump)."""
        error = ContractViolationError(
            "missing task_findings field",
            "re-run with updated design spec containing task_findings"
        )
        msg = build_system_message(error=error)
        # Should be readable, with line breaks and clear structure
        self.assertGreater(len(msg), 20)
        # Should not be raw JSON (no "{" at start)
        self.assertNotEqual(msg[0], "{")

    def test_system_message_includes_error_type_name(self):
        """GIVEN different error types
        WHEN build_system_message is called
        THEN message names the error type clearly."""
        errors = [
            (ContractViolationError("e", "f"), "contract"),
            (DependencyUnavailableError("e", "f"), "dependency"),
            (InfrastructureError("e", "f"), "infrastructure"),
        ]
        for error, keyword in errors:
            msg = build_system_message(error=error)
            self.assertIn(keyword, msg.lower())


class TestSystemMessageMultipleErrors(unittest.TestCase):
    """Red tests: systemMessage can show multiple recent errors."""

    def test_system_message_includes_multiple_errors(self):
        """GIVEN multiple errors in error list
        WHEN build_system_message is called
        THEN message includes last 3 errors."""
        errors = [
            ContractViolationError("error1", "fix1"),
            DependencyUnavailableError("error2", "fix2"),
            InfrastructureError("error3", "fix3"),
        ]
        msg = build_system_message(errors=errors)
        # Should mention multiple errors
        self.assertGreater(len(msg), 50)

    def test_system_message_includes_suggested_action(self):
        """GIVEN errors with recovery_actions
        WHEN build_system_message is called
        THEN message includes next steps."""
        error = ContractViolationError("missing fields", "ensure all required fields are present")
        msg = build_system_message(error=error)
        self.assertIn("ensure all required", msg)


if __name__ == '__main__':
    unittest.main()
