"""planner.plan: board-side changes since last sync + recap line; never our own writes (F5)."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

STATE = "- Slug: s\n- Current Phase: Implementation\n- Workflow Status: In Progress\n- Next Action: build\n"
NOTES = "Phase: Implementation · Next: build · Spec: s"


def synced_pair(board_status="In progress"):
    """A sidecar + board item as they are right after a clean sync."""
    sc = store.default_sidecar()
    sc["item_id"] = "1"
    it = {"id": "1", "status": "To do", "notes": "", "code_link": "", "updated_at": "t0",
          "updates": [{"id": "u1", "body": "hello", "created_at": "2026-09-29"}]}
    p = planner.plan(STATE, sc, None, it, "s", now="n0")
    sc.update(p["snapshot"])
    it = dict(it, status=board_status, notes=NOTES, updated_at="t1")  # our writes landed
    return sc, it


def test_own_writes_are_not_reported_as_changes():
    sc, it = synced_pair()
    p = planner.plan(STATE, sc, None, it, "s", now="n1")
    assert p["changes"] == [] and p["recap_line"] is None


def test_user_status_notes_and_new_updates_are_reported():
    sc, it = synced_pair()
    it["status"] = "Review"
    it["notes"] = "user wrote this"
    it["updates"] = it["updates"] + [{"id": "u2", "body": "<p>ping</p>", "created_at": "2026-09-30"}]
    p = planner.plan(STATE, sc, None, it, "s", now="2026-09-30")
    assert {"kind": "status", "from": "In progress", "to": "Review"} in p["changes"]
    assert {"kind": "notes", "text": "user wrote this"} in p["changes"]
    assert {"kind": "update", "id": "u2", "text": "ping"} in p["changes"]
    assert len(p["changes"]) == 3
    assert p["recap_line"].startswith("- 2026-09-30 Board changes: ")
    assert "Review" in p["recap_line"] and "ping" in p["recap_line"]


def test_first_sync_reports_nothing():
    sc = store.default_sidecar()
    sc["item_id"] = "1"
    it = {"id": "1", "status": "Review", "notes": "x", "updates": [{"id": "u1", "body": "b"}]}
    assert planner.plan(STATE, sc, None, it, "s")["changes"] == []


def test_unknown_last_update_id_falls_back_to_created_at():
    sc, it = synced_pair()
    sc["last_seen_board"] = dict(sc["last_seen_board"], last_update_id="gone",
                                 update_created_at="2026-09-29")
    it["updates"] = [{"id": "u1", "body": "old", "created_at": "2026-09-29"},
                     {"id": "u2", "body": "new", "created_at": "2026-09-30"}]
    changes = planner.plan(STATE, sc, None, it, "s")["changes"]
    assert [c["id"] for c in changes if c["kind"] == "update"] == ["u2"]


def test_unknown_last_update_id_without_created_at_reports_nothing():
    sc, it = synced_pair()
    sc["last_seen_board"] = dict(sc["last_seen_board"], last_update_id="gone", update_created_at=None)
    it["updates"] = [{"id": "u2", "body": "new", "created_at": "2026-09-30"}]
    assert planner.plan(STATE, sc, None, it, "s")["changes"] == []


def test_snapshot_stores_latest_update_created_at():
    sc, it = synced_pair()
    assert sc["last_seen_board"]["update_created_at"] == "2026-09-29"
