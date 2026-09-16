"""Tests for orchestrator/hook_telemetry.py and its wiring into the two hook
entrypoints Claude Code actually invokes (hooks/before_continue.py,
hooks/subagent_stop.py).

Covers the gap code-reviewer flagged: this wiring previously shipped with no
test coverage of its own, so a regression (e.g. emit() silently swallowing
events, or the off-switch env var stopping working) would only ever surface
as a missing/empty hook_telemetry_log.jsonl someone happens to notice much
later -- the exact class of problem this wiring exists to fix.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.hook_telemetry import get_hook_telemetry_logger
from orchestrator.telemetry_sinks import JSONLFileHook

BEFORE_CONTINUE_SCRIPT = Path(__file__).parent.parent / "hooks" / "before_continue.py"
SUBAGENT_STOP_SCRIPT = Path(__file__).parent.parent / "hooks" / "subagent_stop.py"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_jsonl(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestHookTelemetryLogger(unittest.TestCase):
    """Unit coverage for the logger itself, independent of any hook script."""

    def test_emit_writes_one_well_formed_json_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            logger = get_hook_telemetry_logger(state_dir)
            logger.emit("hook_invoked", hook="before_continue", agent_type="agent-tdd")

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["event_type"], "hook_invoked")
            self.assertEqual(record["hook"], "before_continue")
            self.assertEqual(record["agent_type"], "agent-tdd")
            self.assertIn("timestamp", record)
            self.assertIn("logged_at", record)

    def test_multiple_emits_append_multiple_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            logger = get_hook_telemetry_logger(state_dir)
            logger.emit("hook_invoked", hook="subagent_stop")
            logger.emit("hook_completed", hook="subagent_stop", outcome="ok")

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            self.assertEqual([r["event_type"] for r in records], ["hook_invoked", "hook_completed"])

    def test_no_workflow_state_dir_is_a_safe_no_op(self):
        logger = get_hook_telemetry_logger(None)
        logger.emit("hook_invoked", hook="before_continue")  # must not raise

    @patch.dict(os.environ, {"PLUGIN_ORCHESTRATOR_TELEMETRY": "off"})
    def test_env_off_switch_suppresses_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            logger = get_hook_telemetry_logger(state_dir)
            logger.emit("hook_invoked", hook="before_continue")
            self.assertFalse((state_dir / "hook_telemetry_log.jsonl").exists())

    def test_a_hook_that_raises_never_propagates(self):
        """TelemetryPublisher.emit's own fail-closed contract: a broken sink
        never breaks the caller, even if the underlying file write fails."""
        with tempfile.TemporaryDirectory() as tmp:
            # Point the sink's path at something that can never be a valid
            # file (a directory), forcing the write to fail.
            bad_path = Path(tmp)
            logger = get_hook_telemetry_logger(None)
            logger.publisher.register_hook(JSONLFileHook(bad_path))
            logger.emit("hook_invoked", hook="before_continue")  # must not raise


class TestJSONLFileHookMkdirCaching(unittest.TestCase):
    """Regression test for the mkdir-per-emit nit: mkdir must only run once
    the directory doesn't yet exist, not unconditionally on every event."""

    def test_mkdir_called_at_most_once_across_repeated_emits(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "nested" / "hook_telemetry_log.jsonl"
            hook = JSONLFileHook(log_path)
            with patch.object(Path, "mkdir", wraps=Path.mkdir, autospec=True) as mock_mkdir:
                hook({"event_type": "a"})
                hook({"event_type": "b"})
                hook({"event_type": "c"})
            self.assertEqual(mock_mkdir.call_count, 1)
            self.assertEqual(len(_read_jsonl(log_path)), 3)


class TestBeforeContinueHookTelemetry(unittest.TestCase):
    """Confirms hooks/before_continue.py actually emits telemetry, not just
    that the underlying logger works in isolation."""

    def test_emits_invoked_and_completed_on_normal_run(self):
        module = _load_module(BEFORE_CONTINUE_SCRIPT, "_before_continue_telemetry")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state_path = str(state_dir / "workflow-state.json")
            fake_state = {"feature": "test-feature", "orchestration": {}}
            tool_input = {"prompt": "original prompt", "subagent_type": "agent-tdd"}
            stdin_payload = json.dumps({
                "cwd": tmp, "tool_name": "Agent", "tool_input": tool_input,
            })
            with patch.object(module, "workflow_state_path", return_value=state_path), \
                 patch.object(module, "load_workflow_state", return_value=fake_state), \
                 patch.object(module, "save_workflow_state"), \
                 patch("orchestrator.hooks.before_continue.handle_agent_spawn"), \
                 patch("sys.stdin", io.StringIO(stdin_payload)), \
                 patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    module.main()

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            event_types = [r["event_type"] for r in records]
            self.assertEqual(event_types, ["hook_invoked", "hook_completed"])
            self.assertEqual(records[1]["outcome"], "ok")
            self.assertEqual(records[1]["agent_type"], "agent-tdd")

    def test_emits_hook_error_on_unexpected_exception(self):
        module = _load_module(BEFORE_CONTINUE_SCRIPT, "_before_continue_telemetry_err")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state_path = str(state_dir / "workflow-state.json")
            tool_input = {"prompt": "original prompt", "subagent_type": "agent-tdd"}
            stdin_payload = json.dumps({
                "cwd": tmp, "tool_name": "Agent", "tool_input": tool_input,
            })
            with patch.object(module, "workflow_state_path", return_value=state_path), \
                 patch.object(module, "load_workflow_state", side_effect=RuntimeError("boom")), \
                 patch("sys.stdin", io.StringIO(stdin_payload)), \
                 patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    module.main()

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            self.assertEqual([r["event_type"] for r in records], ["hook_invoked", "hook_error"])
            self.assertEqual(records[1]["error_type"], "RuntimeError")


class TestSubagentStopHookTelemetry(unittest.TestCase):
    """Confirms hooks/subagent_stop.py actually emits telemetry."""

    def test_emits_invoked_and_completed_on_normal_run(self):
        module = _load_module(SUBAGENT_STOP_SCRIPT, "_subagent_stop_telemetry")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state_path = str(state_dir / "workflow-state.json")
            fake_state = {"orchestration": {"handoff_history": []}}
            stdin_payload = json.dumps({
                "cwd": tmp,
                "agent_type": "agent-tdd",
                "last_assistant_message": "Agent completed successfully.",
            })
            with patch.object(module, "workflow_state_path", return_value=state_path), \
                 patch.object(module, "load_workflow_state", return_value=fake_state), \
                 patch.object(module, "save_workflow_state"), \
                 patch(
                     "orchestrator.hooks.subagent_stop.handle_agent_completion",
                     return_value={
                         "success": True, "validation_result": "contract_valid",
                         "error_details": {}, "escalation_marker": None,
                         "recovery_action": None,
                     },
                 ), \
                 patch("sys.stdin", io.StringIO(stdin_payload)), \
                 patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    module.main()

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            event_types = [r["event_type"] for r in records]
            self.assertEqual(event_types, ["hook_invoked", "hook_completed"])
            self.assertEqual(records[1]["validation_result"], "contract_valid")
            self.assertEqual(records[1]["escalation_marker"], False)

    def test_emits_hook_error_when_handle_agent_completion_raises(self):
        module = _load_module(SUBAGENT_STOP_SCRIPT, "_subagent_stop_telemetry_err")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state_path = str(state_dir / "workflow-state.json")
            fake_state = {"orchestration": {"handoff_history": []}}
            stdin_payload = json.dumps({
                "cwd": tmp,
                "agent_type": "agent-tdd",
                "last_assistant_message": "Agent completed successfully.",
            })
            with patch.object(module, "workflow_state_path", return_value=state_path), \
                 patch.object(module, "load_workflow_state", return_value=fake_state), \
                 patch(
                     "orchestrator.hooks.subagent_stop.handle_agent_completion",
                     side_effect=RuntimeError("boom"),
                 ), \
                 patch("sys.stdin", io.StringIO(stdin_payload)), \
                 patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    module.main()

            records = _read_jsonl(state_dir / "hook_telemetry_log.jsonl")
            self.assertEqual([r["event_type"] for r in records], ["hook_invoked", "hook_error"])
            self.assertEqual(records[1]["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
