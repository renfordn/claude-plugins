"""planner.plan: diff-only writes, snapshot, idempotency."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

STATE = """- Title: Feature X
- Slug: 2026-09-30-x
- Current Phase: Implementation
- Workflow Status: In Progress
- Next Action: build it
"""
GIT = {"branch": "claude/x", "on_origin": True, "ahead": 2, "head": "h1", "merged": False,
       "merge_subject": "", "origin_url": "git@github.com:o/r.git"}
S, N, L = planner.STATUS_COL, planner.NOTES_COL, planner.LINK_COL


def sidecar(**kw):
    sc = store.default_sidecar()
    sc.update({"project": "file-organiser", "branch": "claude/x"}, **kw)
    return sc


def item(**kw):
    it = {"id": "1", "name": "[file-organiser] Feature X", "status": "To do", "notes": "",
          "code_link": "", "updated_at": "t0", "updates": []}
    it.update(kw)
    return it


def apply(it, writes):
    it = dict(it)
    for col, key in ((S, "status"), (N, "notes"), (L, "code_link")):
        if col in writes:
            it[key] = writes[col]
    return it


def test_unlinked_feature_plans_a_create_with_all_columns():
    p = planner.plan(STATE, sidecar(), GIT, None, "2026-09-30-x")
    assert p["create"] is True
    assert p["writes"][S] == "Review"
    assert p["writes"][N] == "Phase: Implementation · Next: build it · Spec: 2026-09-30-x"
    assert p["writes"][L] == "https://github.com/o/r/tree/claude/x"
    assert p["writes"][planner.TYPE_COL] == "Feature" and p["writes"][planner.PROJECT_COL] == "file-organiser"


def test_linked_item_gets_only_differing_columns():
    sc = sidecar(item_id="1")
    it = item(notes="Phase: Implementation · Next: build it · Spec: 2026-09-30-x")
    p = planner.plan(STATE, sc, GIT, it, "2026-09-30-x")
    assert p["create"] is False
    assert set(p["writes"]) == {S, L}


def test_second_plan_after_applying_snapshot_makes_zero_writes():
    sc = sidecar(item_id="1")
    it = item()
    p1 = planner.plan(STATE, sc, GIT, it, "2026-09-30-x", now="n1")
    sc.update(p1["snapshot"])
    p2 = planner.plan(STATE, sc, GIT, apply(it, p1["writes"]), "2026-09-30-x", now="n2")
    assert p2["writes"] == {} and p2["isdd_updates"] == {} and p2["conflicts"] == []


def test_snapshot_records_pushed_head_last_pushed_and_synced_fields():
    p = planner.plan(STATE, sidecar(item_id="1"), GIT, item(), "2026-09-30-x", now="n1")
    snap = p["snapshot"]
    assert snap["pushed_head"] == "h1"
    assert snap["last_pushed"]["status"] == "Review" and snap["last_pushed"]["source"] == "git"
    assert snap["synced_fields"] == {"phase": "Implementation", "workflow_status": "In Progress"}
    assert snap["state_hash"] == p["state_hash"] == planner.state_hash(STATE)


def test_zero_ahead_branch_does_not_record_pushed_head():
    git = dict(GIT, ahead=0)
    p = planner.plan(STATE, sidecar(item_id="1"), git, item(), "2026-09-30-x")
    assert p["snapshot"]["pushed_head"] is None


def test_unknown_git_with_git_sourced_last_pushed_keeps_status_and_head():
    last = {"status": "Review", "source": "git", "notes_hash": "x", "code_link": "c"}
    sc = sidecar(item_id="1", last_pushed=last, pushed_head="h0")
    unknown = {"branch": "claude/x", "on_origin": "unknown", "ahead": "unknown", "head": "unknown",
               "merged": "unknown", "merge_subject": "unknown", "origin_url": "unknown"}
    p = planner.plan(STATE, sc, unknown, item(status="Review"), "2026-09-30-x")
    assert S not in p["writes"]
    assert p["snapshot"]["last_pushed"]["status"] == "Review"
    assert p["snapshot"]["last_pushed"]["source"] == "git"
    assert p["snapshot"]["pushed_head"] == "h0"
