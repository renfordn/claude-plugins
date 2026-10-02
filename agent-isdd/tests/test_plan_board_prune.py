"""hooks/plan_board_sync.py -- pruning orphaned Plan Board sync entries.

An orphan is a sync-file entry (id `<project>--<slug>`) with no feature dir under <memory_dir>/spec/.
plan_prune only plans; apply_prune deletes sync entries only when confirmed is True. Board-side
deletes are returned as instructions, never performed.
"""
import json
import os
import sys

import hook_test_utils as h

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import plan_board_sync  # noqa: E402

GONE = "proj--2026-08-01-gone"
GONE2 = "proj--2026-08-02-gone-too"
LIVE = "proj--2026-09-01-alive"


def _mem(tmp_path, sync, name="mem"):
    mem = tmp_path / name
    h.seed_state_file(str(mem / "spec" / "2026-09-01-alive"), title="alive", slug="2026-09-01-alive")
    if sync is not None:
        (mem / "plan-board-sync.json").write_text(sync if isinstance(sync, str) else json.dumps(sync))
    return mem


def _entries(mem):
    return json.loads((mem / "plan-board-sync.json").read_text())


def test_plan_prune_returns_candidates_and_confirmation_and_deletes_nothing(tmp_path):
    mem = _mem(tmp_path, {GONE: "h1", GONE2: "h2", LIVE: "h3"})
    before = (mem / "plan-board-sync.json").read_text()
    plan = plan_board_sync.plan_prune([GONE, GONE2])
    assert sorted(plan["candidates"]) == sorted([GONE, GONE2])
    assert isinstance(plan["confirmation"], str)
    assert GONE in plan["confirmation"] and GONE2 in plan["confirmation"]
    assert (mem / "plan-board-sync.json").read_text() == before


def test_unconfirmed_apply_removes_nothing(tmp_path):
    mem = _mem(tmp_path, {GONE: "h1", LIVE: "h3"})
    sync = str(mem / "plan-board-sync.json")
    for flag in (False, None, "yes", 1):
        plan_board_sync.apply_prune(sync, [GONE], flag)
        assert _entries(mem) == {GONE: "h1", LIVE: "h3"}


def test_confirmed_apply_removes_only_the_orphan_entries(tmp_path):
    mem = _mem(tmp_path, {GONE: "h1", GONE2: "h2", LIVE: "h3"})
    sync = str(mem / "plan-board-sync.json")
    result = plan_board_sync.apply_prune(sync, [GONE], True)
    assert _entries(mem) == {GONE2: "h2", LIVE: "h3"}
    assert GONE in result["removed"]
    # Board-side delete is an instruction for the caller, not an action taken here.
    assert any(GONE in str(i) for i in result["board_instructions"])


def test_id_with_a_live_feature_dir_is_never_removed(tmp_path):
    mem = _mem(tmp_path, {GONE: "h1", LIVE: "h3"})
    sync = str(mem / "plan-board-sync.json")
    result = plan_board_sync.apply_prune(sync, [LIVE, GONE], True)
    assert _entries(mem) == {LIVE: "h3"}
    assert LIVE not in result["removed"]
    assert not any(LIVE in str(i) for i in result["board_instructions"])


def test_state_files_and_other_projects_are_untouched(tmp_path):
    mem = _mem(tmp_path, {GONE: "h1", LIVE: "h3"})
    other = _mem(tmp_path, {GONE: "o1"}, name="other")
    state = mem / "spec" / "2026-09-01-alive" / "workflow-state.md"
    state_before, other_before = state.read_text(), (other / "plan-board-sync.json").read_text()
    plan_board_sync.apply_prune(str(mem / "plan-board-sync.json"), [GONE], True)
    assert state.read_text() == state_before
    assert (other / "plan-board-sync.json").read_text() == other_before
    assert sorted(os.listdir(mem / "spec")) == ["2026-09-01-alive"]


def test_missing_sync_file_is_a_no_op_and_not_created(tmp_path):
    mem = _mem(tmp_path, None)
    sync = mem / "plan-board-sync.json"
    result = plan_board_sync.apply_prune(str(sync), [GONE], True)
    assert not sync.exists()
    assert result["removed"] == []


def test_corrupt_sync_file_is_left_byte_for_byte(tmp_path):
    mem = _mem(tmp_path, "{not json")
    sync = mem / "plan-board-sync.json"
    result = plan_board_sync.apply_prune(str(sync), [GONE], True)
    assert sync.read_text() == "{not json"
    assert result["removed"] == []
