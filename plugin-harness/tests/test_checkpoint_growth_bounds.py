"""Regression tests for the 2026-09-24 workflow-state.json disk blow-up.

Each checkpoint used to snapshot orchestration.checkpoints, so every snapshot
nested all prior ones and the file doubled per checkpoint (up to 18 GB), and
failed writes of those payloads left orphaned `.workflow-state-*.tmp` files.
"""

import json
import os
import tempfile
import time
import unittest
import unittest.mock

from orchestrator.checkpoint import (
    MAX_CHECKPOINTS,
    MAX_HANDOFF_HISTORY,
    SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS,
    CheckpointManager,
)
from orchestrator.error_handler import ErrorHandler
from orchestrator.hooks.subagent_stop import _log_handoff
from orchestrator.state_store import FileStateStore


def _state():
    return {
        "phase": "Design",
        "payload": "x" * 2000,
        "orchestration": {"checkpoints": [], "handoff_history": []},
    }


class TestCheckpointGrowth(unittest.TestCase):
    def setUp(self):
        self.manager = CheckpointManager()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = FileStateStore(self.tmp.name)

    def _size(self):
        return os.path.getsize(os.path.join(self.tmp.name, "workflow-state.json"))

    def test_successive_checkpoints_grow_linearly_then_plateau(self):
        state = _state()
        sizes = []
        for i in range(MAX_CHECKPOINTS * 2):
            state = self.store.get("workflow-state") or state
            self.manager.record_handoff(state, {"i": i})
            self.manager.create_checkpoint(state, f"cp{i}")
            self.store.save("workflow-state", state)
            sizes.append(self._size())

        per_checkpoint = sizes[1] - sizes[0]
        # Linear: the Nth file is ~N snapshots, not 2**N.
        self.assertLess(sizes[MAX_CHECKPOINTS - 1], sizes[0] + per_checkpoint * MAX_CHECKPOINTS * 1.5)
        # Capped: once pruning kicks in, size stops growing.
        self.assertLess(sizes[-1], sizes[MAX_CHECKPOINTS - 1] * 1.2)

        on_disk = self.store.get("workflow-state")
        self.assertEqual(len(on_disk["orchestration"]["checkpoints"]), MAX_CHECKPOINTS)
        for cp in on_disk["orchestration"]["checkpoints"]:
            snap_orch = cp["state_snapshot"].get("orchestration", {})
            for key in SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS:
                self.assertNotIn(key, snap_orch)

    def test_legacy_nested_snapshots_are_stripped_on_next_checkpoint(self):
        nested = _state()
        nested["orchestration"]["checkpoints"] = [
            {"checkpoint_id": "old", "label": "old", "timestamp": "t", "state_snapshot": _state()}
        ]
        state = _state()
        state["orchestration"]["checkpoints"] = [
            {"checkpoint_id": "legacy", "label": "l", "timestamp": "t", "state_snapshot": nested}
        ]
        self.manager.create_checkpoint(state, "new")
        for cp in state["orchestration"]["checkpoints"]:
            self.assertNotIn("checkpoints", cp["state_snapshot"]["orchestration"])

    def test_restore_keeps_current_checkpoints_and_history(self):
        state = _state()
        first = self.manager.create_checkpoint(state, "first")
        state["phase"] = "Implementation"
        self.manager.record_handoff(state, {"step": 1})
        self.manager.create_checkpoint(state, "second")

        restored = self.manager.restore_checkpoint(state, first)

        self.assertEqual(restored["phase"], "Design")
        self.assertEqual(restored["rollback_pending"]["checkpoint_restored"], first)
        self.assertEqual(
            [cp["checkpoint_id"] for cp in restored["orchestration"]["checkpoints"]],
            [cp["checkpoint_id"] for cp in state["orchestration"]["checkpoints"]],
        )
        self.assertEqual(restored["orchestration"]["handoff_history"],
                         state["orchestration"]["handoff_history"])
        # Deep copies, not aliases.
        self.assertIsNot(restored["orchestration"]["checkpoints"], state["orchestration"]["checkpoints"])
        # The restored state can itself be restored from again.
        again = self.manager.restore_checkpoint(restored, first)
        self.assertEqual(again["phase"], "Design")


class TestHandoffHistoryCap(unittest.TestCase):
    def test_record_handoff_caps_history(self):
        state = _state()
        manager = CheckpointManager()
        for i in range(MAX_HANDOFF_HISTORY + 25):
            manager.record_handoff(state, {"i": i})
        history = state["orchestration"]["handoff_history"]
        self.assertEqual(len(history), MAX_HANDOFF_HISTORY)
        self.assertEqual(history[-1]["i"], MAX_HANDOFF_HISTORY + 24)

    def test_error_handler_log_error_caps_history(self):
        state = _state()
        handler = ErrorHandler.__new__(ErrorHandler)
        for i in range(MAX_HANDOFF_HISTORY + 5):
            handler.log_error(state, "e", "a", "b", "skip", str(i))
        self.assertEqual(len(state["orchestration"]["handoff_history"]), MAX_HANDOFF_HISTORY)

    def test_subagent_stop_log_handoff_caps_history(self):
        state = _state()
        for _ in range(MAX_HANDOFF_HISTORY + 5):
            _log_handoff(state, "agent-tdd", None, "contract_valid", {}, True)
        self.assertEqual(len(state["orchestration"]["handoff_history"]), MAX_HANDOFF_HISTORY)


class TestFileStateStoreTempCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = FileStateStore(self.tmp.name)

    def _tmp_files(self):
        return [f for f in os.listdir(self.tmp.name) if f.endswith(".tmp")]

    def test_failed_write_removes_temp_file(self):
        with unittest.mock.patch("orchestrator.state_store.json.dump", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save("workflow-state", {"a": 1})
        self.assertEqual(self._tmp_files(), [])

    def test_interrupted_write_removes_temp_file(self):
        with unittest.mock.patch("orchestrator.state_store.os.replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.store.save("workflow-state", {"a": 1})
        self.assertEqual(self._tmp_files(), [])

    def test_successful_write_sweeps_stale_temp_files_only(self):
        stale = os.path.join(self.tmp.name, ".workflow-state-stale.tmp")
        fresh = os.path.join(self.tmp.name, ".workflow-state-fresh.tmp")
        other = os.path.join(self.tmp.name, ".other-stale.tmp")
        for p in (stale, fresh, other):
            with open(p, "w") as f:
                f.write("{}")
        old = time.time() - FileStateStore.STALE_TMP_SECONDS - 60
        os.utime(stale, (old, old))
        os.utime(other, (old, old))

        self.store.save("workflow-state", {"a": 1})

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(fresh))  # may belong to a concurrent writer
        self.assertTrue(os.path.exists(other))  # another workflow's file
        with open(os.path.join(self.tmp.name, "workflow-state.json")) as f:
            self.assertEqual(json.load(f), {"a": 1})


if __name__ == "__main__":
    unittest.main()
