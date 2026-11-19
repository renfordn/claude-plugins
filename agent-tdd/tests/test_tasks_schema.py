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


class TestSliceContractFields(unittest.TestCase):
    """Optional fields for parallel-slice delivery: contract kind, test_files, shared_files, wave."""

    def setUp(self):
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "references", "tasks-schema.json"
        )
        with open(schema_path) as f:
            self.schema = json.load(f)
        self.items = self.schema["properties"]["tasks"]["items"]
        self.props = self.items["properties"]

    def _slice(self, **extra):
        base = {
            "number": 1,
            "title": "t",
            "risk_tier": "standard",
            "files": ["a.py"],
            "test_intent": "x",
            "validation_target": "pytest",
            "ordered_steps": ["s"],
        }
        base.update(extra)
        return {"tasks": [base]}

    def _errors(self, doc):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        return list(jsonschema.Draft7Validator(self.schema).iter_errors(doc))

    def test_kind_enum_includes_validation(self):
        self.assertIn("validation", self.props["kind"]["enum"])
        self.assertEqual(self._errors(self._slice(kind="validation")), [])

    def test_kind_enum_includes_contract(self):
        self.assertIn("contract", self.props["kind"]["enum"])
        self.assertEqual(self._errors(self._slice(kind="contract")), [])

    def test_new_fields_declared_optional_and_described(self):
        for name in ("test_files", "shared_files", "wave"):
            self.assertIn(name, self.props)
            self.assertNotIn(name, self.items["required"])
            self.assertTrue(self.props[name].get("description"))
        self.assertIs(self.items["additionalProperties"], False)

    def test_new_fields_accepted(self):
        doc = self._slice(test_files=["t.py"], shared_files=["hooks.json"], wave=0)
        self.assertEqual(self._errors(doc), [])

    def test_slice_without_new_fields_still_valid(self):
        self.assertEqual(self._errors(self._slice()), [])

    def test_wave_must_be_non_negative_integer(self):
        self.assertEqual(self.props["wave"]["type"], "integer")
        self.assertEqual(self.props["wave"]["minimum"], 0)
        for bad in ("1", 1.5, -1):
            self.assertNotEqual(self._errors(self._slice(wave=bad)), [], bad)


class TestTasksFormatExtraction(unittest.TestCase):
    def test_pointer_and_report_fields(self):
        base = os.path.join(os.path.dirname(__file__), "..")
        agent = open(os.path.join(base, "agents", "agent-TDD.md")).read()
        fmt = open(os.path.join(base, "references", "tasks-format.md")).read()
        self.assertIn("Read `references/tasks-format.md` when writing tasks.md", agent)
        for needle in ("Readiness Verdict", "Tasks File Path", "Validation Summary", "<!--AGENT-TDD-REPORT-->"):
            self.assertIn(needle, fmt)


if __name__ == "__main__":
    unittest.main()
