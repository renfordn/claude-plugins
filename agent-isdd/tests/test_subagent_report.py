"""Tests for hooks/subagent_report.py.

New test design (no prior ad-hoc coverage this session) -- the most complex of the five new
tests: JSONL transcript parsing plus two independent report-detection paths (explicit marker,
keyword fallback).
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


def _assistant_block_line(text):
    return json.dumps({
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    })


def _user_line(content):
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}})


class SubagentReportTests(unittest.TestCase):
    def _log_path(self, feature_dir):
        return os.path.join(feature_dir, "recap", "subagent-reports.md")

    def test_no_active_state_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line("<!--SDD-REPORT:tdd-planner-->\nDone.")])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

    def test_explicit_marker_report_is_appended(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line("<!--SDD-REPORT:tdd-planner-->\nImplemented the thing.")],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            with open(self._log_path(feature_dir)) as fh:
                logged = fh.read()
            self.assertIn("Implemented the thing.", logged)

    def test_keyword_fallback_list_block_content_is_appended(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_block_line("Final handoff: acceptance criteria all met.")],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            with open(self._log_path(feature_dir)) as fh:
                logged = fh.read()
            self.assertIn("Final handoff", logged)

    def test_non_report_text_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(transcript, [_assistant_line("Just some ordinary chit-chat.")])
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            self.assertFalse(os.path.exists(self._log_path(feature_dir)))

    def test_malformed_jsonl_line_is_skipped_valid_line_still_found(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [
                    _assistant_line("<!--SDD-REPORT:tdd-planner-->\nPlan ready."),
                    "not valid json {{{",
                    _user_line("thanks"),
                ],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            with open(self._log_path(feature_dir)) as fh:
                logged = fh.read()
            self.assertIn("Plan ready.", logged)

    def test_rollback_marker_writes_rollback_pending_and_md_line(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line(
                    '<!--SDD-ROLLBACK-REQUEST: target=Design reason="the interface was wrong"-->\n'
                    "Green->Refactor review found a design-level issue."
                )],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertEqual(state["rollback_pending"]["target"], "Design")
            self.assertEqual(state["rollback_pending"]["reason"], "the interface was wrong")
            self.assertEqual(state["rollback_pending"]["source"], "agent-tdd")

            md_path = os.path.join(feature_dir, "workflow-state.md")
            with open(md_path) as fh:
                md_text = fh.read()
            self.assertIn("Pending Rollback Request", md_text)
            self.assertIn("Design", md_text)

    def test_rollback_marker_with_invalid_target_is_ignored(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line(
                    '<!--SDD-ROLLBACK-REQUEST: target=NotAPhase reason="bogus"-->\nchit-chat'
                )],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            with open(json_path) as fh:
                state = json.load(fh)
            self.assertNotIn("rollback_pending", state)

    def test_plan_validity_flag_marker_writes_rollback_pending_defaulted_to_requirements(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line(
                    "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                    '<!--AGENT-TDD-PLAN-FLAG:reason="acceptance criteria contradicts existing '
                    'tested behavior"-->\nGreen work surfaced a conflict."'
                )],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)

            with open(json_path) as fh:
                state = json.load(fh)
            self.assertEqual(state["rollback_pending"]["target"], "Requirements")
            self.assertIn(
                "acceptance criteria contradicts existing tested behavior",
                state["rollback_pending"]["reason"],
            )
            self.assertEqual(state["rollback_pending"]["source"], "agent-tdd")

    def test_agent_tdd_report_without_plan_flag_is_not_treated_as_rollback(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line(
                    "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                    "Implemented the counter reset behavior with a targeted unit test."
                )],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            with open(json_path) as fh:
                state = json.load(fh)
            self.assertNotIn("rollback_pending", state)

    def test_rollback_marker_without_active_state_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            transcript = os.path.join(home, "transcript.jsonl")
            _write_transcript(
                transcript,
                [_assistant_line(
                    '<!--SDD-ROLLBACK-REQUEST: target=Tasks reason="oops"-->\nreview note'
                )],
            )
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)

    def test_missing_transcript_file_is_silent_no_crash(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": os.path.join(home, "does-not-exist.jsonl")},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
