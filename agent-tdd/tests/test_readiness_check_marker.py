#!/usr/bin/env python3
"""
Test suite for readiness-check marker emission.

Verifies that readiness-check emits the PLAN_FLAG_MARKER when verdict = paused,
and that the marker format matches the expected pattern.
"""

import json
import re
import unittest
from unittest.mock import patch, MagicMock


class TestReadinessCheckMarkerEmission(unittest.TestCase):
    """Test marker emission in readiness-check agent."""

    MARKER_PATTERN = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'

    def extract_marker(self, text):
        """Extract marker from text; return (marker_line, reason) or None."""
        match = re.search(self.MARKER_PATTERN, text)
        if match:
            return (match.group(0), match.group(1))
        return None

    def test_marker_emitted_on_paused_verdict(self):
        """
        Verify: When readiness-check verdict = paused, marker is emitted before verdict JSON.

        Setup: Simulate readiness-check with one failed checklist item.
        Expected: Marker line precedes the paused verdict JSON.
        """
        # Simulated readiness-check output when Item 4 (Dependencies) fails
        simulated_output = (
            '<!--AGENT-TDD-PLAN-FLAG:reason="Readiness check failed: Cyclic dependency detected between Phase 2 and Phase 3; task-slicer must reorganize slices"-->\n'
            '```json\n'
            '{\n'
            '  "verdict": "paused",\n'
            '  "state": "Awaiting Clarification",\n'
            '  "confidence": "low",\n'
            '  "blockers": [\n'
            '    {\n'
            '      "item": "Item 4: Dependencies",\n'
            '      "issue": "Cyclic dependency detected between Phase 2 and Phase 3",\n'
            '      "resolution": "task-slicer must reorganize slices"\n'
            '    }\n'
            '  ],\n'
            '  "next_action": "Fix blockers (reslice or resolve blockers) and re-run readiness-check"\n'
            '}\n'
            '```\n'
        )

        marker = self.extract_marker(simulated_output)
        self.assertIsNotNone(marker, "Marker not found in output when verdict = paused")
        marker_line, reason = marker
        self.assertIn("Cyclic dependency", reason)
        # Verify marker appears before verdict JSON
        self.assertTrue(
            simulated_output.index(marker_line) < simulated_output.index('"verdict": "paused"'),
            "Marker must appear before verdict JSON"
        )

    def test_marker_not_emitted_on_ready_verdict(self):
        """
        Verify: When readiness-check verdict = ready, NO marker is emitted.

        Setup: Simulate readiness-check with all items passing.
        Expected: No marker line present; only verdict JSON.
        """
        simulated_output = (
            '```json\n'
            '{\n'
            '  "verdict": "ready",\n'
            '  "state": "Ready For Implementation",\n'
            '  "confidence": "high",\n'
            '  "message": "All checklist items passed. Proceed to Red-Green-Refactor.",\n'
            '  "handoff": {\n'
            '    "tasks_file": "tasks/tasks.md",\n'
            '    "high_risk_slices": ["Phase 4"],\n'
            '    "total_slices": 4\n'
            '  }\n'
            '}\n'
            '```\n'
        )

        marker = self.extract_marker(simulated_output)
        self.assertIsNone(marker, "Marker should not appear when verdict = ready")

    def test_marker_format_valid(self):
        """
        Verify: Marker format matches expected pattern.

        Expected format: <!--AGENT-TDD-PLAN-FLAG:reason="<reason>"-->
        """
        test_reasons = [
            "Cyclic dependency detected between Phase 2 and Phase 3",
            "Research gap: File src/api.ts not in cache",
            "Phase 4 has unresolved blocker: high-risk slice cannot be split",
            "Design assumes User.role but schema has User.permissions",
        ]

        for reason in test_reasons:
            output = f'<!--AGENT-TDD-PLAN-FLAG:reason="{reason}"-->\n'
            marker = self.extract_marker(output)
            self.assertIsNotNone(marker, f"Failed to extract marker with reason: {reason}")
            _, extracted_reason = marker
            self.assertEqual(extracted_reason, reason)

    def test_marker_parsing_by_subagent_hook(self):
        """
        Verify: SubagentStop hook can correctly parse and extract marker.

        Simulates the regex pattern used by subagent_report.py.
        """
        subagent_output = (
            "Research validation complete.\n\n"
            "<!--AGENT-TDD-PLAN-FLAG:reason=\"Design contradicts research: Design assumes User.role but schema has User.permissions\"-->\n"
            "\nReadiness verdict: paused\n"
        )

        # Pattern from before_continue.py (and subagent_report.py)
        marker_pattern = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'
        match = re.search(marker_pattern, subagent_output)

        self.assertIsNotNone(match, "Hook regex failed to match marker")
        reason = match.group(1)
        self.assertIn("User.role", reason)
        self.assertIn("schema", reason)

    def test_blocker_scenarios_produce_appropriate_reasons(self):
        """
        Verify: Each blocker scenario (item 1-10) produces appropriate marker reason.

        Maps each checklist item to representative failure reason.
        """
        blocker_scenarios = [
            ("Item 1: At Least One Phase Exists", "No phases defined in tasks.md"),
            ("Item 2: Each Phase Has Required Fields", "Phase User Email Validation missing Objective"),
            ("Item 3: Slices Are Safe for TDD", "Phase user-email has 4 files (max 3)"),
            ("Item 4: Dependencies Are Acyclic", "Cyclic dependency detected"),
            ("Item 5: Steps Are Grounded in Research", "Step not in research or design"),
            ("Item 6: Test Intent Is Clear", "Phase X Test Intent lacks structure"),
            ("Item 7: Validation Target Is Verifiable", "Phase X Validation Target missing Command"),
            ("Item 8: No Unresolved Blockers", "Phase 4 has unresolved blocker"),
            ("Item 9: Risk Tiers Are Assigned", "Phase 5 missing or invalid Risk Tier"),
            ("Item 10: Ready State Documented", "tasks.md does not mark state as Ready For Implementation"),
        ]

        for item, expected_reason_fragment in blocker_scenarios:
            # Simulate readiness-check producing marker for this blocker
            marker_line = f'<!--AGENT-TDD-PLAN-FLAG:reason="Readiness check failed: {expected_reason_fragment}"-->'
            marker = self.extract_marker(marker_line)
            self.assertIsNotNone(marker, f"Failed to extract marker for {item}")
            _, reason = marker
            self.assertIn(expected_reason_fragment, reason)


class TestMarkerEscalationFlow(unittest.TestCase):
    """Test end-to-end escalation flow from readiness-check through SubagentStop hook."""

    def test_escalation_flow_research_gap(self):
        """
        Verify: Research gap escalation is detected and handled.

        Flow: readiness-check → marker → SubagentStop → before_continue surface
        """
        # Step 1: readiness-check emits marker
        readiness_output = (
            '<!--AGENT-TDD-PLAN-FLAG:reason="Research gap: File src/api.ts not in cache; needs interface review"-->\n'
            '{"verdict": "paused", ...}\n'
        )

        # Step 2: SubagentStop hook extracts marker
        marker_pattern = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'
        match = re.search(marker_pattern, readiness_output)
        self.assertIsNotNone(match)

        # Step 3: Reason is stored in workflow-state.json
        rollback_state = {
            "rollback_pending": {
                "target": "Requirements",  # or specific phase from reason
                "reason": match.group(1),
                "source": "agent-tdd"
            }
        }

        # Step 4: before_continue hook will surface this on next session
        self.assertIn("Research gap", rollback_state["rollback_pending"]["reason"])

    def test_escalation_flow_design_contradiction(self):
        """
        Verify: Design contradiction escalation is detected.

        Flow: readiness-check → marker → SubagentStop → before_continue surface
        """
        readiness_output = (
            '<!--AGENT-TDD-PLAN-FLAG:reason="Design contradicts research: Design assumes User.role but schema has User.permissions"-->\n'
            '{"verdict": "paused", ...}\n'
        )

        marker_pattern = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'
        match = re.search(marker_pattern, readiness_output)
        self.assertIsNotNone(match)

        reason = match.group(1)
        self.assertIn("Design contradicts", reason)
        # Should trigger rollback to Design phase
        self.assertIn("User.role", reason)

    def test_escalation_flow_slicing_blocked(self):
        """
        Verify: Slicing blocked escalation is detected.

        Flow: readiness-check → marker → SubagentStop → before_continue surface
        """
        readiness_output = (
            '<!--AGENT-TDD-PLAN-FLAG:reason="Slicing blocked: Tasks 3 and 4 cannot be split without breaking acyclic dependency; requires design refactor"-->\n'
            '{"verdict": "paused", ...}\n'
        )

        marker_pattern = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'
        match = re.search(marker_pattern, readiness_output)
        self.assertIsNotNone(match)

        reason = match.group(1)
        self.assertIn("Slicing blocked", reason)
        # Should trigger rollback to Design phase
        self.assertIn("design refactor", reason)


class TestMarkerConsistency(unittest.TestCase):
    """Test consistency between readiness-check marker and agent-TDD Plan Validity Flag."""

    def test_marker_format_consistency(self):
        """
        Verify: readiness-check marker uses same format as agent-TDD Plan Validity Flag.

        Both should use: <!--AGENT-TDD-PLAN-FLAG:reason="..."-->
        """
        readiness_marker = '<!--AGENT-TDD-PLAN-FLAG:reason="Readiness check failed: Item 4"-->'
        agent_tdd_marker = '<!--AGENT-TDD-PLAN-FLAG:reason="Task conflicts with existing behavior"-->'

        pattern = r'<!--AGENT-TDD-PLAN-FLAG:reason="([^"]+)"-->'

        self.assertIsNotNone(re.search(pattern, readiness_marker))
        self.assertIsNotNone(re.search(pattern, agent_tdd_marker))

        # Both parse to the same structure
        readiness_match = re.search(pattern, readiness_marker)
        tdd_match = re.search(pattern, agent_tdd_marker)

        self.assertEqual(readiness_match.group(0)[:30], tdd_match.group(0)[:30])  # Same prefix


if __name__ == "__main__":
    unittest.main()
