import json
import os
import unittest


class TestTasksSchemaIsValidJson(unittest.TestCase):
    """Verify tasks-schema.json is syntactically valid JSON."""

    def test_schema_file_parses_as_json(self):
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "references",
            "tasks-schema.json",
        )
        with open(schema_path) as f:
            schema = json.load(f)
        self.assertIsInstance(schema, dict)
        self.assertIn("$schema", schema)


class TestTasksSchemaMatchesContract(unittest.TestCase):
    """Verify tasks-schema.json documents the expected fields and constraints."""

    def setUp(self):
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "references",
            "tasks-schema.json",
        )
        with open(schema_path) as f:
            self.schema = json.load(f)

    def test_declares_all_task_slice_fields(self):
        """Verify schema declares required fields for each task slice."""
        items_schema = self.schema["properties"]["tasks"]["items"]
        required_fields = items_schema["required"]

        expected_required = [
            "number",
            "title",
            "risk_tier",
            "files",
            "test_intent",
            "validation_target",
            "ordered_steps",
        ]

        for field in expected_required:
            self.assertIn(
                field,
                required_fields,
                f"Required field '{field}' missing from tasks-schema.json",
            )

    def test_risk_tier_enum_matches_documented_values(self):
        """Verify risk_tier enum has exactly the documented values."""
        items_schema = self.schema["properties"]["tasks"]["items"]
        risk_tier_schema = items_schema["properties"]["risk_tier"]

        expected_values = ["standard", "high-risk"]
        self.assertEqual(
            risk_tier_schema["enum"],
            expected_values,
            f"risk_tier enum mismatch: expected {expected_values}, got {risk_tier_schema['enum']}",
        )

    def test_depends_on_is_optional(self):
        """Verify depends_on is optional (not in required list)."""
        items_schema = self.schema["properties"]["tasks"]["items"]
        required_fields = items_schema["required"]

        self.assertNotIn("depends_on", required_fields)

    def test_notes_is_optional(self):
        """Verify notes is optional (not in required list)."""
        items_schema = self.schema["properties"]["tasks"]["items"]
        required_fields = items_schema["required"]

        self.assertNotIn("notes", required_fields)

    def test_schema_rejects_unknown_properties(self):
        """Verify schema enforces no additional properties on task slices."""
        items_schema = self.schema["properties"]["tasks"]["items"]

        # Check if additionalProperties is set
        if "additionalProperties" in items_schema:
            self.assertFalse(
                items_schema["additionalProperties"],
                "Schema should not allow additional properties on task slices",
            )


if __name__ == "__main__":
    unittest.main()
