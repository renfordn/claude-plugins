"""Tests for interop_drift_validator.py module."""

import os
import tempfile
import unittest
from pathlib import Path
from orchestrator.interop_drift_validator import InteropDriftValidator, PreCommitHook


class TestInteropDriftValidator(unittest.TestCase):
    """Test InteropDriftValidator."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.validator = InteropDriftValidator(repo_root=self.repo_root)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_extract_schema_from_text(self):
        """Test extracting schema from INTEROP.md text."""
        text = """# Agent TDD

| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
"""
        schema = self.validator.extract_schema_from_text("agent-tdd", "test_cap", text)

        expected = {
            "requirements_md": "string",
            "design_md": "string"
        }
        self.assertEqual(schema, expected)

    def test_extract_schema_from_text_no_table(self):
        """Test extracting schema when no table found."""
        text = "# Agent TDD\n\nNo schema table here."
        schema = self.validator.extract_schema_from_text("agent-tdd", "test_cap", text)

        self.assertEqual(schema, {})

    def test_compare_schemas_no_changes(self):
        """Test comparing identical schemas."""
        schema = {"field1": "string", "field2": "object"}

        added, removed, mismatches = self.validator.compare_schemas(schema, schema)

        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(mismatches, [])

    def test_compare_schemas_added_fields(self):
        """Test comparing schemas with added fields."""
        before = {"field1": "string"}
        after = {"field1": "string", "field2": "object"}

        added, removed, mismatches = self.validator.compare_schemas(before, after)

        self.assertEqual(added, ["field2"])
        self.assertEqual(removed, [])
        self.assertEqual(mismatches, [])

    def test_compare_schemas_removed_fields(self):
        """Test comparing schemas with removed fields."""
        before = {"field1": "string", "field2": "object"}
        after = {"field1": "string"}

        added, removed, mismatches = self.validator.compare_schemas(before, after)

        self.assertEqual(added, [])
        self.assertEqual(removed, ["field2"])
        self.assertEqual(mismatches, [])

    def test_compare_schemas_type_mismatches(self):
        """Test comparing schemas with type mismatches."""
        before = {"field1": "string"}
        after = {"field1": "object"}

        added, removed, mismatches = self.validator.compare_schemas(before, after)

        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0], ("field1", "string", "object"))

    def test_compare_schemas_multiple_changes(self):
        """Test comparing schemas with multiple changes."""
        before = {
            "requirements_md": "string",
            "design_md": "string",
            "old_field": "boolean"
        }
        after = {
            "requirements_md": "string",
            "design_md": "object",  # type mismatch
            "new_field": "array"    # added
        }

        added, removed, mismatches = self.validator.compare_schemas(before, after)

        self.assertIn("new_field", added)
        self.assertIn("old_field", removed)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0][0], "design_md")

    def test_format_error_message(self):
        """Test formatting error messages."""
        errors = [
            "\nSchema Drift Detected: agent-tdd/INTEROP.md\n"
            "  Added fields: phase_md\n"
        ]

        message = self.validator.format_error_message(errors)

        self.assertIn("DRIFT VALIDATION FAILED", message)
        self.assertIn("Schema Drift Detected", message)
        self.assertIn("phase_md", message)
        self.assertIn("ACTION REQUIRED", message)

    def test_sdd_gate_off_escape_hatch(self):
        """Test that SDD_GATE=off bypasses validation."""
        os.environ["SDD_GATE"] = "off"
        try:
            is_valid, errors = self.validator.validate_drift()
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])
        finally:
            del os.environ["SDD_GATE"]


class TestPreCommitHook(unittest.TestCase):
    """Test PreCommitHook."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.hook = PreCommitHook(repo_root=self.repo_root)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_should_intercept_git_commit(self):
        """Test intercepting git commit command."""
        self.assertTrue(self.hook.should_intercept("git commit -m 'test'"))
        self.assertTrue(self.hook.should_intercept("git commit"))
        self.assertTrue(self.hook.should_intercept("git commit --amend"))

    def test_should_not_intercept_other_commands(self):
        """Test not intercepting other commands."""
        self.assertFalse(self.hook.should_intercept("git push"))
        self.assertFalse(self.hook.should_intercept("git status"))
        self.assertFalse(self.hook.should_intercept("git add"))
        self.assertFalse(self.hook.should_intercept("echo 'hello'"))

    def test_validate_commit_when_no_changes(self):
        """Test validation passes when no INTEROP changes."""
        # In a non-git repo or repo with no staged changes,
        # validation should pass (no error)
        allowed, error_msg = self.hook.validate_commit()

        # Should be allowed (no INTEROP files staged)
        self.assertTrue(allowed)
        self.assertIsNone(error_msg)


class TestSchemaDriftScenarios(unittest.TestCase):
    """Test realistic drift scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.validator = InteropDriftValidator(repo_root=self.repo_root)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_scenario_adding_required_field(self):
        """Test scenario: adding a required field to INTEROP.md."""
        before_schema = {
            "requirements_md": "string",
            "design_md": "string"
        }

        after_schema = {
            "requirements_md": "string",
            "design_md": "string",
            "research_cache": "object"
        }

        added, removed, mismatches = self.validator.compare_schemas(before_schema, after_schema)

        # Drift detected
        self.assertIn("research_cache", added)

    def test_scenario_removing_optional_field(self):
        """Test scenario: removing an optional field."""
        before_schema = {
            "field1": "string",
            "field2": "string"
        }

        after_schema = {
            "field1": "string"
        }

        added, removed, mismatches = self.validator.compare_schemas(before_schema, after_schema)

        # Drift detected
        self.assertIn("field2", removed)

    def test_scenario_changing_field_type(self):
        """Test scenario: changing a field type."""
        before_schema = {
            "research_cache": "object"
        }

        after_schema = {
            "research_cache": "array"
        }

        added, removed, mismatches = self.validator.compare_schemas(before_schema, after_schema)

        # Drift detected
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0][0], "research_cache")


if __name__ == "__main__":
    unittest.main()
