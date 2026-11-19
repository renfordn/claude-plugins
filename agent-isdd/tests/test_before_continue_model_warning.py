"""PreToolUse Agent spawning agent-tdd:agent-TDD with a non-sonnet model warns but allows."""
import json
import os
import unittest

import hook_test_utils as h


def _spawn(subagent_type, model=None):
    tool_input = {"subagent_type": subagent_type, "prompt": "Slice Spec"}
    if model is not None:
        tool_input["model"] = model
    return {"tool_name": "Agent", "tool_input": tool_input}


class BeforeContinueModelWarningTests(unittest.TestCase):
    def _msg(self, payload):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            return h.run_hook_message(
                "before_continue.py", dict(payload, cwd=repo), env_extra={"HOME": home}
            )

    def test_opus_spawn_warns_and_allows(self):
        msg, rc = self._msg(_spawn("agent-tdd:agent-TDD", "opus"))
        self.assertEqual(rc, 0)
        self.assertIsNotNone(msg)
        self.assertIn("sonnet", msg.lower())
        self.assertIn("opus", msg.lower())

    def test_sonnet_spawn_is_silent(self):
        msg, rc = self._msg(_spawn("agent-tdd:agent-TDD", "sonnet"))
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_other_agent_with_opus_is_silent(self):
        msg, rc = self._msg(_spawn("agent-isdd:plan-reviewer-tier1", "opus"))
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_test_author_opus_warns_but_test_strategist_is_silent(self):
        msg, _ = self._msg(_spawn("agent-tdd:test-author", "opus"))
        self.assertIsNotNone(msg)
        msg, rc = self._msg(_spawn("agent-tdd:test-strategist", "opus"))
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_wording_is_neutral(self):
        msg, _ = self._msg(_spawn("agent-tdd:agent-TDD", "opus"))
        self.assertIn("default is sonnet", msg)
        self.assertIn("Model Tier", msg)

    def _seed_feature(self, home, repo, state):
        feature_dir = h.feature_spec_dir(home, repo)
        h.seed_state_file(feature_dir, title="F", workflow_status="Implementing")
        path = os.path.join(feature_dir, "workflow-state.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        return path

    def test_rollback_pending_and_opus_spawn_join_both_messages(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            self._seed_feature(
                home, repo, {"rollback_pending": {"target": "Design", "reason": "contradiction"}}
            )
            payload = dict(_spawn("agent-tdd:agent-TDD", "opus"), cwd=repo)
            msg, rc = h.run_hook_message("before_continue.py", payload, env_extra={"HOME": home})
        self.assertEqual(rc, 0)
        self.assertIn("Rollback Pending", msg)
        self.assertIn("default is sonnet", msg)

    def test_spawn_matching_pending_escalation_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            self._seed_feature(
                home, repo, {"escalation_pending": {"reason": "r", "to_model": "Opus"}}
            )
            payload = dict(_spawn("agent-tdd:agent-TDD", "opus"), cwd=repo)
            msg, rc = h.run_hook_message("before_continue.py", payload, env_extra={"HOME": home})
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_escalation_write_preserves_other_keys(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            path = self._seed_feature(home, repo, {"keep": {"a": 1}, "reviewed": {"1": True}})
            transcript = os.path.join(home, "t.jsonl")
            text = (
                '<!--AGENT-TDD-MODEL-ESCALATE: reason="deep" from_model="Haiku" '
                'to_model="Sonnet"-->\nx'
            )
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"type": "assistant",
                                     "message": {"role": "assistant", "content": text}}) + "\n")
            h.run_hook_message(
                "before_continue.py", {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            with open(path) as fh:
                state = json.load(fh)
        self.assertEqual(state["keep"], {"a": 1})
        self.assertEqual(state["reviewed"], {"1": True})
        self.assertEqual(state["escalation_pending"]["to_model"], "Sonnet")

    def test_warning_never_denies(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = h.run_hook(
                "before_continue.py",
                dict(_spawn("agent-tdd:agent-TDD", "opus"), cwd=repo),
                env_extra={"HOME": home},
            )
        self.assertEqual(rc, 0)
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
