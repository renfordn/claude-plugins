"""Smoke end-to-end tests against the REAL plugin contracts.

Unlike the rest of the suite (which validates parser/router mechanics against
tests/fixtures INTEROP.md stubs — see the "Test fixture note" in each fixture
file), these tests point CapabilityMap at the actual repo root and load the
real agent-isdd/, agent-tdd/, code-reviewer/, agent-nelly/, agent-ux/
INTEROP.md files. This catches drift between the router's expectations and
what the real contracts currently say (e.g. a renamed capability or field)
that a fixture-only run would never surface.
"""

import unittest
from pathlib import Path

from orchestrator.core import PluginRouter
from orchestrator.interop_parser import CapabilityMap

REPO_ROOT = Path(__file__).parent.parent.parent


class TestRealContractsParse(unittest.TestCase):
    """The real INTEROP.md files must parse into a usable CapabilityMap."""

    @classmethod
    def setUpClass(cls):
        cls.capability_map = CapabilityMap(str(REPO_ROOT))
        cls.router = PluginRouter(cls.capability_map)

    def test_all_declared_plugins_parsed(self):
        for name in CapabilityMap.PLUGIN_PATHS:
            with self.subTest(plugin=name):
                self.assertIsNotNone(
                    self.capability_map.get_plugin(name),
                    f"{name} did not parse from its real INTEROP.md/STRUCTURE.md",
                )

    def test_hard_dependencies_have_capabilities(self):
        for name in ("agent-isdd", "agent-tdd", "code-reviewer"):
            plugin = self.capability_map.get_plugin(name)
            with self.subTest(plugin=name):
                self.assertTrue(
                    plugin.capabilities,
                    f"{name}'s real INTEROP.md declares no capabilities",
                )

    def test_soft_dependencies_flagged(self):
        for name in ("agent-nelly", "agent-ux"):
            with self.subTest(plugin=name):
                self.assertTrue(self.router.is_soft_dependency(name))
        for name in ("agent-isdd", "agent-tdd", "code-reviewer"):
            with self.subTest(plugin=name):
                self.assertFalse(self.router.is_soft_dependency(name))


class TestRealHandoffChain(unittest.TestCase):
    """isdd -> tdd -> code-reviewer must validate against the real contracts."""

    @classmethod
    def setUpClass(cls):
        cls.capability_map = CapabilityMap(str(REPO_ROOT))
        cls.router = PluginRouter(cls.capability_map)

    def test_isdd_to_tdd_handoff_valid(self):
        payload = {
            "requirements_md": "# Requirements",
            "design_md": "# Design",
            "research_cache": {"findings": []},
            "recap_md": "# Recap",
        }
        is_valid, error = self.router.validate_handoff(
            "agent-isdd", "design_spec_handoff",
            "agent-tdd", "design_spec_slicing",
            payload,
        )
        self.assertTrue(is_valid, error)

    def test_isdd_to_tdd_handoff_missing_field_rejected(self):
        payload = {"requirements_md": "# Requirements"}
        is_valid, error = self.router.validate_handoff(
            "agent-isdd", "design_spec_handoff",
            "agent-tdd", "design_spec_slicing",
            payload,
        )
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_tdd_to_code_reviewer_handoff_valid(self):
        payload = {"sliced_specs": [{"id": "slice-1"}], "implementation": {"files": []}}
        is_valid, error = self.router.validate_handoff(
            "agent-tdd", "design_spec_slicing",
            "code-reviewer", "code_review",
            payload,
        )
        self.assertTrue(is_valid, error)

    def test_full_chain_isdd_tdd_code_reviewer(self):
        isdd_output = {
            "requirements_md": "# Requirements",
            "design_md": "# Design",
            "research_cache": {"findings": []},
            "recap_md": "# Recap",
        }
        is_valid, error = self.router.validate_handoff(
            "agent-isdd", "design_spec_handoff",
            "agent-tdd", "design_spec_slicing",
            isdd_output,
        )
        self.assertTrue(is_valid, error)

        tdd_output = {"sliced_specs": [{"id": "slice-1"}], "implementation": {"files": []}}
        is_valid, error = self.router.validate_handoff(
            "agent-tdd", "design_spec_slicing",
            "code-reviewer", "code_review",
            tdd_output,
        )
        self.assertTrue(is_valid, error)


class TestSoftDependencyDegradation(unittest.TestCase):
    """Absence of agent-nelly / agent-ux in a session must not block routing."""

    @classmethod
    def setUpClass(cls):
        cls.capability_map = CapabilityMap(str(REPO_ROOT))
        cls.router = PluginRouter(cls.capability_map)

    def test_missing_soft_dependency_is_available_false_but_not_hard_error(self):
        system_reminder = "Setup: agent-tdd:agent-TDD available. code-reviewer:code-reviewer available."
        for name in ("agent-nelly", "agent-ux"):
            with self.subTest(plugin=name):
                available = self.router.check_plugin_availability(name, system_reminder)
                self.assertFalse(available)
                self.assertFalse(self.router.is_hard_dependency(name))

    def test_missing_hard_dependency_is_flagged(self):
        system_reminder = "Setup: agent-tdd:agent-TDD available."
        available = self.router.check_plugin_availability("code-reviewer", system_reminder)
        self.assertFalse(available)
        self.assertTrue(self.router.is_hard_dependency("code-reviewer"))


if __name__ == "__main__":
    unittest.main()
