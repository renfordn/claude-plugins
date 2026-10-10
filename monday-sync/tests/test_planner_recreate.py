"""planner.plan: a linked item deleted on the board is recreated once, then the user is asked (F7)."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

STATE = "- Slug: s\n- Current Phase: Design\n- Workflow Status: In Progress\n"


def linked(**kw):
    sc = store.default_sidecar()
    sc.update(item_id="111", last_pushed={"status": "Review", "source": "git"},
              last_seen_board={"status": "Review", "updated_at": "t", "last_update_id": "u9"}, **kw)
    return sc


def test_missing_item_is_recreated_once_with_reset_snapshot():
    p = planner.plan(STATE, linked(), None, None, "s")
    assert p["recreate"] == "recreate" and p["create"] is True
    assert p["writes"][planner.STATUS_COL] == "Gather Requirements"
    snap = p["snapshot"]
    assert snap["recreated_from"] == "111" and snap["item_id"] is None
    assert snap["last_pushed"]["status"] == "Gather Requirements" and snap["last_seen_board"]["last_update_id"] is None


def test_missing_again_after_recreate_asks_and_writes_nothing():
    p = planner.plan(STATE, linked(recreated_from="100"), None, None, "s")
    assert p["recreate"] == "ask" and p["create"] is False and p["writes"] == {}
    assert p["conflicts"][0]["kind"] == "item_missing" and p["snapshot"] is None


def test_unlinked_feature_is_a_plain_create_not_a_recreate():
    p = planner.plan(STATE, store.default_sidecar(), None, None, "s")
    assert p["recreate"] is None and p["create"] is True
