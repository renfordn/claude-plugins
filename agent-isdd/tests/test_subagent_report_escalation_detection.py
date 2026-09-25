"""subagent_report.py records a MODEL-ESCALATE marker at agent-TDD's own SubagentStop.

The marker used to be looked for only by before_continue.py in the parent session's transcript,
where agent-TDD's report arrives as a tool result rather than an assistant message, so it was
effectively never seen. The report reaches SubagentStop as last_assistant_message.
"""
import json
import os
import unittest

import hook_test_utils as h

ESCALATE = ('<!--AGENT-TDD-MODEL-ESCALATE: reason="async ordering too subtle" '
            'from_model="Haiku" to_model="Sonnet"-->')


def _assistant_line(text):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": text}})


class EscalationDetectionTests(unittest.TestCase):
    def _run(self, repo, home, report, state=None):
        feature_dir = h.feature_spec_dir(home, repo)
        h.seed_state_file(feature_dir, title="F", workflow_status="Implementing")
        json_path = os.path.join(feature_dir, "workflow-state.json")
        if state is not None:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
        parent = os.path.join(home, "parent.jsonl")
        with open(parent, "w", encoding="utf-8") as fh:
            fh.write(_assistant_line("Spawning agent-TDD.") + "\n")
        msg, rc = h.run_hook_message(
            "subagent_report.py",
            {"cwd": repo, "transcript_path": parent, "last_assistant_message": report},
            env_extra={"HOME": home},
        )
        self.assertEqual(rc, 0)
        with open(json_path, encoding="utf-8") as fh:
            return msg, json.load(fh)

    def test_marker_records_pending_and_tells_caller_to_respawn(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            msg, state = self._run(repo, home,
                                   f"<!--AGENT-TDD-REPORT-->\n{ESCALATE}\nStuck on ordering.")
            pending = state["escalation_pending"]
            self.assertEqual(pending["reason"], "async ordering too subtle")
            self.assertEqual((pending["from_model"], pending["to_model"]), ("Haiku", "Sonnet"))
            self.assertIn("detected_at", pending)
            self.assertIn("get_spawn_context", msg)
            self.assertIn("Sonnet", msg)

    def test_respawn_that_escalates_again_closes_old_and_opens_new(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            old = {"reason": "first", "from_model": "Haiku", "to_model": "Sonnet",
                   "detected_at": "2026-09-25T00:00:00"}
            second = ('<!--AGENT-TDD-MODEL-ESCALATE: reason="still too subtle" '
                      'from_model="Sonnet" to_model="Opus"-->')
            msg, state = self._run(
                repo, home,
                f"<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n{second}",
                state={"escalation_pending": old})
            self.assertEqual(state["escalation_history"][-1]["reason"], "first")
            self.assertEqual(state["escalation_history"][-1]["outcome"], "failed")
            self.assertEqual(state["escalation_pending"]["to_model"], "Opus")
            self.assertIn("Escalation resolved: failed", msg)
            self.assertIn("Opus", msg)

    def test_report_without_marker_records_nothing(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _, state = self._run(repo, home,
                                 "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\nok",
                                 state={})
            self.assertNotIn("escalation_pending", state)


if __name__ == "__main__":
    unittest.main()
