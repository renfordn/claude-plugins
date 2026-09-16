"""Tests for hooks/direct_mode_state.py.

Slice 1 of making `skills/design-spec-direct/SKILL.md`'s "Caller-owned loop" persistence
concrete: read/write direct-mode-state.json and update one slice's status, mirroring
tdd_state.py's read/write pattern (see that module's own tests for the convention this
follows) rather than introducing a new one.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import direct_mode_state


DEFAULT_SHAPE = {"mode": "direct", "tasks_file": None, "current_slice": None, "slices": []}


class ReadDirectModeStateTests(unittest.TestCase):
    def test_missing_file_returns_default_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = direct_mode_state.read_direct_mode_state(os.path.join(tmp, "nonexistent"))
            self.assertEqual(result, DEFAULT_SHAPE)

    def test_malformed_json_returns_default_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = direct_mode_state.direct_mode_memory_dir(tmp)
            os.makedirs(mem, exist_ok=True)
            with open(os.path.join(mem, "direct-mode-state.json"), "w") as f:
                f.write("not json{{{")
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result, DEFAULT_SHAPE)

    def test_wrong_schema_not_a_dict_returns_default_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = direct_mode_state.direct_mode_memory_dir(tmp)
            os.makedirs(mem, exist_ok=True)
            with open(os.path.join(mem, "direct-mode-state.json"), "w") as f:
                json.dump(["not", "a", "dict"], f)
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result, DEFAULT_SHAPE)

    def test_wrong_schema_slices_not_a_list_returns_default_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = direct_mode_state.direct_mode_memory_dir(tmp)
            os.makedirs(mem, exist_ok=True)
            with open(os.path.join(mem, "direct-mode-state.json"), "w") as f:
                json.dump({"mode": "direct", "slices": "not-a-list"}, f)
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result, DEFAULT_SHAPE)

    def test_valid_file_round_trips_through_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "mode": "direct",
                "tasks_file": "tasks/tasks.md",
                "current_slice": "Slice 1",
                "slices": [{"id": "Slice 1", "status": "pending", "risk_tier": "standard"}],
            }
            direct_mode_state.write_direct_mode_state(tmp, data)
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result, data)


class DefaultShapeIsolationTests(unittest.TestCase):
    def test_mutating_one_projects_default_does_not_leak_into_another(self):
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            direct_mode_state.set_slice_status(tmp_a, "Slice 1", "pending")
            self.assertEqual(direct_mode_state.read_direct_mode_state(tmp_b)["slices"], [])


class WriteDirectModeStateTests(unittest.TestCase):
    def test_creates_parent_dirs_as_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            mem = direct_mode_state.direct_mode_memory_dir(tmp)
            self.assertTrue(os.path.isfile(os.path.join(mem, "direct-mode-state.json")))

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(
                tmp, {**DEFAULT_SHAPE, "tasks_file": "tasks/tasks.md"}
            )
            direct_mode_state.write_direct_mode_state(
                tmp, {**DEFAULT_SHAPE, "tasks_file": "tasks/other.md"}
            )
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result["tasks_file"], "tasks/other.md")


class SetSliceStatusTests(unittest.TestCase):
    def test_updates_status_of_existing_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(
                tmp,
                {
                    **DEFAULT_SHAPE,
                    "slices": [{"id": "Slice 1", "status": "pending", "risk_tier": "standard"}],
                },
            )
            direct_mode_state.set_slice_status(tmp, "Slice 1", "red_green_done")
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result["slices"][0]["status"], "red_green_done")

    def test_appends_slice_when_id_not_seen_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(
                tmp, "Slice 1", "pending", risk_tier="high-risk"
            )
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(len(result["slices"]), 1)
            self.assertEqual(
                result["slices"][0],
                {"id": "Slice 1", "status": "pending", "risk_tier": "high-risk"},
            )

    def test_updates_current_slice_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(tmp, "Slice 2", "awaiting_review")
            result = direct_mode_state.read_direct_mode_state(tmp)
            self.assertEqual(result["current_slice"], "Slice 2")

    def test_rejects_unknown_status_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            with self.assertRaises(ValueError):
                direct_mode_state.set_slice_status(tmp, "Slice 1", "not-a-real-status")

    def test_accepts_every_documented_status_value(self):
        # pending, red_green_done, awaiting_review, blocked, done — per SKILL.md's
        # "Caller-owned loop" section.
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            for status in ("pending", "red_green_done", "awaiting_review", "blocked", "done"):
                direct_mode_state.set_slice_status(tmp, "Slice 1", status)
                result = direct_mode_state.read_direct_mode_state(tmp)
                self.assertEqual(result["slices"][0]["status"], status)


class AllSlicesDoneTests(unittest.TestCase):
    def test_false_when_no_slices_exist_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            self.assertFalse(direct_mode_state.all_slices_done(tmp))

    def test_false_when_any_slice_is_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(tmp, "Slice 1", "done")
            direct_mode_state.set_slice_status(tmp, "Slice 2", "awaiting_review")
            self.assertFalse(direct_mode_state.all_slices_done(tmp))

    def test_true_when_every_slice_is_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(tmp, "Slice 1", "done")
            direct_mode_state.set_slice_status(tmp, "Slice 2", "done")
            self.assertTrue(direct_mode_state.all_slices_done(tmp))


class FirstIncompleteSliceIdTests(unittest.TestCase):
    def test_returns_first_id_not_marked_done_in_given_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(tmp, "Slice 1", "done")
            result = direct_mode_state.first_incomplete_slice_id(
                tmp, ["Slice 1", "Slice 2", "Slice 3"]
            )
            self.assertEqual(result, "Slice 2")

    def test_treats_a_slice_absent_from_state_as_incomplete(self):
        # A slice tasks.md names but that has never had set_slice_status called for it
        # yet (i.e. not started) must count as incomplete, not error or get skipped.
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            result = direct_mode_state.first_incomplete_slice_id(tmp, ["Slice 1", "Slice 2"])
            self.assertEqual(result, "Slice 1")

    def test_returns_none_when_every_named_slice_is_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            direct_mode_state.set_slice_status(tmp, "Slice 1", "done")
            direct_mode_state.set_slice_status(tmp, "Slice 2", "done")
            result = direct_mode_state.first_incomplete_slice_id(tmp, ["Slice 1", "Slice 2"])
            self.assertIsNone(result)

    def test_respects_given_order_not_state_file_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct_mode_state.write_direct_mode_state(tmp, DEFAULT_SHAPE)
            # state file ends up with Slice 2 recorded before Slice 1
            direct_mode_state.set_slice_status(tmp, "Slice 2", "done")
            direct_mode_state.set_slice_status(tmp, "Slice 1", "blocked")
            result = direct_mode_state.first_incomplete_slice_id(tmp, ["Slice 1", "Slice 2"])
            self.assertEqual(result, "Slice 1")


if __name__ == "__main__":
    unittest.main()
