"""Tests for subagent_report.py's main() wiring of escalation-outcome classification
(Task 3.2, high-risk): must fire only when escalation_pending is present AND the report is
agent-tdd-shaped, must not disturb the existing rollback-marker/generic-report paths, and must
leave escalation_pending alone when either precondition is unmet.
"""
import json
import os
import unittest

import hook_test_utils as h


def _write_transcript(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")


def _assistant_line(content):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})


class EscalationWiringTests(unittest.TestCase):
    def _seed_escalation_pending(self, json_path, extra=None):
        pending = {"reason": "context limit", "from_model": "haiku", "to_model": "sonnet",
                   "detected_at": "2026-09-19T00:00:00"}
        data = {"current_phase": "Implementation", "escalation_pending": pending}
        if extra:
            data.update(extra)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return pending

    def test_succeeded_outcome_recorded_and_pending_cleared(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            self._seed_escalation_pending(json_path)

            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line(
                "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:all_slices_complete-->\n"
                "All tests passing. Feature complete."
            )])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("succeeded", msg.lower())

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertNotIn("escalation_pending", state)
            self.assertEqual(len(state["escalation_history"]), 1)
            self.assertEqual(state["escalation_history"][0]["outcome"], "succeeded")

    def test_failed_outcome_and_rollback_pending_both_fire(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            self._seed_escalation_pending(json_path)

            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line(
                "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                "All tests passing.\n"
                '<!--SDD-ROLLBACK-REQUEST: target=Design reason="interface wrong"-->\n'
            )])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertNotIn("escalation_pending", state)
            self.assertEqual(state["escalation_history"][0]["outcome"], "failed")
            # existing rollback_pending write must still fire, unchanged
            self.assertEqual(state["rollback_pending"]["target"], "Design")
            self.assertEqual(state["rollback_pending"]["reason"], "interface wrong")

    def test_no_agent_tdd_phase_marker_skips_classification_entirely(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            pending = self._seed_escalation_pending(json_path)

            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line(
                "<!--SDD-REPORT:spec-reviewer-->\nVerdict: acceptance criteria all met."
            )])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertEqual(state["escalation_pending"], pending)
            self.assertNotIn("escalation_history", state)

    def test_no_escalation_pending_behaves_exactly_as_before(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line(
                "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                "Implemented the counter reset behavior with a targeted unit test."
            )])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertNotIn("escalation_pending", state)
            self.assertNotIn("escalation_history", state)
            self.assertNotIn("rollback_pending", state)


if __name__ == "__main__":
    unittest.main()
