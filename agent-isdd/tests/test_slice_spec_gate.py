"""Tests for hooks/slice_spec_gate.py.

New PreToolUse hard-deny gate (2026-08-12, ISDD Sibling-Plugin Hook Reliability feature,
Phase 4): the Implementation Handoff's one cleanly-interceptable, narrowly-scoped tool call
-- spawning agent-tdd:agent-TDD or agent-tdd:test-author via the Task tool. Mirrors
commit_audit_gate.py's verify-then-allow/deny pattern, but scoped to exactly two
subagent_type values so it can't misfire on unrelated Task calls. High-risk per tasks.md:
a false positive here blocks a legitimate handoff, so every required-field case gets its
own test.
"""
import unittest

import hook_test_utils as h

COMPLETE_PROMPT = """
Objective: Implement the thing.
Ordered Steps:
1. Write a failing test.
2. Make it pass.
Test Intent: Add tests/test_thing.py covering the happy path.
Risk Tier: standard
Data Contracts And Interfaces: ThingService.do_thing(x) -> bool
"""


def _prompt_without(section_line):
    lines = [l for l in COMPLETE_PROMPT.splitlines() if section_line not in l]
    return "\n".join(lines)


class SliceSpecGateTests(unittest.TestCase):
    def _call(self, subagent_type, prompt):
        return h.run_hook(
            "slice_spec_gate.py",
            {"tool_input": {"subagent_type": subagent_type, "prompt": prompt}},
        )

    def test_unrelated_subagent_type_is_noop(self):
        decision, rc = self._call("agent-isdd:planning-agent", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNone(decision)

    def test_complete_slice_spec_is_allowed(self):
        decision, rc = self._call("agent-tdd:agent-TDD", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_test_author_subagent_type_is_also_gated(self):
        decision, rc = self._call("agent-tdd:test-author", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_missing_objective_is_denied(self):
        decision, rc = self._call("agent-tdd:agent-TDD", _prompt_without("Objective:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Objective", decision["permissionDecisionReason"])

    def test_missing_test_intent_is_denied(self):
        decision, rc = self._call("agent-tdd:agent-TDD", _prompt_without("Test Intent:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Test Intent", decision["permissionDecisionReason"])

    def test_missing_risk_tier_is_denied(self):
        decision, rc = self._call("agent-tdd:agent-TDD", _prompt_without("Risk Tier:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Risk Tier", decision["permissionDecisionReason"])

    def test_missing_data_contracts_is_denied(self):
        decision, rc = self._call("agent-tdd:agent-TDD", _prompt_without("Data Contracts"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Data Contracts", decision["permissionDecisionReason"])

    def test_malformed_payload_is_noop(self):
        decision, rc = h.run_hook("slice_spec_gate.py", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
