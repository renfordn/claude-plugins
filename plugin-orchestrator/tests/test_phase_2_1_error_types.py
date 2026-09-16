"""Phase 2.1: Red tests for HookErrorType enum and error classes.

Goal: Verify that hook errors are explicitly classified into CONTRACT_VIOLATION,
DEPENDENCY_UNAVAILABLE, and INFRASTRUCTURE_ERROR types, each with severity,
recovery_action, and message fields.
"""

import unittest
from enum import Enum
from orchestrator.error import HookErrorType, HookError, ContractViolationError, DependencyUnavailableError, InfrastructureError


class TestHookErrorTypeEnum(unittest.TestCase):
    """Red tests: HookErrorType enum exists and has required values."""

    def test_hook_error_type_enum_exists(self):
        """GIVEN hook error handling needs explicit classification
        WHEN HookErrorType enum is accessed
        THEN it exists and is an Enum."""
        self.assertTrue(issubclass(HookErrorType, Enum))

    def test_hook_error_type_has_contract_violation(self):
        """GIVEN HookErrorType enum
        WHEN accessing CONTRACT_VIOLATION
        THEN it exists."""
        self.assertTrue(hasattr(HookErrorType, 'CONTRACT_VIOLATION'))
        self.assertEqual(HookErrorType.CONTRACT_VIOLATION.name, 'CONTRACT_VIOLATION')

    def test_hook_error_type_has_dependency_unavailable(self):
        """GIVEN HookErrorType enum
        WHEN accessing DEPENDENCY_UNAVAILABLE
        THEN it exists."""
        self.assertTrue(hasattr(HookErrorType, 'DEPENDENCY_UNAVAILABLE'))
        self.assertEqual(HookErrorType.DEPENDENCY_UNAVAILABLE.name, 'DEPENDENCY_UNAVAILABLE')

    def test_hook_error_type_has_infrastructure_error(self):
        """GIVEN HookErrorType enum
        WHEN accessing INFRASTRUCTURE_ERROR
        THEN it exists."""
        self.assertTrue(hasattr(HookErrorType, 'INFRASTRUCTURE_ERROR'))
        self.assertEqual(HookErrorType.INFRASTRUCTURE_ERROR.name, 'INFRASTRUCTURE_ERROR')


class TestHookErrorBaseClass(unittest.TestCase):
    """Red tests: HookError base class with type, severity, message, recovery_action."""

    def test_hook_error_base_class_exists(self):
        """GIVEN hook error handling
        WHEN HookError base class is accessed
        THEN it exists and is an Exception subclass."""
        self.assertTrue(issubclass(HookError, Exception))

    def test_hook_error_has_type_field(self):
        """GIVEN HookError is raised
        WHEN inspecting its type field
        THEN error_type is set and is a HookErrorType."""
        error = HookError(
            error_type=HookErrorType.CONTRACT_VIOLATION,
            severity="critical",
            message="missing fields",
            recovery_action="re-run with complete spec"
        )
        self.assertEqual(error.error_type, HookErrorType.CONTRACT_VIOLATION)

    def test_hook_error_has_severity_field(self):
        """GIVEN HookError is raised
        WHEN inspecting its severity field
        THEN severity is set (one of "critical", "warn", "info")."""
        error = HookError(
            error_type=HookErrorType.DEPENDENCY_UNAVAILABLE,
            severity="warn",
            message="nelly unavailable",
            recovery_action="continue with degraded state"
        )
        self.assertEqual(error.severity, "warn")

    def test_hook_error_has_message_field(self):
        """GIVEN HookError is raised
        WHEN inspecting its message field
        THEN message is set."""
        error = HookError(
            error_type=HookErrorType.INFRASTRUCTURE_ERROR,
            severity="critical",
            message="workflow-state file corrupted",
            recovery_action="manual intervention required"
        )
        self.assertEqual(error.message, "workflow-state file corrupted")

    def test_hook_error_has_recovery_action_field(self):
        """GIVEN HookError is raised
        WHEN inspecting its recovery_action field
        THEN recovery_action is set."""
        error = HookError(
            error_type=HookErrorType.CONTRACT_VIOLATION,
            severity="critical",
            message="missing required capability",
            recovery_action="ensure agent exports required capability"
        )
        self.assertEqual(error.recovery_action, "ensure agent exports required capability")

    def test_hook_error_is_exception(self):
        """GIVEN HookError is raised
        WHEN catching it as an Exception
        THEN it is caught successfully."""
        error = HookError(
            error_type=HookErrorType.INFRASTRUCTURE_ERROR,
            severity="critical",
            message="test error",
            recovery_action="test recovery"
        )
        with self.assertRaises(Exception):
            raise error


class TestContractViolationError(unittest.TestCase):
    """Red tests: ContractViolationError subclass with default severity."""

    def test_contract_violation_error_exists(self):
        """GIVEN hook error handling
        WHEN ContractViolationError is accessed
        THEN it exists and is a HookError subclass."""
        self.assertTrue(issubclass(ContractViolationError, HookError))

    def test_contract_violation_error_has_critical_severity(self):
        """GIVEN ContractViolationError is raised
        WHEN inspecting severity
        THEN default severity is "critical" (blocking)."""
        error = ContractViolationError(
            message="missing task_findings field",
            recovery_action="re-run with updated design spec"
        )
        self.assertEqual(error.severity, "critical")

    def test_contract_violation_error_has_correct_type(self):
        """GIVEN ContractViolationError is raised
        WHEN inspecting error_type
        THEN error_type is CONTRACT_VIOLATION."""
        error = ContractViolationError(
            message="invalid handoff",
            recovery_action="check INTEROP.md"
        )
        self.assertEqual(error.error_type, HookErrorType.CONTRACT_VIOLATION)


class TestDependencyUnavailableError(unittest.TestCase):
    """Red tests: DependencyUnavailableError subclass with default severity."""

    def test_dependency_unavailable_error_exists(self):
        """GIVEN hook error handling
        WHEN DependencyUnavailableError is accessed
        THEN it exists and is a HookError subclass."""
        self.assertTrue(issubclass(DependencyUnavailableError, HookError))

    def test_dependency_unavailable_error_has_warn_severity(self):
        """GIVEN DependencyUnavailableError is raised
        WHEN inspecting severity
        THEN default severity is "warn" (soft, graceful)."""
        error = DependencyUnavailableError(
            message="agent-nelly unavailable",
            recovery_action="continue with empty brief"
        )
        self.assertEqual(error.severity, "warn")

    def test_dependency_unavailable_error_has_correct_type(self):
        """GIVEN DependencyUnavailableError is raised
        WHEN inspecting error_type
        THEN error_type is DEPENDENCY_UNAVAILABLE."""
        error = DependencyUnavailableError(
            message="agent-ux missing",
            recovery_action="no UI rendering, continue"
        )
        self.assertEqual(error.error_type, HookErrorType.DEPENDENCY_UNAVAILABLE)


class TestInfrastructureError(unittest.TestCase):
    """Red tests: InfrastructureError subclass with default severity."""

    def test_infrastructure_error_exists(self):
        """GIVEN hook error handling
        WHEN InfrastructureError is accessed
        THEN it exists and is a HookError subclass."""
        self.assertTrue(issubclass(InfrastructureError, HookError))

    def test_infrastructure_error_has_critical_severity(self):
        """GIVEN InfrastructureError is raised
        WHEN inspecting severity
        THEN default severity is "critical" (non-recoverable)."""
        error = InfrastructureError(
            message="workflow-state.json corrupted",
            recovery_action="manual intervention required"
        )
        self.assertEqual(error.severity, "critical")

    def test_infrastructure_error_has_correct_type(self):
        """GIVEN InfrastructureError is raised
        WHEN inspecting error_type
        THEN error_type is INFRASTRUCTURE_ERROR."""
        error = InfrastructureError(
            message="I/O failure",
            recovery_action="check disk space and permissions"
        )
        self.assertEqual(error.error_type, HookErrorType.INFRASTRUCTURE_ERROR)


class TestHookErrorRecoveryAction(unittest.TestCase):
    """Red tests: Recovery actions are specific and actionable."""

    def test_contract_violation_recovery_action(self):
        """GIVEN ContractViolationError with recovery_action
        WHEN recovery_action is provided
        THEN it guides how to resolve the contract mismatch."""
        error = ContractViolationError(
            message="missing design_findings in output",
            recovery_action="re-run agent-tdd with updated design spec"
        )
        self.assertIn("re-run", error.recovery_action.lower())

    def test_dependency_unavailable_recovery_action(self):
        """GIVEN DependencyUnavailableError with recovery_action
        WHEN recovery_action is provided
        THEN it guides how to degrade gracefully."""
        error = DependencyUnavailableError(
            message="agent-nelly temporary unavailable",
            recovery_action="continue workflow with empty nelly brief cache"
        )
        self.assertIn("continue", error.recovery_action.lower())

    def test_infrastructure_error_recovery_action(self):
        """GIVEN InfrastructureError with recovery_action
        WHEN recovery_action is provided
        THEN it guides manual intervention."""
        error = InfrastructureError(
            message="permission denied on workflow-state.json",
            recovery_action="check file permissions: chmod 600 ~/.claude/sdd-memory/*/workflow-state.json"
        )
        self.assertIn("permission", error.recovery_action.lower())


if __name__ == '__main__':
    unittest.main()
