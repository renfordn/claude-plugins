"""planner.plan board->isdd rules: Stuck (F1 both directions), conflicts, isdd_updates only if differ."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

S = planner.STATUS_COL


def state(status="In Progress", phase="Implementation", reason="None"):
    return (f"- Current Phase: {phase}\n- Workflow Status: {status}\n- Pause Reason: {reason}\n"
            "- Next Action: build\n- Hook Notes: ok\n")


def sidecar(last_status, source="phase"):
    sc = store.default_sidecar()
    sc.update(item_id="1", branch=None,
              last_pushed=None if last_status is None else {"status": last_status, "source": source})
    return sc


def item(status, updates=()):
    return {"id": "1", "status": status, "notes": "", "code_link": "", "updated_at": "t1",
            "updates": list(updates)}


def test_user_set_stuck_blocks_isdd_with_latest_note_and_no_status_push():
    it = item("Stuck", [{"id": "u1", "body": "old", "created_at": "2026-09-29"},
                        {"id": "u2", "body": "<p>waiting on API key</p>", "created_at": "2026-09-30"}])
    p = planner.plan(state(), sidecar("In progress"), None, it, "s")
    assert p["isdd_updates"] == {"Workflow Status": "Blocked", "Pause Reason": "blocker",
                                 "Hook Notes": "waiting on API key"}
    assert S not in p["writes"] and planner.NOTES_COL not in p["writes"]
    assert p["snapshot"]["last_pushed"]["status"] == "Stuck"


def test_user_set_stuck_when_isdd_already_blocked_makes_no_isdd_updates():
    p = planner.plan(state("Blocked", reason="blocker"), sidecar("In progress"), None, item("Stuck"), "s")
    assert p["isdd_updates"] == {} and S not in p["writes"]


def test_stuck_we_pushed_is_unblocked_when_isdd_resumes():
    p = planner.plan(state(), sidecar("Stuck"), None, item("Stuck"), "s")
    assert p["writes"][S] == "In progress" and p["isdd_updates"] == {}


def test_user_changed_status_that_disagrees_is_a_conflict_not_a_write():
    p = planner.plan(state(phase="Design"), sidecar("To do"), None, item("Done"), "s")
    assert S not in p["writes"]
    assert p["conflicts"] == [{"kind": "status", "board": "Done", "desired": "Gather Requirements",
                               "last_pushed": "To do"}]
    assert p["snapshot"]["last_pushed"]["status"] == "To do"


def test_freshly_linked_ticket_pushes_over_todo_but_conflicts_otherwise():
    assert planner.plan(state(), sidecar(None), None, item("To do"), "s")["writes"][S] == "In progress"
    p = planner.plan(state(), sidecar(None), None, item("Review"), "s")
    assert S not in p["writes"] and p["conflicts"][0]["kind"] == "status"


def test_branch_gone_unmerged_is_surfaced_as_a_question():
    sc = sidecar("Review", source="git")
    sc.update(branch="claude/x", pushed_head="h1")
    git = {"on_origin": False, "ahead": 0, "merged": False, "merge_subject": "", "origin_url": ""}
    p = planner.plan(state(), sc, git, item("Review"), "s")
    assert [c["kind"] for c in p["conflicts"]] == ["branch_gone"]


def test_no_status_conflict_when_desired_status_is_unknown():
    p = planner.plan(state(phase=""), sidecar(None), None, item("Review"), "s")
    assert p["conflicts"] == [] and S not in p["writes"]


def test_linked_todo_ticket_moves_to_the_new_pre_impl_labels_without_a_conflict():
    p = planner.plan(state(phase="Design"), sidecar("To do"), None, item("To do"), "s")
    assert p["writes"][S] == "Gather Requirements" and p["conflicts"] == []
    p = planner.plan(state("Awaiting Implementation Request", phase="Design"), sidecar("To do"), None,
                     item("To do"), "s")
    assert p["writes"][S] == "Implementation Ready" and p["conflicts"] == []
    assert p["snapshot"]["last_pushed"]["status"] == "Implementation Ready"
