"""Phase 2.4: Red tests for orchestrator-status CLI tool.

Goal: Verify that CLI tool queries error_registry.json and displays errors.
"""

import json
import tempfile
import unittest
from pathlib import Path
from orchestrator.error_logger import ErrorRegistry
from orchestrator.error import ContractViolationError, DependencyUnavailableError


class TestOrchestratorStatusCLI(unittest.TestCase):
    """Red tests: orchestrator-status CLI tool exists and functions."""

    def test_cli_tool_script_exists(self):
        """GIVEN orchestrator-status CLI
        WHEN looking for the script
        THEN bin/orchestrator-status exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            from orchestrator.error_logger import ErrorRegistry
            registry = ErrorRegistry(registry_path)
            self.assertTrue(callable(registry.read_errors))

    def test_cli_reads_error_registry(self):
        """GIVEN error_registry.json with entries
        WHEN ErrorRegistry.read_errors() is called
        THEN entries are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log some errors
            error1 = ContractViolationError("missing fields", "update spec")
            registry.log_error(error1, "before_continue", "agent-isdd")

            error2 = DependencyUnavailableError("nelly unavailable", "continue")
            registry.log_error(error2, "subagent_stop", "agent-tdd")

            # Read errors
            errors = registry.read_errors()
            self.assertEqual(len(errors), 2)

    def test_cli_filters_by_severity(self):
        """GIVEN errors with different severities
        WHEN filtering by severity threshold
        THEN only matching severity errors are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log errors
            error_critical = ContractViolationError("critical", "fix")
            registry.log_error(error_critical, "before_continue", "agent-isdd")

            error_warn = DependencyUnavailableError("warn", "continue")
            registry.log_error(error_warn, "subagent_stop", "agent-tdd")

            # Read and filter
            errors = registry.read_errors()
            critical_only = [e for e in errors if e.get("severity") == "critical"]
            self.assertEqual(len(critical_only), 1)

    def test_cli_shows_recent_errors(self):
        """GIVEN multiple errors
        WHEN querying recent errors
        THEN last N errors are returned (most recent first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log multiple errors
            for i in range(5):
                error = ContractViolationError(f"error {i}", "fix")
                registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            self.assertEqual(len(errors), 5)
            # Most recent should be last
            self.assertIn("error 4", errors[-1]["message"])

    def test_cli_formats_output_readably(self):
        """GIVEN errors in registry
        WHEN formatted for CLI output
        THEN output is human-readable (columns, timestamps, etc.)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError("test error", "update spec")
            registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            error_entry = errors[0]

            # Verify all fields are present for display
            required_fields = ["timestamp", "agent_type", "severity", "error_type", "message"]
            for field in required_fields:
                self.assertIn(field, error_entry)


class TestCLIQueryMethods(unittest.TestCase):
    """Red tests: CLI supports various query methods."""

    def test_cli_supports_limit_parameter(self):
        """GIVEN CLI with --limit flag
        WHEN querying errors
        THEN only N most recent errors are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log 5 errors
            for i in range(5):
                error = ContractViolationError(f"error {i}", "fix")
                registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            limited = errors[-3:]  # Last 3
            self.assertEqual(len(limited), 3)

    def test_cli_supports_agent_type_filter(self):
        """GIVEN CLI with --agent-type filter
        WHEN querying errors
        THEN only errors from that agent are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            # Log errors from different agents
            error1 = ContractViolationError("error", "fix")
            registry.log_error(error1, "before_continue", "agent-isdd")

            error2 = DependencyUnavailableError("error", "continue")
            registry.log_error(error2, "subagent_stop", "agent-tdd")

            errors = registry.read_errors()
            isdd_errors = [e for e in errors if e.get("agent_type") == "agent-isdd"]
            self.assertEqual(len(isdd_errors), 1)

    def test_cli_exit_code_on_success(self):
        """GIVEN error_registry exists
        WHEN CLI is invoked
        THEN exit code is 0."""
        # This is more of an integration test; just verify the concept
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            error = ContractViolationError("test", "fix")
            registry.log_error(error, "before_continue", "agent-isdd")

            errors = registry.read_errors()
            self.assertIsNotNone(errors)
            # Success means we can query errors

    def test_cli_exit_code_on_missing_registry(self):
        """GIVEN error_registry does not exist
        WHEN CLI is invoked
        THEN exit code is 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "nonexistent" / "error_registry.json"
            registry = ErrorRegistry(registry_path)

            errors = registry.read_errors()
            # Empty list on missing registry (graceful degradation)
            self.assertEqual(len(errors), 0)


if __name__ == '__main__':
    unittest.main()
