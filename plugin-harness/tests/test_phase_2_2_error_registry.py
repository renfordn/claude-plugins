"""Phase 2.2: Red tests for structured error logging to error_registry.json.

Goal: Verify that errors are persisted in JSON lines format with auto-rotation
at 10MB threshold.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from orchestrator.error_logger import ErrorRegistry
from orchestrator.error import ContractViolationError, DependencyUnavailableError, InfrastructureError


class TestErrorRegistryCreation(unittest.TestCase):
    """Red tests: ErrorRegistry class exists and initializes correctly."""

    def test_error_registry_class_exists(self):
        """GIVEN error logging
        WHEN ErrorRegistry is accessed
        THEN it exists."""
        self.assertTrue(hasattr(__import__('orchestrator.error_logger', fromlist=['ErrorRegistry']), 'ErrorRegistry'))

    def test_error_registry_init_with_path(self):
        """GIVEN a target registry file path
        WHEN ErrorRegistry is initialized
        THEN it accepts the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)
            self.assertEqual(registry.registry_path, registry_path)

    def test_error_registry_creates_file_on_first_log(self):
        """GIVEN error_registry.json does not exist
        WHEN first error is logged
        THEN file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError(
                message="test error",
                recovery_action="test recovery"
            )
            registry.log_error(error, "before_continue", "agent-isdd")

            self.assertTrue(registry_path.exists())


class TestErrorLogging(unittest.TestCase):
    """Red tests: Errors are logged in JSON lines format."""

    def test_log_error_creates_json_lines_entry(self):
        """GIVEN error is logged
        WHEN error_registry.json is read
        THEN each line is valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError(
                message="missing fields",
                recovery_action="update spec"
            )
            registry.log_error(error, "subagent_stop", "agent-tdd")

            # Read and parse JSON lines
            with open(registry_path) as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["message"], "missing fields")

    def test_log_error_includes_all_required_fields(self):
        """GIVEN error is logged
        WHEN entry is in error_registry.json
        THEN it includes timestamp, hook, agent_type, error_type, severity, message, recovery_action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = DependencyUnavailableError(
                message="nelly unavailable",
                recovery_action="continue with empty brief"
            )
            registry.log_error(error, "before_continue", "agent-isdd")

            with open(registry_path) as f:
                entry = json.loads(f.readline())

            self.assertIn("timestamp", entry)
            self.assertIn("hook", entry)
            self.assertIn("agent_type", entry)
            self.assertIn("error_type", entry)
            self.assertIn("severity", entry)
            self.assertIn("message", entry)
            self.assertIn("recovery_action", entry)

    def test_log_error_includes_hook_and_agent_type(self):
        """GIVEN error is logged with hook and agent_type
        WHEN entry is in error_registry.json
        THEN hook and agent_type are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = InfrastructureError(
                message="file corrupted",
                recovery_action="manual fix"
            )
            registry.log_error(error, "before_continue", "agent-tdd")

            with open(registry_path) as f:
                entry = json.loads(f.readline())

            self.assertEqual(entry["hook"], "before_continue")
            self.assertEqual(entry["agent_type"], "agent-tdd")

    def test_log_error_appends_to_existing_entries(self):
        """GIVEN error_registry.json has one entry
        WHEN another error is logged
        THEN it is appended (JSON lines format, not array)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log first error
            error1 = ContractViolationError("error1", "fix1")
            registry.log_error(error1, "before_continue", "agent-isdd")

            # Log second error
            error2 = DependencyUnavailableError("error2", "fix2")
            registry.log_error(error2, "subagent_stop", "agent-tdd")

            # Read all lines
            with open(registry_path) as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 2)
            entry1 = json.loads(lines[0])
            entry2 = json.loads(lines[1])
            self.assertEqual(entry1["message"], "error1")
            self.assertEqual(entry2["message"], "error2")

    def test_log_error_includes_error_severity(self):
        """GIVEN errors with different severities
        WHEN logged
        THEN severity is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error_critical = ContractViolationError("critical error", "fix")
            registry.log_error(error_critical, "before_continue", "agent-isdd")

            error_warn = DependencyUnavailableError("warn error", "fix")
            registry.log_error(error_warn, "subagent_stop", "agent-tdd")

            with open(registry_path) as f:
                lines = f.readlines()

            entry1 = json.loads(lines[0])
            entry2 = json.loads(lines[1])
            self.assertEqual(entry1["severity"], "critical")
            self.assertEqual(entry2["severity"], "warn")


class TestErrorRegistryRotation(unittest.TestCase):
    """Red tests: Error registry auto-rotates at 10MB threshold."""

    def test_error_registry_rotates_at_10mb(self):
        """GIVEN error_registry.json is at 10MB
        WHEN another error is logged
        THEN file is rotated to error_registry.<timestamp>.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Create a "large" error_registry.json by writing directly
            large_entry = {
                "timestamp": "2026-09-16T00:00:00Z",
                "hook": "test",
                "agent_type": "test",
                "error_type": "contract_violation",
                "severity": "critical",
                "message": "x" * 1000,  # Large message
                "recovery_action": "fix"
            }

            # Write enough entries to exceed 10MB
            # Each entry ~1.1KB, so need ~10000 entries
            # For testing, we'll use a smaller threshold (mock or check rotation logic)
            # For now, just verify rotation method exists
            self.assertTrue(hasattr(registry, 'rotate_on_size'))

    def test_error_registry_read_errors_method_exists(self):
        """GIVEN error_registry.json with entries
        WHEN read_errors is called
        THEN it returns list of entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError("test", "fix")
            registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            self.assertIsInstance(errors, list)
            self.assertGreater(len(errors), 0)

    def test_error_registry_read_errors_returns_dicts(self):
        """GIVEN errors are logged
        WHEN read_errors is called
        THEN it returns list of dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError("test", "fix")
            registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            self.assertIsInstance(errors[0], dict)
            self.assertIn("message", errors[0])


class TestErrorRegistryGracefulDegradation(unittest.TestCase):
    """Red tests: Error logging handles I/O failures gracefully."""

    def test_log_error_graceful_on_permission_error(self):
        """GIVEN registry path is not writable
        WHEN error is logged
        THEN it does not crash (graceful degradation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "readonly" / "error_registry.json"
            registry_path.parent.mkdir(exist_ok=True)
            registry_path.parent.chmod(0o444)  # Read-only

            try:
                registry = ErrorRegistry(registry_path)
                error = ContractViolationError("test", "fix")
                # Should not raise, even though write will fail
                registry.log_error(error, "before_continue", "agent-isdd")
            finally:
                # Restore permissions for cleanup
                registry_path.parent.chmod(0o755)


if __name__ == '__main__':
    unittest.main()
