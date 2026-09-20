#!/usr/bin/env python3
"""Tests that shared/AGENT-MODEL-TIERS.md formalizes agent frontmatter
`model:` field semantics consistently across plugins (Task 6: Agent
Frontmatter Documentation & Semantics)."""
import unittest
from pathlib import Path

DOC_PATH = Path(__file__).parent / "AGENT-MODEL-TIERS.md"

EXPECTED_VALUES = ["inherit", "haiku", "sonnet", "opus", "fable-5-1"]


class TestAgentModelTiersDoc(unittest.TestCase):
    def setUp(self):
        self.content = DOC_PATH.read_text() if DOC_PATH.exists() else ""

    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.exists(), "shared/AGENT-MODEL-TIERS.md not found")

    def test_documents_all_frontmatter_values(self):
        for value in EXPECTED_VALUES:
            self.assertIn(
                value,
                self.content,
                f"AGENT-MODEL-TIERS.md does not document model value '{value}'",
            )

    def test_documents_semantics_of_fixed_tier(self):
        # Each concrete tier value (not "inherit") means the agent always
        # runs at that model, regardless of caller-level model settings.
        self.assertIn("always", self.content.lower())

    def test_includes_frontmatter_example(self):
        # At least one worked frontmatter example block.
        self.assertIn("model:", self.content)
        self.assertIn("---", self.content)

    def test_does_not_instruct_changing_existing_agent_frontmatter(self):
        # This is purely additive documentation; it must not tell readers to
        # go edit already-shipped agents' frontmatter values.
        self.assertNotIn("change the existing", self.content.lower())


if __name__ == "__main__":
    unittest.main()
