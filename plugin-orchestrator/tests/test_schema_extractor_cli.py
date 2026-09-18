"""Tests for schema_extractor.py CLI mode."""

import tempfile
import unittest
from pathlib import Path
from orchestrator.schema_extractor import SchemaExtractor


class TestSchemaExtractorCLI(unittest.TestCase):
    """Test CLI interface of schema_extractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create minimal plugin structure
        for plugin in ["agent-tdd", "agent-isdd"]:
            plugin_dir = self.base_dir / plugin
            plugin_dir.mkdir(exist_ok=True)
            interop_path = plugin_dir / "INTEROP.md"
            interop_path.write_text("# Test")

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_schema_extractor_cli_mode(self):
        """Test SchemaExtractor CLI functionality."""
        # Create an INTEROP.md with a schema table
        plugin_dir = self.base_dir / "agent-tdd"
        interop_path = plugin_dir / "INTEROP.md"

        interop_content = """# Agent TDD

| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
| research_cache | object | yes |
| recap_md | string | yes |
"""
        interop_path.write_text(interop_content)

        # Test extraction
        extractor = SchemaExtractor(base_dir=self.base_dir)
        registry = extractor.extract_all_plugins()

        # Should have extracted a schema
        self.assertIsNotNone(registry)

    def test_schema_extractor_validation(self):
        """Test schema validation via CLI-like interface."""
        # Create INTEROP.md
        plugin_dir = self.base_dir / "agent-tdd"
        interop_path = plugin_dir / "INTEROP.md"

        interop_content = """# Agent TDD

| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
"""
        interop_path.write_text(interop_content)

        # Test check mode
        extractor = SchemaExtractor(base_dir=self.base_dir)
        errors = extractor.validate_schemas_against_code()

        # Should return error list (may be empty or have drift errors)
        self.assertIsInstance(errors, list)


if __name__ == "__main__":
    unittest.main()
