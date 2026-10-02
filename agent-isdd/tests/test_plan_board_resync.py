"""hooks/plan_board_sync.py -- resync: one batch for every stale or missing record."""
import json
import os
import sys

import hook_test_utils as h

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import plan_board  # noqa: E402
import plan_board_sync  # noqa: E402

URL = "https://claude.ai/artifact/PLANBOARD123"
SLUGS = ("2026-09-01-synced", "2026-09-02-stale", "2026-09-03-missing")


def _mem(tmp_path, sync_line=""):
    mem = tmp_path / "mem"
    for slug in SLUGS:
        h.seed_state_file(str(mem / "spec" / slug), title=slug, slug=slug,
                          current_phase="Design", workflow_status="In Progress")
    (mem / "PLAN-BOARD.md").write_text(f"# Plan Board\n\n- URL: {URL}\n{sync_line}")
    return str(mem)


def _doc(mem, slug):
    return plan_board.build_doc(os.path.join(mem, "spec", slug, "workflow-state.md"), project="proj")


def _board(mem):
    synced, stale = _doc(mem, SLUGS[0]), _doc(mem, SLUGS[1])
    return {synced["id"]: synced["contentHash"], stale["id"]: "old-hash"}


def test_batch_has_one_set_per_stale_or_missing_record_and_none_for_synced(tmp_path):
    mem = _mem(tmp_path)
    batch = plan_board_sync.build_batch(mem, "proj", _board(mem))
    ids = [op["id"] for op in batch["ops"]]
    assert ids == [_doc(mem, SLUGS[1])["id"], _doc(mem, SLUGS[2])["id"]]
    for op in batch["ops"]:
        assert op["op"] == "set" and op["collection"] == "plans"
        assert op["data"]["id"] == op["id"] and op["data"]["schema"] == 2
    assert batch["ids"] == ids


def test_nothing_to_do_gives_an_empty_batch(tmp_path):
    mem = _mem(tmp_path)
    board = {_doc(mem, s)["id"]: _doc(mem, s)["contentHash"] for s in SLUGS}
    assert plan_board_sync.build_batch(mem, "proj", board)["ops"] == []


def test_sync_off_gives_an_empty_batch(tmp_path):
    mem = _mem(tmp_path, "- Sync: off\n")
    assert plan_board_sync.build_batch(mem, "proj", {})["ops"] == []


def test_only_successful_ids_are_marked_synced(tmp_path):
    mem = _mem(tmp_path)
    ok, failed = _doc(mem, SLUGS[1])["id"], _doc(mem, SLUGS[2])["id"]
    assert plan_board_sync.mark_success(mem, "proj", [ok]) == [ok]
    synced = json.loads(open(os.path.join(mem, "plan-board-sync.json")).read())
    assert synced == {ok: _doc(mem, SLUGS[1])["contentHash"]}
    assert failed not in synced
    assert failed in [s[2]["id"] for s in plan_board.stale_features(mem, "proj")]
