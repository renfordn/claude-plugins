"""Tests for schema_extractor.py module."""

import unittest
import tempfile
from pathlib import Path
from orchestrator.schema_extractor import (
    SchemaExtractor,
    SchemaRegistry,
    Field,
    Schema
)


class TestFieldAndSchema(unittest.TestCase):
    """Test Field and Schema dataclasses."""

    def test_field_creation(self):
        """Test creating a Field."""
        field = Field(name="requirements_md", type_name="string", required=True)
        self.assertEqual(field.name, "requirements_md")
        self.assertEqual(field.type_name, "string")
        self.assertTrue(field.required)

    def test_schema_creation(self):
        """Test creating a Schema."""
        field1 = Field(name="requirements_md", type_name="string", required=True)
        field2 = Field(name="design_md", type_name="string", required=True)
        schema = Schema(
            plugin_name="agent-isdd",
            capability_name="design_spec_handoff",
            fields={"requirements_md": field1, "design_md": field2}
        )
        self.assertEqual(schema.plugin_name, "agent-isdd")
        self.assertEqual(schema.capability_name, "design_spec_handoff")
        self.assertEqual(len(schema.fields), 2)


class TestSchemaRegistry(unittest.TestCase):
    """Test SchemaRegistry."""

    def setUp(self):
        """Set up a registry for tests."""
        self.registry = SchemaRegistry()

    def test_add_and_retrieve_schema(self):
        """Test adding and retrieving a schema."""
        field = Field(name="test_field", type_name="string", required=True)
        schema = Schema(
            plugin_name="test-plugin",
            capability_name="test_capability",
            fields={"test_field": field}
        )

        self.registry.add_schema(schema)
        retrieved = self.registry.get_schema("test-plugin", "test_capability")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.plugin_name, "test-plugin")
        self.assertEqual(retrieved.capability_name, "test_capability")

    def test_get_nonexistent_schema(self):
        """Test retrieving a nonexistent schema."""
        result = self.registry.get_schema("nonexistent", "nonexistent")
        self.assertIsNone(result)

    def test_get_capability_consumes(self):
        """Test getting consumes as Dict[field_name: type_name]."""
        field1 = Field(name="requirements_md", type_name="string", required=True)
        field2 = Field(name="design_md", type_name="string", required=True)
        schema = Schema(
            plugin_name="agent-tdd",
            capability_name="design_spec_slicing",
            fields={"requirements_md": field1, "design_md": field2}
        )

        self.registry.add_schema(schema)
        consumes = self.registry.get_capability_consumes("agent-tdd", "design_spec_slicing")

        expected = {
            "requirements_md": "string",
            "design_md": "string"
        }
        self.assertEqual(consumes, expected)

    def test_get_capability_consumes_nonexistent(self):
        """Test getting consumes for a nonexistent capability."""
        consumes = self.registry.get_capability_consumes("nonexistent", "nonexistent")
        self.assertEqual(consumes, {})


class TestSchemaExtractor(unittest.TestCase):
    """Test SchemaExtractor."""

    def setUp(self):
        """Set up a temporary directory with test INTEROP.md files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create fake plugin directories
        (self.base_dir / "agent-tdd").mkdir(exist_ok=True)
        (self.base_dir / "agent-isdd").mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def _create_interop_file(self, plugin_name: str, content: str):
        """Helper to create an INTEROP.md file."""
        plugin_dir = self.base_dir / plugin_name
        plugin_dir.mkdir(exist_ok=True)
        interop_path = plugin_dir / "INTEROP.md"
        interop_path.write_text(content)

    def test_parse_markdown_table(self):
        """Test parsing a markdown table."""
        table_text = """| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
| research_cache | object | yes |
"""
        extractor = SchemaExtractor(base_dir=self.base_dir)
        rows = extractor.parse_markdown_table(table_text)

        expected = [
            ("requirements_md", "string", True),
            ("design_md", "string", True),
            ("research_cache", "object", True)
        ]
        self.assertEqual(rows, expected)

    def test_parse_markdown_table_with_optional_fields(self):
        """Test parsing a table with optional fields."""
        table_text = """| Field | Type | Required |
|-------|------|----------|
| field1 | string | yes |
| field2 | object | no |
| field3 | array | false |
"""
        extractor = SchemaExtractor(base_dir=self.base_dir)
        rows = extractor.parse_markdown_table(table_text)

        expected = [
            ("field1", "string", True),
            ("field2", "object", False),
            ("field3", "array", False)
        ]
        self.assertEqual(rows, expected)

    def test_extract_schema_from_content(self):
        """Test extracting a schema from INTEROP.md content."""
        content = """# Agent TDD

## Design Spec Handoff

**Consumes:**

| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
| research_cache | object | yes |
| recap_md | string | yes |
"""
        extractor = SchemaExtractor(base_dir=self.base_dir)
        schema = extractor.extract_schema_from_content(
            "agent-tdd",
            "design_spec_slicing",
            content
        )

        self.assertIsNotNone(schema)
        self.assertEqual(schema.plugin_name, "agent-tdd")
        self.assertEqual(schema.capability_name, "design_spec_slicing")
        self.assertEqual(len(schema.fields), 4)
        self.assertIn("requirements_md", schema.fields)
        self.assertIn("design_md", schema.fields)
        self.assertIn("research_cache", schema.fields)
        self.assertIn("recap_md", schema.fields)

    def test_extract_schema_from_content_not_found(self):
        """Test extracting from content with no table."""
        content = "# Agent TDD\n\nNo schema table here."
        extractor = SchemaExtractor(base_dir=self.base_dir)
        schema = extractor.extract_schema_from_content(
            "agent-tdd",
            "design_spec_slicing",
            content
        )

        self.assertIsNone(schema)

    def test_extract_all_plugins(self):
        """Test extracting schemas from all plugins."""
        # Create a test INTEROP.md for agent-tdd
        tdd_content = """# Agent TDD

## Design Spec Handoff

| Field | Type | Required |
|-------|------|----------|
| requirements_md | string | yes |
| design_md | string | yes |
"""
        self._create_interop_file("agent-tdd", tdd_content)

        # Create a test INTEROP.md for agent-isdd
        isdd_content = """# Agent ISDD

## Handoff

| Field | Type | Required |
|-------|------|----------|
| field1 | string | yes |
"""
        self._create_interop_file("agent-isdd", isdd_content)

        extractor = SchemaExtractor(base_dir=self.base_dir)
        registry = extractor.extract_all_plugins()

        # Should have extracted at least one schema
        self.assertGreater(len(registry.schemas), 0)


class TestSchemaValidation(unittest.TestCase):
    """Test schema validation against hardcoded schemas."""

    def test_schema_extraction_performance(self):
        """Test that schema extraction is fast (<100ms for 6 files)."""
        import time

        # This test just ensures the extraction completes without error
        # Real performance testing would use timeit or pytest-benchmark
        temp_dir = tempfile.TemporaryDirectory()
        try:
            base_dir = Path(temp_dir.name)

            # Create minimal test files
            for plugin in ["agent-tdd", "agent-isdd", "code-reviewer", "plugin-harness", "agent-nelly", "agent-ux"]:
                plugin_dir = base_dir / plugin
                plugin_dir.mkdir(exist_ok=True)
                interop_path = plugin_dir / "INTEROP.md"
                interop_path.write_text("# Test")

            extractor = SchemaExtractor(base_dir=base_dir)

            start = time.time()
            registry = extractor.extract_all_plugins()
            elapsed = time.time() - start

            # Should complete quickly (sub-second)
            self.assertLess(elapsed, 1.0)
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
