"""Tests that references/slice-spec.schema.json is valid JSON Schema and
stays in sync with the Slice Spec contract documented in INTEROP.md (the two
required fields, three enums, and the full set of seven properties).
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "references" / "slice-spec.schema.json"

EXPECTED_PROPERTIES = {
    "taskDescription",
    "acceptanceCriteria",
    "riskTier",
    "modelTier",
    "dataContractsAndInterfaces",
    "preSliceBrief",
    "reviewHandoffMode",
}
EXPECTED_REQUIRED = {"taskDescription", "acceptanceCriteria"}


def _load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestSliceSpecSchemaIsValidJson(unittest.TestCase):
    def test_schema_file_parses_as_json(self):
        schema = _load_schema()
        self.assertEqual(schema.get("type"), "object")


class TestSliceSpecSchemaMatchesContract(unittest.TestCase):
    def test_declares_all_slice_spec_fields(self):
        schema = _load_schema()
        properties = set(schema.get("properties", {}).keys())
        self.assertEqual(properties, EXPECTED_PROPERTIES)

    def test_only_task_description_and_acceptance_criteria_are_required(self):
        schema = _load_schema()
        required = set(schema.get("required", []))
        self.assertEqual(required, EXPECTED_REQUIRED)

    def test_risk_tier_enum_matches_documented_values(self):
        schema = _load_schema()
        risk_tier = schema["properties"]["riskTier"]
        self.assertEqual(set(risk_tier["enum"]), {"standard", "high-risk"})
        self.assertEqual(risk_tier.get("default"), "standard")

    def test_review_handoff_mode_enum_matches_documented_values(self):
        schema = _load_schema()
        review_mode = schema["properties"]["reviewHandoffMode"]
        self.assertEqual(set(review_mode["enum"]), {"pause", "skip"})
        self.assertEqual(review_mode.get("default"), "pause")

    def test_model_tier_enum_matches_documented_values(self):
        schema = _load_schema()
        model_tier = schema["properties"]["modelTier"]
        self.assertEqual(set(model_tier["enum"]), {"inherit", "haiku", "sonnet", "opus"})
        self.assertEqual(model_tier.get("default"), "inherit")

    def test_rejects_unknown_properties(self):
        schema = _load_schema()
        self.assertIs(schema.get("additionalProperties"), False)


if __name__ == "__main__":
    unittest.main()
