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
    """Tests for tracking reviewed vs. unreviewed high-risk slices."""

    def test_init_tracking_creates_state_field(self):
        """Initialize tracking creates code_reviewer_tracking in state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            json_path = os.path.join(feature_dir, "workflow-state.json")

            # Create initial state
            with open(json_path, 'w') as f:
                json.dump({"current_phase": "Implementation"}, f)

            high_risk_phases = [
                {"name": "Phase 1", "risk": "high-risk"},
                {"name": "Phase 2", "risk": "high-risk"},
            ]

            high_risk_reviewer.init_code_reviewer_tracking(feature_dir, high_risk_phases)

            # Read back and verify
            with open(json_path, 'r') as f:
                state = json.load(f)

            self.assertIn("code_reviewer_tracking", state)
            self.assertEqual(len(state["code_reviewer_tracking"]["high_risk_phases"]), 2)
            self.assertEqual(state["code_reviewer_tracking"]["reviewed_phases"], [])

    def test_checkpoint_lists_unreviewed_phases(self):
        """Checkpoint message lists unreviewed high-risk phases."""
        tasks_md = """# Tasks

## Phase 1: Email validation
### Risk Tier
- `high-risk`

## Phase 2: Schema migration
### Risk Tier
- `high-risk`

## Phase 3: Config update
### Risk Tier
- `standard`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)

            # Write tasks.md
            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            # Create state with tracking
            json_path = os.path.join(feature_dir, "workflow-state.json")
            state = {
                "code_reviewer_tracking": {
                    "high_risk_phases": ["Email validation", "Schema migration"],
                    "reviewed_phases": ["Email validation"]  # Only 1 reviewed
                }
            }
            with open(json_path, 'w') as f:
                json.dump(state, f)

            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(feature_dir)

            self.assertIsNotNone(checkpoint)
            self.assertEqual(checkpoint["high_risk_count"], 2)
            self.assertEqual(checkpoint["reviewed_count"], 1)
            self.assertIn("Schema migration", checkpoint["message"])

    def test_all_high_risk_reviewed_success_message(self):
        """All reviewed high-risk slices show success message."""
        tasks_md = """# Tasks

## Phase 1: Email validation
### Risk Tier
- `high-risk`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)

            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            json_path = os.path.join(feature_dir, "workflow-state.json")
            state = {
                "code_reviewer_tracking": {
                    "high_risk_phases": ["Email validation"],
                    "reviewed_phases": ["Email validation"]  # All reviewed
                }
            }
            with open(json_path, 'w') as f:
                json.dump(state, f)

            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(feature_dir)

            self.assertIsNotNone(checkpoint)
            self.assertEqual(checkpoint["type"], "success")
            self.assertIn("All high-risk slices reviewed", checkpoint["message"])

    def test_no_high_risk_phases_no_checkpoint(self):
        """No high-risk phases means no checkpoint."""
        tasks_md = """# Tasks

## Phase 1: Simple fix
### Risk Tier
- `standard`
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_dir = tmpdir
            os.makedirs(os.path.join(feature_dir, "tasks"), exist_ok=True)

            with open(os.path.join(feature_dir, "tasks", "tasks.md"), 'w') as f:
                f.write(tasks_md)

            json_path = os.path.join(feature_dir, "workflow-state.json")
            with open(json_path, 'w') as f:
                json.dump({}, f)

            checkpoint = high_risk_reviewer.get_code_reviewer_checkpoint(feature_dir)

            self.assertIsNone(checkpoint)


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


class ParseDesignMdRisksTests(unittest.TestCase):
    """Tests for parse_design_md_risks function."""

    def test_parse_design_md_risks_extracts_file_paths(self):
        """Extract high-risk file paths from design.md Risks section."""
        design_md = """# Design

## Risks And Tradeoffs

- Risk: Schema changes to `src/models/user.py` and `src/db/migrations.py` without deprecation.
  - Mitigation: Update tests accordingly.

- Risk: API breaking change in `src/api/endpoints.py`.
  - Mitigation: Document in changelog.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            design_path = os.path.join(tmpdir, "design.md")
            with open(design_path, 'w') as f:
                f.write(design_md)

            paths = high_risk_reviewer.parse_design_md_risks(design_path)

            # Should extract file paths mentioned in Risks section
            self.assertIn("src/models/user.py", paths)
            self.assertIn("src/db/migrations.py", paths)
            self.assertIn("src/api/endpoints.py", paths)

    def test_parse_design_md_risks_returns_empty_when_no_risks_section(self):
        """Return empty list when design.md has no Risks And Tradeoffs section."""
        design_md = """# Design

## Architecture

Some content but no risks section.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            design_path = os.path.join(tmpdir, "design.md")
            with open(design_path, 'w') as f:
                f.write(design_md)

            paths = high_risk_reviewer.parse_design_md_risks(design_path)

            self.assertEqual(paths, [])

    def test_parse_design_md_risks_returns_empty_for_missing_file(self):
        """Return empty list when design.md does not exist."""
        paths = high_risk_reviewer.parse_design_md_risks("/nonexistent/design.md")
        self.assertEqual(paths, [])

    def test_parse_design_md_risks_extracts_backtick_quoted_paths(self):
        """Extract paths enclosed in backticks from risk descriptions."""
        design_md = """# Design

## Risks And Tradeoffs

- Risk: Modifications to persistence layer `src/persistence/adapter.py`.
- Risk: Changes affecting `src/models/profile.py` and `src/validators/profile.py`.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            design_path = os.path.join(tmpdir, "design.md")
            with open(design_path, 'w') as f:
                f.write(design_md)

            paths = high_risk_reviewer.parse_design_md_risks(design_path)

            self.assertIn("src/persistence/adapter.py", paths)
            self.assertIn("src/models/profile.py", paths)
            self.assertIn("src/validators/profile.py", paths)


class GetApplicablePhasesTests(unittest.TestCase):
    """Tests for get_applicable_phases filtering logic."""

    def test_get_applicable_phases_includes_all_high_risk(self):
        """Include all high-risk phases regardless of file paths."""
        phases = [
            {"name": "Phase 1", "risk": "high-risk", "files": ["src/critical.py"]},
            {"name": "Phase 2", "risk": "high-risk", "files": ["src/other.py"]},
            {"name": "Phase 3", "risk": "standard", "files": ["src/config.py"]},
        ]
        high_risk_paths = ["src/critical.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        # All high-risk phases should be included
        self.assertEqual(len(applicable), 2)
        self.assertEqual(applicable[0]["name"], "Phase 1")
        self.assertEqual(applicable[1]["name"], "Phase 2")

    def test_get_applicable_phases_includes_standard_with_matching_files(self):
        """Include standard phases only if files intersect with high-risk paths."""
        phases = [
            {"name": "Phase 1", "risk": "standard", "files": ["src/critical.py", "src/config.py"]},
            {"name": "Phase 2", "risk": "standard", "files": ["src/utils.py"]},
            {"name": "Phase 3", "risk": "high-risk", "files": ["src/other.py"]},
        ]
        high_risk_paths = ["src/critical.py", "src/security.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        # Phase 1 (standard + intersects) and Phase 3 (high-risk)
        self.assertEqual(len(applicable), 2)
        names = [p["name"] for p in applicable]
        self.assertIn("Phase 1", names)
        self.assertIn("Phase 3", names)

    def test_get_applicable_phases_excludes_standard_without_matching_files(self):
        """Exclude standard phases when files don't intersect with high-risk paths."""
        phases = [
            {"name": "Phase 1", "risk": "standard", "files": ["src/utils.py"]},
            {"name": "Phase 2", "risk": "standard", "files": ["src/helpers.py"]},
            {"name": "Phase 3", "risk": "high-risk", "files": ["src/other.py"]},
        ]
        high_risk_paths = ["src/critical.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        # Only high-risk phase
        self.assertEqual(len(applicable), 1)
        self.assertEqual(applicable[0]["name"], "Phase 3")

    def test_get_applicable_phases_with_empty_high_risk_paths_returns_only_high_risk(self):
        """When high_risk_paths is empty, return only high-risk phases."""
        phases = [
            {"name": "Phase 1", "risk": "standard", "files": ["src/utils.py"]},
            {"name": "Phase 2", "risk": "high-risk", "files": ["src/critical.py"]},
            {"name": "Phase 3", "risk": "high-risk", "files": ["src/security.py"]},
        ]
        high_risk_paths = []

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        # Only high-risk phases
        self.assertEqual(len(applicable), 2)
        for phase in applicable:
            self.assertEqual(phase["risk"], "high-risk")

    def test_get_applicable_phases_no_phases_returns_empty(self):
        """Empty phases list returns empty applicable phases."""
        phases = []
        high_risk_paths = ["src/critical.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        self.assertEqual(applicable, [])

    def test_get_applicable_phases_preserves_phase_order(self):
        """Applicable phases maintain original order from input."""
        phases = [
            {"name": "Phase 1", "risk": "standard", "files": ["src/critical.py"]},
            {"name": "Phase 2", "risk": "high-risk", "files": ["src/other.py"]},
            {"name": "Phase 3", "risk": "standard", "files": ["src/critical.py"]},
        ]
        high_risk_paths = ["src/critical.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        self.assertEqual(len(applicable), 3)
        self.assertEqual(applicable[0]["name"], "Phase 1")
        self.assertEqual(applicable[1]["name"], "Phase 2")
        self.assertEqual(applicable[2]["name"], "Phase 3")

    def test_get_applicable_phases_with_partial_file_overlap(self):
        """Standard phase with multiple files: included if any file matches high-risk paths."""
        phases = [
            {"name": "Phase 1", "risk": "standard", "files": ["src/utils.py", "src/critical.py", "src/helpers.py"]},
        ]
        high_risk_paths = ["src/critical.py", "src/security.py"]

        applicable = high_risk_reviewer.get_applicable_phases(phases, high_risk_paths)

        # Phase 1 matches because it has src/critical.py
        self.assertEqual(len(applicable), 1)
        self.assertEqual(applicable[0]["name"], "Phase 1")


class InvokeCodeReviewerTests(unittest.TestCase):
    """Tests for invoke_code_reviewer subprocess invocation with timeout."""

    def setUp(self):
        """Set up test fixtures."""
        self.slice_spec = {
            "phase_name": "green_pause",
            "objective": "Add email validation",
            "test_intent": "Verify validation logic",
            "risk_tier": "high-risk",
            "data_contracts": {}
        }

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_success_returns_json(self, mock_popen):
        """Successful subprocess call returns parsed JSON in expected tuple."""
        json_output = '{"status": "reviewed", "findings": "No issues"}'

        # Mock successful subprocess
        mock_process = MagicMock()
        mock_process.communicate.return_value = (json_output.encode(), b'')
        mock_process.returncode = 0
        mock_process.timeout.return_value = None
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(parsed_json)
        self.assertIsInstance(parsed_json, dict)
        self.assertEqual(parsed_json["status"], "reviewed")
        self.assertIsNone(error)
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_timeout_kills_process(self, mock_popen):
        """Timeout exception sets timed_out=True and error='timeout'."""
        # Mock timeout exception in communicate()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired('cmd', 30)
        mock_process.kill = MagicMock()
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec, timeout_seconds=30
        )

        self.assertEqual(exit_code, -1)
        self.assertIsNone(parsed_json)
        self.assertEqual(error, "timeout")
        self.assertTrue(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_non_zero_exit(self, mock_popen):
        """Non-zero exit code captured with stderr."""
        stderr_output = "Command failed: invalid arguments"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', stderr_output.encode())
        mock_process.returncode = 127
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 127)
        self.assertIsNone(parsed_json)
        self.assertEqual(error, stderr_output)
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_invalid_json_output(self, mock_popen):
        """Invalid JSON output handled gracefully."""
        invalid_json = "This is not JSON {broken]"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (invalid_json.encode(), b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(parsed_json)
        self.assertEqual(error, "invalid JSON")
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_missing_command(self, mock_popen):
        """FileNotFoundError when /code-reviewer command not found."""
        mock_popen.side_effect = FileNotFoundError("No such file or directory")

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, -1)
        self.assertIsNone(parsed_json)
        self.assertEqual(error, "/code-reviewer not found")
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_stderr_capture(self, mock_popen):
        """Stderr captured and returned on process crash."""
        stderr_text = "Critical error occurred in subprocess"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', stderr_text.encode())
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 1)
        self.assertIsNone(parsed_json)
        self.assertIn("Critical error occurred", error)
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_with_custom_timeout(self, mock_popen):
        """Custom timeout_seconds value passed to wait() call."""
        json_output = '{"result": "success"}'

        mock_process = MagicMock()
        mock_process.communicate.return_value = (json_output.encode(), b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec, timeout_seconds=120
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(parsed_json)
        self.assertEqual(parsed_json["result"], "success")
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_empty_stdout(self, mock_popen):
        """Empty stdout with zero exit code treated as invalid JSON."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(parsed_json)
        self.assertEqual(error, "invalid JSON")
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_large_json_output(self, mock_popen):
        """Large JSON output parsed correctly."""
        large_findings = [{"issue_id": i, "message": f"Issue {i}"} for i in range(100)]
        json_output = json.dumps({
            "status": "reviewed",
            "findings": large_findings,
            "timestamp": "2026-08-24T10:00:00Z"
        })

        mock_process = MagicMock()
        mock_process.communicate.return_value = (json_output.encode(), b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(parsed_json)
        self.assertEqual(len(parsed_json["findings"]), 100)
        self.assertIsNone(error)
        self.assertFalse(timed_out)

    @patch('subprocess.Popen')
    def test_invoke_code_reviewer_command_construction(self, mock_popen):
        """Verify /code-reviewer command is invoked with slice_spec as JSON."""
        json_output = '{"status": "ok"}'

        mock_process = MagicMock()
        mock_process.communicate.return_value = (json_output.encode(), b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        exit_code, parsed_json, error, timed_out = high_risk_reviewer.invoke_code_reviewer(
            self.slice_spec
        )

        # Verify Popen was called with /code-reviewer command
        self.assertTrue(mock_popen.called)
        call_args = mock_popen.call_args
        self.assertIsNotNone(call_args)

        # Verify command includes /code-reviewer
        cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
        self.assertTrue(any('/code-reviewer' in str(c) for c in (cmd if isinstance(cmd, list) else [cmd])))


class UpdateReviewedPhasesTests(unittest.TestCase):
    """Tests for update_reviewed_phases schema extension."""

    def test_update_reviewed_phases_appends_new_entry(self):
        """Append new reviewed phase entry to workflow state."""
        state = {
            "code_reviewer_tracking": {
                "high_risk_phases": ["Phase 1"],
                "reviewed_phases": []
            }
        }
        findings = [
            {"dimension": "intent", "status": "PASS", "finding_text": "Good intent"}
        ]

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "clean", findings, "code-reviewer@0.1.0"
        )

        self.assertIn("code_reviewer_tracking", result)
        reviewed = result["code_reviewer_tracking"]["reviewed_phases"]
        self.assertEqual(len(reviewed), 1)
        self.assertEqual(reviewed[0]["phase_name"], "Phase 1")
        self.assertEqual(reviewed[0]["severity"], "clean")
        self.assertEqual(reviewed[0]["findings_count"], 1)

    def test_update_reviewed_phases_creates_structure_if_missing(self):
        """Create code_reviewer_tracking structure if not present."""
        state = {}

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "major", [], "code-reviewer@0.1.0"
        )

        self.assertIn("code_reviewer_tracking", result)
        self.assertIn("reviewed_phases", result["code_reviewer_tracking"])
        self.assertEqual(len(result["code_reviewer_tracking"]["reviewed_phases"]), 1)

    def test_update_reviewed_phases_includes_all_fields(self):
        """All required fields are populated in reviewed entry."""
        state = {"code_reviewer_tracking": {"high_risk_phases": [], "reviewed_phases": []}}
        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "XSS"}
        ]

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 2", "major", findings, "code-reviewer@0.2.1"
        )

        entry = result["code_reviewer_tracking"]["reviewed_phases"][0]
        self.assertEqual(entry["phase_name"], "Phase 2")
        self.assertEqual(entry["severity"], "major")
        self.assertEqual(entry["findings_count"], 1)
        self.assertEqual(entry["findings"], findings)
        self.assertEqual(entry["reviewer_version"], "code-reviewer@0.2.1")
        self.assertIn("reviewed_at", entry)

    def test_update_reviewed_phases_multiple_entries(self):
        """Multiple phase reviews accumulate in reviewed_phases."""
        state = {"code_reviewer_tracking": {"high_risk_phases": [], "reviewed_phases": []}}

        # First review
        high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "clean", [], "code-reviewer@0.1.0"
        )

        # Second review
        high_risk_reviewer.update_reviewed_phases(
            state, "Phase 2", "non-major", [{"dimension": "naming", "status": "WARN", "finding_text": "poor name"}],
            "code-reviewer@0.1.0"
        )

        reviewed = state["code_reviewer_tracking"]["reviewed_phases"]
        self.assertEqual(len(reviewed), 2)
        self.assertEqual(reviewed[0]["phase_name"], "Phase 1")
        self.assertEqual(reviewed[1]["phase_name"], "Phase 2")
        self.assertEqual(reviewed[1]["findings_count"], 1)

    def test_update_reviewed_phases_empty_findings(self):
        """Empty findings list results in findings_count=0."""
        state = {"code_reviewer_tracking": {"high_risk_phases": [], "reviewed_phases": []}}

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "clean", [], "code-reviewer@0.1.0"
        )

        entry = result["code_reviewer_tracking"]["reviewed_phases"][0]
        self.assertEqual(entry["findings_count"], 0)
        self.assertEqual(entry["findings"], [])

    def test_update_reviewed_phases_none_findings(self):
        """None findings list is handled gracefully."""
        state = {"code_reviewer_tracking": {"high_risk_phases": [], "reviewed_phases": []}}

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "clean", None, "code-reviewer@0.1.0"
        )

        entry = result["code_reviewer_tracking"]["reviewed_phases"][0]
        self.assertEqual(entry["findings_count"], 0)
        self.assertEqual(entry["findings"], [])

    def test_update_reviewed_phases_timestamp_included(self):
        """reviewed_at timestamp is included in ISO format."""
        state = {"code_reviewer_tracking": {"high_risk_phases": [], "reviewed_phases": []}}

        result = high_risk_reviewer.update_reviewed_phases(
            state, "Phase 1", "clean", [], "code-reviewer@0.1.0"
        )

        entry = result["code_reviewer_tracking"]["reviewed_phases"][0]
        self.assertIn("reviewed_at", entry)
        # Should be ISO format with Z suffix
        self.assertTrue(entry["reviewed_at"].endswith("Z"))


class GetHighRiskFilePathsConfigTests(unittest.TestCase):
    """Tests for get_high_risk_file_paths_config."""

    def test_get_high_risk_file_paths_config_returns_list(self):
        """Extract high-risk file paths from config."""
        state = {
            "code_reviewer_tracking": {
                "config": {
                    "high_risk_file_paths": ["src/models/user.py", "src/api/endpoints.py"]
                }
            }
        }

        paths = high_risk_reviewer.get_high_risk_file_paths_config(state)

        self.assertEqual(len(paths), 2)
        self.assertIn("src/models/user.py", paths)
        self.assertIn("src/api/endpoints.py", paths)

    def test_get_high_risk_file_paths_config_empty_when_missing(self):
        """Return empty list when config is missing."""
        state = {}

        paths = high_risk_reviewer.get_high_risk_file_paths_config(state)

        self.assertEqual(paths, [])

    def test_get_high_risk_file_paths_config_tracking_missing(self):
        """Return empty list when code_reviewer_tracking is missing."""
        state = {"other_field": "value"}

        paths = high_risk_reviewer.get_high_risk_file_paths_config(state)

        self.assertEqual(paths, [])

    def test_get_high_risk_file_paths_config_config_missing(self):
        """Return empty list when config section is missing."""
        state = {
            "code_reviewer_tracking": {
                "high_risk_phases": []
            }
        }

        paths = high_risk_reviewer.get_high_risk_file_paths_config(state)

        self.assertEqual(paths, [])

    def test_get_high_risk_file_paths_config_paths_field_missing(self):
        """Return empty list when high_risk_file_paths field is missing."""
        state = {
            "code_reviewer_tracking": {
                "config": {
                    "review_timeout_seconds": 600
                }
            }
        }

        paths = high_risk_reviewer.get_high_risk_file_paths_config(state)

        self.assertEqual(paths, [])

    def test_get_high_risk_file_paths_config_backward_compat(self):
        """Backward compatible with old schema (missing config)."""
        old_state = {
            "code_reviewer_tracking": {
                "high_risk_phases": ["Phase 1"],
                "reviewed_phases": []
            }
        }

        paths = high_risk_reviewer.get_high_risk_file_paths_config(old_state)

        self.assertEqual(paths, [])


class ConstructRollbackMarkerTests(unittest.TestCase):
    """Tests for construct_rollback_marker (Slice 6)."""

    def test_construct_rollback_marker_basic(self):
        """Construct rollback marker from findings."""
        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "SQL injection"}
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings)

        self.assertIn("SDD-ROLLBACK-REQUEST", marker)
        self.assertIn("target=Tasks", marker)
        self.assertIn("security", marker)
        self.assertIn("SQL injection", marker)

    def test_construct_rollback_marker_custom_target(self):
        """Construct marker with custom rollback target."""
        findings = [
            {"dimension": "intent", "status": "FAIL", "finding_text": "wrong approach"}
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings, target="Requirements")

        self.assertIn("target=Requirements", marker)

    def test_construct_rollback_marker_multiple_findings(self):
        """Multiple findings summarized in reason (top 3)."""
        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "XSS"},
            {"dimension": "regressions", "status": "WARN", "finding_text": "potential regression"},
            {"dimension": "intent", "status": "FAIL", "finding_text": "wrong logic"},
            {"dimension": "naming", "status": "FAIL", "finding_text": "bad name"}  # 4th, not included
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings)

        # Should include first 3 findings
        self.assertIn("security", marker)
        self.assertIn("regressions", marker)
        self.assertIn("intent", marker)

    def test_construct_rollback_marker_empty_findings(self):
        """Empty findings list returns empty string."""
        marker = high_risk_reviewer.construct_rollback_marker([])
        self.assertEqual(marker, "")

    def test_construct_rollback_marker_none_findings(self):
        """None findings returns empty string."""
        marker = high_risk_reviewer.construct_rollback_marker(None)
        self.assertEqual(marker, "")

    def test_construct_rollback_marker_reason_truncation(self):
        """Reason text truncated if exceeds 200 chars."""
        findings = [
            {
                "dimension": "security",
                "status": "FAIL",
                "finding_text": "Very long finding text: " + "x" * 300
            }
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings)

        # Should not exceed reasonable length
        self.assertLess(len(marker), 500)
        self.assertIn("...", marker)  # Truncation indicator

    def test_construct_rollback_marker_format(self):
        """Marker follows HTML comment format."""
        findings = [
            {"dimension": "test", "status": "FAIL", "finding_text": "test"}
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings)

        # Should be HTML comment format
        self.assertTrue(marker.startswith("<!--"))
        self.assertTrue(marker.endswith("-->"))

    def test_construct_rollback_marker_regex_match(self):
        """Marker format matches subagent_report.py regex."""
        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "vulnerability"}
        ]
        marker = high_risk_reviewer.construct_rollback_marker(findings)

        # Pattern should match: <!--SDD-ROLLBACK-REQUEST: target=X reason="..."/>-->
        import re
        pattern = r'<!--SDD-ROLLBACK-REQUEST: target=\w+ reason="[^"]*"/?>-->'
        self.assertIsNotNone(re.search(pattern, marker))


class ConstructResumeMessageTests(unittest.TestCase):
    """Tests for construct_resume_message (Slice 7)."""

    def test_construct_resume_message_clean(self):
        """Resume message for clean severity."""
        message = high_risk_reviewer.construct_resume_message(
            "Phase 1: Foo", "clean", []
        )

        self.assertIn("Phase 1: Foo", message)
        self.assertIn("Severity: clean", message)
        self.assertIn("No issues found", message)
        self.assertIn("Proceeding to refactor", message)

    def test_construct_resume_message_non_major(self):
        """Resume message for non-major severity."""
        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "bad name"}
        ]
        message = high_risk_reviewer.construct_resume_message(
            "Phase 2: Bar", "non-major", findings
        )

        self.assertIn("Phase 2: Bar", message)
        self.assertIn("Severity: non-major", message)
        self.assertIn("1 finding", message)
        self.assertIn("Proceeding to refactor", message)

    def test_construct_resume_message_finding_count(self):
        """Message includes correct finding count."""
        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue1"},
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue2"},
        ]
        message = high_risk_reviewer.construct_resume_message(
            "Phase 3", "non-major", findings
        )

        self.assertIn("2 findings", message)
        self.assertIn("2 follow-ups", message)

    def test_construct_resume_message_single_finding_pluralization(self):
        """Single finding uses singular form."""
        findings = [{"dimension": "naming", "status": "WARN", "finding_text": "issue"}]
        message = high_risk_reviewer.construct_resume_message(
            "Phase 1", "non-major", findings
        )

        # "1 finding" (singular) and "1 follow-up" (singular)
        self.assertIn("1 finding", message)
        self.assertIn("1 follow-up", message)

    def test_construct_resume_message_empty_findings_non_major(self):
        """Non-major with empty findings."""
        message = high_risk_reviewer.construct_resume_message(
            "Phase X", "non-major", []
        )

        self.assertIn("0 findings", message)
        self.assertIn("0 follow-ups", message)

    def test_construct_resume_message_none_findings(self):
        """None findings handled gracefully."""
        message = high_risk_reviewer.construct_resume_message(
            "Phase Y", "clean", None
        )

        self.assertIn("No issues found", message)
        self.assertIn("0 follow-ups", message)

    def test_construct_resume_message_format(self):
        """Message has complete structure."""
        message = high_risk_reviewer.construct_resume_message(
            "Phase 1: Test", "clean", []
        )

        # Should contain all key components
        self.assertIn("Code review complete", message)
        self.assertIn("Severity:", message)
        self.assertIn("Proceeding to refactor", message)
        self.assertIn("follow-up", message)

    def test_construct_resume_message_large_finding_count(self):
        """Large finding count handled correctly."""
        findings = [{"dimension": f"dim{i}", "status": "WARN", "finding_text": f"issue{i}"}
                   for i in range(25)]
        message = high_risk_reviewer.construct_resume_message(
            "Phase Z", "non-major", findings
        )

        self.assertIn("25 findings", message)
        self.assertIn("25 follow-ups", message)


class CreateFollowUpTasksTests(unittest.TestCase):
    """Tests for create_follow_up_tasks (Slice 8, high-risk)."""

    def test_create_follow_up_tasks_empty_findings(self):
        """Empty findings returns empty task list."""
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", [])
        self.assertEqual(tasks, [])

    def test_create_follow_up_tasks_none_findings(self):
        """None findings returns empty task list."""
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", None)
        self.assertEqual(tasks, [])

    @patch('subprocess.run')
    def test_create_follow_up_tasks_success(self, mock_run):
        """Successful TaskCreate call adds task ID to list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "bad name"}
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        self.assertEqual(len(tasks), 1)
        self.assertTrue(mock_run.called)

    @patch('subprocess.run')
    def test_create_follow_up_tasks_command_not_found(self, mock_run):
        """TaskCreate command not found handled gracefully."""
        mock_run.side_effect = FileNotFoundError()

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue"}
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        # Should return empty list, not raise
        self.assertEqual(tasks, [])

    @patch('subprocess.run')
    def test_create_follow_up_tasks_timeout(self, mock_run):
        """Timeout handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)

        findings = [
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue"}
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        # Should return empty list, not raise
        self.assertEqual(tasks, [])

    @patch('subprocess.run')
    def test_create_follow_up_tasks_nonzero_exit(self, mock_run):
        """Non-zero exit code handled gracefully."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "vuln"}
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        # Should return empty list on failure
        self.assertEqual(tasks, [])

    @patch('subprocess.run')
    def test_create_follow_up_tasks_multiple_findings(self, mock_run):
        """Multiple findings create multiple tasks."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue1"},
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue2"},
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(mock_run.call_count, 2)

    @patch('subprocess.run')
    def test_create_follow_up_tasks_partial_failure(self, mock_run):
        """Partial failure returns IDs from successful tasks."""
        # First call succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Error")
        ]

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue1"},
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue2"},
        ]
        tasks = high_risk_reviewer.create_follow_up_tasks("Phase 1", findings)

        # Should have 1 task ID from first success
        self.assertEqual(len(tasks), 1)


class AppendToRecapMdTests(unittest.TestCase):
    """Tests for append_to_recap_md (Slice 9, standard)."""

    def test_append_to_recap_md_creates_file(self):
        """Creates recap.md if not present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "naming", "status": "WARN", "finding_text": "bad name"}
            ]
            result = high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings
            )

            self.assertTrue(result)
            self.assertTrue(os.path.exists(recap_path))

    def test_append_to_recap_md_adds_section(self):
        """Adds Code-Review Findings section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "naming", "status": "WARN", "finding_text": "issue"}
            ]
            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            self.assertIn("## Code-Review Findings", content)

    def test_append_to_recap_md_formats_findings(self):
        """Findings formatted correctly in recap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "security", "status": "FAIL", "finding_text": "XSS"}
            ]
            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "major", findings
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            self.assertIn("Phase 1", content)
            self.assertIn("security", content)
            self.assertIn("FAIL", content)
            self.assertIn("XSS", content)

    def test_append_to_recap_md_idempotent(self):
        """Same finding logged twice appears only once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "naming", "status": "WARN", "finding_text": "bad"}
            ]

            # Log same finding twice
            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings
            )
            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            # Count occurrences
            count = content.count("Phase 1 / naming (WARN): bad")
            self.assertEqual(count, 1)

    def test_append_to_recap_md_with_task_ids(self):
        """Task IDs included in findings entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "naming", "status": "WARN", "finding_text": "issue"}
            ]
            task_ids = ["task-123"]

            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings, task_ids
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            self.assertIn("task-123", content)

    def test_append_to_recap_md_with_issue_urls(self):
        """GitHub issue URLs included in findings entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "security", "status": "FAIL", "finding_text": "vuln"}
            ]
            issue_urls = ["https://github.com/org/repo/issues/123"]

            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "major", findings, None, issue_urls
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            self.assertIn("https://github.com/org/repo/issues/123", content)

    def test_append_to_recap_md_multiple_findings(self):
        """Multiple findings all appended."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            findings = [
                {"dimension": "naming", "status": "WARN", "finding_text": "name1"},
                {"dimension": "best_practices", "status": "FAIL", "finding_text": "practice2"},
            ]

            high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "non-major", findings
            )

            with open(recap_path, 'r') as f:
                content = f.read()

            self.assertIn("name1", content)
            self.assertIn("practice2", content)

    def test_append_to_recap_md_empty_findings(self):
        """Empty findings handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recap_path = os.path.join(tmpdir, "recap.md")

            result = high_risk_reviewer.append_to_recap_md(
                recap_path, "Phase 1", "clean", []
            )

            self.assertTrue(result)
            with open(recap_path, 'r') as f:
                content = f.read()
            self.assertIn("## Code-Review Findings", content)


class CreateGitHubIssuesTests(unittest.TestCase):
    """Tests for create_github_issues (Slice 10, high-risk)."""

    def test_create_github_issues_empty_findings(self):
        """Empty findings returns empty URL list."""
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", []
        )
        self.assertEqual(urls, [])

    def test_create_github_issues_none_findings(self):
        """None findings returns empty URL list."""
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", None
        )
        self.assertEqual(urls, [])

    @patch('subprocess.run')
    def test_create_github_issues_success(self, mock_run):
        """Successful gh issue create adds URL to list."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/org/repo/issues/123"
        )

        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "XSS"}
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        self.assertEqual(len(urls), 1)
        self.assertTrue(mock_run.called)

    @patch('subprocess.run')
    def test_create_github_issues_cli_not_found(self, mock_run):
        """gh CLI not found handled gracefully."""
        mock_run.side_effect = FileNotFoundError()

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "bad"}
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        # Should return empty list, not raise
        self.assertEqual(urls, [])

    @patch('subprocess.run')
    def test_create_github_issues_timeout(self, mock_run):
        """Timeout handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 30)

        findings = [
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue"}
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        # Should return empty list, not raise
        self.assertEqual(urls, [])

    @patch('subprocess.run')
    def test_create_github_issues_nonzero_exit(self, mock_run):
        """Non-zero exit code handled gracefully."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Auth failed")

        findings = [
            {"dimension": "security", "status": "FAIL", "finding_text": "vuln"}
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        # Should return empty list on failure
        self.assertEqual(urls, [])

    @patch('subprocess.run')
    def test_create_github_issues_multiple_findings(self, mock_run):
        """Multiple findings create multiple issues."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="https://github.com/org/repo/issues/123"),
            MagicMock(returncode=0, stdout="https://github.com/org/repo/issues/124"),
        ]

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue1"},
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue2"},
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        self.assertEqual(len(urls), 2)
        self.assertEqual(mock_run.call_count, 2)

    @patch('subprocess.run')
    def test_create_github_issues_with_task_ids(self, mock_run):
        """Task IDs included in issue body."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/org/repo/issues/123"
        )

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue"}
        ]
        task_ids = ["task-456"]

        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings, task_ids
        )

        # Check that body argument included task ID
        call_args = mock_run.call_args
        body_arg = None
        for i, arg in enumerate(call_args[0][0]):
            if arg == "--body":
                body_arg = call_args[0][0][i + 1]
                break

        self.assertIsNotNone(body_arg)
        self.assertIn("task-456", body_arg)

    @patch('subprocess.run')
    def test_create_github_issues_repo_url_parsing_https(self, mock_run):
        """Parse HTTPS repo URL correctly."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/org/repo/issues/123")

        findings = [{"dimension": "test", "status": "FAIL", "finding_text": "test"}]

        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        # Check that -R argument used correct repo slug
        call_args = mock_run.call_args
        self.assertIn("org/repo", call_args[0][0])

    @patch('subprocess.run')
    def test_create_github_issues_partial_failure(self, mock_run):
        """Partial failure returns URLs from successful issues."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="https://github.com/org/repo/issues/123"),
            MagicMock(returncode=1, stdout=""),  # Second fails
        ]

        findings = [
            {"dimension": "naming", "status": "WARN", "finding_text": "issue1"},
            {"dimension": "best_practices", "status": "FAIL", "finding_text": "issue2"},
        ]
        urls = high_risk_reviewer.create_github_issues(
            "https://github.com/org/repo", "Phase 1", findings
        )

        # Should have 1 URL from first success
        self.assertEqual(len(urls), 1)


class ClassifySeverityTests(unittest.TestCase):
    """Tests for classify_severity function."""

    def test_classify_severity_all_pass_returns_clean(self):
        """All dimensions PASS returns 'clean'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_intent_fail_returns_major(self):
        """FAIL on intent (critical) returns 'major'."""
        dimensions = {
            "intent": {"status": "FAIL", "findings": ["bad intent"]},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_regressions_warn_returns_major(self):
        """WARN on regressions (critical) returns 'major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "WARN", "findings": ["potential regression"]},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_security_fail_returns_major(self):
        """FAIL on security (critical) returns 'major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "FAIL", "findings": ["XSS vulnerability"]},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_best_practices_fail_no_majors_returns_non_major(self):
        """FAIL on best_practices (standard) with no majors returns 'non-major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "FAIL", "findings": ["poor style"]},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_naming_warn_no_majors_returns_non_major(self):
        """WARN on naming (standard) with no majors returns 'non-major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "WARN", "findings": ["variable name too short"]},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_scalability_fail_no_majors_returns_non_major(self):
        """FAIL on scalability (standard) with no majors returns 'non-major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "FAIL", "findings": ["O(n²) algorithm"]}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_multiple_standard_issues_returns_non_major(self):
        """Multiple standard dimensions with FAIL/WARN returns 'non-major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "FAIL", "findings": ["issue 1"]},
            "naming": {"status": "WARN", "findings": ["issue 2"]},
            "scalability": {"status": "FAIL", "findings": ["issue 3"]}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_major_overrides_non_major(self):
        """Major issue overrides any non-major issues."""
        dimensions = {
            "intent": {"status": "WARN", "findings": ["major issue"]},  # Critical
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "FAIL", "findings": ["minor issue"]},  # Standard
            "naming": {"status": "FAIL", "findings": ["minor issue"]},  # Standard
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_case_insensitive_status(self):
        """Status matching is case-insensitive."""
        dimensions = {
            "intent": {"status": "pass", "findings": []},  # lowercase
            "regressions": {"status": "fail", "findings": ["issue"]},  # lowercase
            "security": {"status": "PASS", "findings": []},  # uppercase
            "best_practices": {"status": "Pass", "findings": []},  # mixed case
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_missing_dimension_treated_as_pass(self):
        """Missing dimension is treated as PASS."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            # regressions missing
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            # scalability missing
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_empty_dict_returns_clean(self):
        """Empty dimensions dict returns 'clean'."""
        dimensions = {}
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_missing_status_field_treated_as_pass(self):
        """Missing 'status' field in dimension treated as PASS."""
        dimensions = {
            "intent": {"findings": []},  # No status field
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_all_critical_dimensions_fail(self):
        """All critical dimensions with FAIL returns 'major'."""
        dimensions = {
            "intent": {"status": "FAIL", "findings": ["issue 1"]},
            "regressions": {"status": "FAIL", "findings": ["issue 2"]},
            "security": {"status": "FAIL", "findings": ["issue 3"]},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_all_standard_dimensions_fail(self):
        """All standard dimensions with FAIL and no major issues returns 'non-major'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "FAIL", "findings": ["issue 1"]},
            "naming": {"status": "FAIL", "findings": ["issue 2"]},
            "scalability": {"status": "FAIL", "findings": ["issue 3"]}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_mixed_critical_statuses_no_fail_warn_returns_clean(self):
        """Critical dimensions without FAIL/WARN return 'clean'."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_findings_with_empty_list(self):
        """Empty findings list does not affect severity classification."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "WARN", "findings": []},  # WARN but empty findings
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")

    def test_classify_severity_findings_with_multiple_items(self):
        """Multiple findings in a dimension do not affect classification."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {
                "status": "FAIL",
                "findings": ["issue 1", "issue 2", "issue 3"]
            },
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "non-major")

    def test_classify_severity_unknown_status_treated_as_pass(self):
        """Unknown status value treated as PASS."""
        dimensions = {
            "intent": {"status": "UNKNOWN", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "PASS", "findings": []},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "PASS", "findings": []},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "clean")

    def test_classify_severity_security_warn_plus_naming_fail(self):
        """Security WARN (major) overrides naming FAIL (non-major)."""
        dimensions = {
            "intent": {"status": "PASS", "findings": []},
            "regressions": {"status": "PASS", "findings": []},
            "security": {"status": "WARN", "findings": ["potential vulnerability"]},
            "best_practices": {"status": "PASS", "findings": []},
            "naming": {"status": "FAIL", "findings": ["bad name"]},
            "scalability": {"status": "PASS", "findings": []}
        }
        result = high_risk_reviewer.classify_severity(dimensions)
        self.assertEqual(result, "major")


if __name__ == "__main__":
    unittest.main()
