#!/usr/bin/env python3
"""
Tests for high-risk slice code-reviewer auto-invite tracking.

Tests high_risk_reviewer.py functionality for parsing tasks.md,
tracking reviewed slices, and surfacing checkpoints.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

import high_risk_reviewer
import hook_test_utils as h


class ParseAgentTddPhaseTests(unittest.TestCase):
    """Tests for parse_agent_tdd_phase marker parsing."""

    def test_parse_green_pause_marker_returns_true(self):
        """Detect green_pause phase marker and return True."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:green_pause-->\n"
            "Some implementation details here.\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertTrue(is_green_pause)
        self.assertEqual(phase_name, "green_pause")

    def test_parse_refactor_complete_marker_returns_false(self):
        """Detect refactor_complete marker and return False."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:refactor_complete-->\n"
            "Refactoring is done.\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "refactor_complete")

    def test_parse_slicing_complete_marker(self):
        """Detect slicing_complete phase marker."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:slicing_complete-->\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "slicing_complete")

    def test_parse_all_slices_complete_marker(self):
        """Detect all_slices_complete phase marker."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:all_slices_complete-->\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "all_slices_complete")

    def test_missing_marker_returns_false_and_unknown(self):
        """Missing phase marker returns False and 'unknown'."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "Some plan but no phase marker.\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "unknown")

    def test_empty_report_returns_false_and_unknown(self):
        """Empty report returns False and 'unknown'."""
        report = ""
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "unknown")

    def test_malformed_marker_returns_false_and_unknown(self):
        """Malformed marker is ignored, returns False and 'unknown'."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:green_pause\n"  # Missing closing -->
            "Some text.\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "unknown")

    def test_invalid_phase_name_returns_false_and_unknown(self):
        """Unrecognized phase name in marker returns False and 'unknown'."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:invalid_phase-->\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "unknown")

    def test_multiple_markers_uses_first(self):
        """Multiple phase markers present, uses first one."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:green_pause-->\n"
            "Some work here.\n"
            "<!--AGENT-TDD-PHASE:refactor_complete-->\n"  # Second marker ignored
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertTrue(is_green_pause)
        self.assertEqual(phase_name, "green_pause")

    def test_marker_in_middle_of_large_report(self):
        """Marker found correctly in middle of large text."""
        report = (
            "Some long preamble text\n" * 100 +
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:green_pause-->\n" +
            "More text after marker\n" * 50
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertTrue(is_green_pause)
        self.assertEqual(phase_name, "green_pause")

    def test_case_sensitive_phase_name(self):
        """Phase name matching is case-sensitive."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:Green_Pause-->\n"  # Wrong case
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertFalse(is_green_pause)
        self.assertEqual(phase_name, "unknown")

    def test_plan_flag_marker_does_not_interfere(self):
        """Plan flag marker on same report doesn't break phase detection."""
        report = (
            "<!--AGENT-TDD-REPORT-->\n"
            "<!--AGENT-TDD-PHASE:green_pause-->\n"
            "<!--AGENT-TDD-PLAN-FLAG:reason=\"some conflict\"-->\n"
            "Implementation details.\n"
        )
        is_green_pause, phase_name = high_risk_reviewer.parse_agent_tdd_phase(report)
        self.assertTrue(is_green_pause)
        self.assertEqual(phase_name, "green_pause")


class TasksMdParsingTests(unittest.TestCase):
    """Tests for parsing tasks.md and extracting risk tiers."""

    def test_parse_high_risk_phases(self):
        """Parse high-risk phases from tasks.md."""
        tasks_md = """# Tasks

## Phase 1: Add email validation
### Risk Tier
- `high-risk`

## Phase 2: Update database schema
### Risk Tier
- `standard`

## Phase 3: Migrate legacy code
### Risk Tier
- `high-risk`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)
            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            phases = high_risk_reviewer.read_tasks_md(feature_dir)
            self.assertEqual(len(phases), 3)
            self.assertEqual(phases[0]["name"], "Add email validation")
            self.assertEqual(phases[0]["risk"], "high-risk")
            self.assertEqual(phases[1]["risk"], "standard")
            self.assertEqual(phases[2]["risk"], "high-risk")

    def test_filter_high_risk_phases(self):
        """Filter to only high-risk phases."""
        phases = [
            {"name": "Phase 1", "risk": "high-risk"},
            {"name": "Phase 2", "risk": "standard"},
            {"name": "Phase 3", "risk": "high-risk"},
        ]
        high_risk = high_risk_reviewer.get_high_risk_phases(phases)

        self.assertEqual(len(high_risk), 2)
        self.assertEqual(high_risk[0]["name"], "Phase 1")
        self.assertEqual(high_risk[1]["name"], "Phase 3")

    def test_no_tasks_md_returns_empty(self):
        """Missing tasks.md returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            phases = high_risk_reviewer.read_tasks_md(tmpdir)
            self.assertEqual(phases, [])


class CodeReviewerTrackingTests(unittest.TestCase):
    """Checkpoint reads reviewed state from review_tracking (reviewed map + Review Fallback)."""

    TASKS = """# Tasks

## Phase 1: Email validation
### Risk Tier
- `high-risk`

## Slice 2F2: Schema migration
**Risk Tier:** high-risk

## Phase 3: Config update
### Risk Tier
- `standard`
"""

    def _feature(self, tmp, reviewed=None, tasks=None):
        os.makedirs(os.path.join(tmp, "tasks"), exist_ok=True)
        with open(os.path.join(tmp, "tasks", "tasks.md"), "w") as f:
            f.write(tasks or self.TASKS)
        with open(os.path.join(tmp, "workflow-state.md"), "w") as f:
            f.write("# State\n")
        if reviewed is not None:
            with open(os.path.join(tmp, "workflow-state.json"), "w") as f:
                json.dump({"reviewed": reviewed}, f)

    def test_checkpoint_lists_unreviewed_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp, reviewed={"1": True})
            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(tmp)
            self.assertEqual(checkpoint["type"], "checkpoint")
            self.assertEqual(checkpoint["high_risk_count"], 2)
            self.assertEqual(checkpoint["reviewed_count"], 1)
            self.assertIn("Schema migration", checkpoint["message"])
            self.assertNotIn("Email validation", checkpoint["message"])

    def test_all_high_risk_reviewed_success_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp, reviewed={"1": True, "2f2": True})
            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(tmp)
            self.assertEqual(checkpoint["type"], "success")
            self.assertIn("All high-risk slices reviewed", checkpoint["message"])

    def test_legacy_reviewed_phases_list_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp)
            with open(os.path.join(tmp, "workflow-state.json"), "w") as f:
                json.dump({"code_reviewer_tracking": {"reviewed_phases": ["Email validation"]}}, f)
            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(tmp)
            self.assertEqual(checkpoint["reviewed_count"], 0)

    def test_review_fallback_clears_named_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp)
            with open(os.path.join(tmp, "workflow-state.md"), "w") as f:
                f.write("# State\n- Review Fallback: Accepted via AskUserQuestion: all: no reviewer\n")
            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(tmp)
            self.assertEqual(checkpoint["type"], "success")

    def test_no_high_risk_phases_no_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp, tasks="# Tasks\n\n## Phase 1: Simple fix\n### Risk Tier\n- `standard`\n")
            self.assertIsNone(high_risk_reviewer.get_code_reviewer_checkpoint(tmp))


class ExtendedTasksMdParsingTests(unittest.TestCase):
    """Tests for extended parsing: risk tiers + files from tasks.md."""

    def test_read_tasks_md_with_files_returns_full_phase_objects(self):
        """Parse tasks.md and return phases with name, risk_tier, and files."""
        tasks_md = """# Tasks

## Slice 1: Parse green_pause Marker

**Risk Tier:** standard
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`

## Slice 2: Extract High-Risk Phases

**Risk Tier:** high-risk
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`, `agent-isdd/tests/test_high_risk_reviewer.py`

## Slice 3: File-Path Scoping

**Risk Tier:** standard
**Files:** `src/config.py`, `src/utils.py`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)
            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            phases = high_risk_reviewer.read_tasks_md(feature_dir)

            # Should return 3 phases with full objects
            self.assertEqual(len(phases), 3)

            # Check first phase
            self.assertEqual(phases[0]["name"], "Parse green_pause Marker")
            self.assertEqual(phases[0]["risk"], "standard")
            self.assertTrue(any("high_risk_reviewer.py" in f for f in phases[0]["files"]))

            # Check second phase
            self.assertEqual(phases[1]["name"], "Extract High-Risk Phases")
            self.assertEqual(phases[1]["risk"], "high-risk")
            self.assertEqual(len(phases[1]["files"]), 2)

            # Check third phase
            self.assertEqual(phases[2]["name"], "File-Path Scoping")
            self.assertEqual(phases[2]["risk"], "standard")
            self.assertEqual(len(phases[2]["files"]), 2)

    def test_read_tasks_md_extracts_files_as_list(self):
        """Files are returned as a list, not a string."""
        tasks_md = """# Tasks

## Slice 1: Test Slice

**Risk Tier:** standard
**Files:** `file1.py`, `file2.py`, `file3.py`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)
            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            phases = high_risk_reviewer.read_tasks_md(feature_dir)

            self.assertEqual(len(phases), 1)
            self.assertIsInstance(phases[0]["files"], list)
            self.assertEqual(len(phases[0]["files"]), 3)
            self.assertIn("file1.py", phases[0]["files"])


class MainSlicingCompleteTests(unittest.TestCase):
    """Tests for main()'s slicing_complete + test_author_pending detection (design.md
    touchpoint 2: reuses read_tasks_md()/get_high_risk_phases() unchanged, writes
    test_author_pending via sdd_state.write_test_author_pending)."""

    def _write_tasks_md(self, feature_dir, body):
        tasks_dir = os.path.join(feature_dir, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        with open(os.path.join(tasks_dir, "tasks.md"), "w", encoding="utf-8") as fh:
            fh.write(body)

    def _write_transcript(self, path, report_text):
        line = json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": report_text},
        })
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def test_slicing_complete_with_high_risk_writes_test_author_pending(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            self._write_tasks_md(feature_dir, """# Tasks

## Slice 1: Risky migration

**Risk Tier:** high-risk
**Files:** `src/migrate.py`

## Slice 2: Safe rename

**Risk Tier:** standard
**Files:** `src/rename.py`
""")
            transcript = os.path.join(home, "transcript.jsonl")
            self._write_transcript(
                transcript,
                "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:slicing_complete-->\n"
                "Ready for implementation.",
            )
            msg, rc = h.run_hook_message(
                "high_risk_reviewer.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("Risky migration", msg)

            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, encoding="utf-8") as fh:
                state = json.load(fh)
            pending = state.get("test_author_pending")
            self.assertIsNotNone(pending)
            self.assertEqual(len(pending["slices"]), 1)
            self.assertEqual(pending["slices"][0]["name"], "Risky migration")
            self.assertEqual(pending["slices"][0]["files"], ["src/migrate.py"])
            self.assertIn("detected_at", pending)

    def test_report_in_last_assistant_message_not_parent_transcript(self):
        """Current Claude Code: transcript_path is the parent session's transcript; the
        subagent's report only arrives in last_assistant_message."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            self._write_tasks_md(feature_dir, """# Tasks

## Slice 1: Risky migration

**Risk Tier:** high-risk
**Files:** `src/migrate.py`
""")
            parent = os.path.join(home, "parent.jsonl")
            self._write_transcript(parent, "Spawning agent-TDD now.")
            msg, rc = h.run_hook_message(
                "high_risk_reviewer.py",
                {"cwd": repo, "transcript_path": parent,
                 "last_assistant_message": "<!--AGENT-TDD-REPORT-->\n"
                                           "<!--AGENT-TDD-PHASE:slicing_complete-->\nReady."},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIn("Risky migration", msg or "")
            with open(os.path.join(feature_dir, "workflow-state.json"), encoding="utf-8") as fh:
                self.assertIn("test_author_pending", json.load(fh))

    def test_slicing_complete_with_zero_high_risk_makes_no_write(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            self._write_tasks_md(feature_dir, """# Tasks

## Slice 1: Safe rename

**Risk Tier:** standard
**Files:** `src/rename.py`
""")
            transcript = os.path.join(home, "transcript.jsonl")
            self._write_transcript(
                transcript,
                "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:slicing_complete-->\n"
                "Ready for implementation.",
            )
            h.run_hook_message(
                "high_risk_reviewer.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            json_path = os.path.join(feature_dir, "workflow-state.json")
            if os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as fh:
                    state = json.load(fh)
                self.assertNotIn("test_author_pending", state)


class ReviewTrackingWiringTests(unittest.TestCase):
    """Slice 13: main() delegates review recording to review_tracking and filters the reminder."""

    TASKS = (
        "# Tasks\n\n## Slice 2F2: alnum\n**Risk Tier:** high-risk\n**Files:** `a.py`\n\n"
        "## Slice 3: plain\n**Risk Tier:** standard\n"
    )

    def _feature(self, tmp):
        os.makedirs(os.path.join(tmp, "tasks"))
        with open(os.path.join(tmp, "tasks", "tasks.md"), "w") as fh:
            fh.write(self.TASKS)
        md = os.path.join(tmp, "workflow-state.md")
        with open(md, "w") as fh:
            fh.write("# State\n")
        return md, os.path.join(tmp, "workflow-state.json")

    def _run(self, md, payload):
        with mock.patch.object(high_risk_reviewer, "active_state_file", return_value=md), \
             mock.patch.object(high_risk_reviewer.review_tracking.sdd_state, "active_state_file", return_value=md):
            return high_risk_reviewer.main(payload)

    def test_code_reviewer_stop_marks_alphanumeric_slice_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, js = self._feature(tmp)
            payload = {"cwd": tmp, "agent_type": "code-reviewer:code-reviewer",
                       "last_assistant_message": "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=2F2-->"}
            self._run(md, payload)
            with open(js) as fh:
                self.assertEqual(json.load(fh)["reviewed"], {"2F2": True})

    def test_non_code_reviewer_stop_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, js = self._feature(tmp)
            payload = {"cwd": tmp, "agent_type": "agent-tdd:agent-TDD",
                       "last_assistant_message": "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=2F2-->"}
            self._run(md, payload)
            reviewed = {}
            if os.path.exists(js):
                with open(js) as fh:
                    reviewed = json.load(fh).get("reviewed", {})
            self.assertNotIn("2F2", reviewed)

    def test_read_tasks_md_accepts_alphanumeric_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._feature(tmp)
            phases = high_risk_reviewer.read_tasks_md(tmp)
            self.assertEqual([(p["name"], p["risk"]) for p in phases],
                             [("alnum", "high-risk"), ("plain", "standard")])

    def test_reminder_only_for_agent_tdd_and_code_reviewer_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, _ = self._feature(tmp)
            other = self._run(md, {"cwd": tmp, "agent_type": "Explore", "last_assistant_message": "x"})
            self.assertIsNone(other)
            tdd = self._run(md, {"cwd": tmp, "agent_type": "agent-tdd:agent-TDD", "last_assistant_message": "x"})
            self.assertIn("alnum", tdd)

    def test_review_tracking_failure_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, _ = self._feature(tmp)
            with mock.patch.object(high_risk_reviewer.review_tracking, "evaluate", side_effect=RuntimeError("boom")):
                msg = self._run(md, {"cwd": tmp, "agent_type": "agent-tdd:agent-TDD", "last_assistant_message": "x"})
            self.assertIn("alnum", msg)
    def test_reminder_in_same_call_drops_just_reviewed_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, _ = self._feature(tmp)
            payload = {"cwd": tmp, "agent_type": "code-reviewer:code-reviewer",
                       "last_assistant_message": "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=2F2-->"}
            msg = self._run(md, payload)
            self.assertNotIn("2F2", msg or "")
            self.assertIn("All high-risk slices reviewed", msg)

    def test_code_reviewer_stop_gets_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, _ = self._feature(tmp)
            msg = self._run(md, {"cwd": tmp, "agent_type": "code-reviewer:code-reviewer",
                                 "last_assistant_message": "no marker"})
            self.assertIn("alnum", msg)

    def test_payload_without_agent_type_gets_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            md, _ = self._feature(tmp)
            msg = self._run(md, {"cwd": tmp, "last_assistant_message": "x"})
            self.assertIn("alnum", msg)

    def test_duplicated_tier_and_phase_regexes_removed(self):
        for name in ("_PHASE_PATTERN", "_RISK_TIER_NEW_FORMAT", "_RISK_TIER_OLD_FORMAT"):
            self.assertFalse(hasattr(high_risk_reviewer, name), name)


if __name__ == "__main__":
    unittest.main()
