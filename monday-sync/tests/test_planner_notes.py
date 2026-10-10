"""Notes ownership: hook-owned only while the user hasn't edited it; never written while user-Stuck."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

S, N = planner.STATUS_COL, planner.NOTES_COL


def state(next_action="build", status="In Progress", reason="None", hook_notes="ok"):
    return (f"- Slug: s\n- Current Phase: Implementation\n- Workflow Status: {status}\n"
            f"- Pause Reason: {reason}\n- Next Action: {next_action}\n- Hook Notes: {hook_notes}\n")


def apply(it, writes):
    it = dict(it)
    if S in writes:
        it["status"] = writes[S]
    if N in writes:
        it["notes"] = writes[N]
    return it


def synced(next_action="build"):
    sc = store.default_sidecar()
    sc["item_id"] = "1"
    it = {"id": "1", "status": "To do", "notes": "", "code_link": "", "updates": []}
    p = planner.plan(state(next_action), sc, None, it, "s")
    sc.update(p["snapshot"])
    return sc, apply(it, p["writes"])


def run(text, sc, it):
    p = planner.plan(text, sc, None, it, "s")
    if p["snapshot"]:
        sc.update(p["snapshot"])
    return p, apply(it, p["writes"])


def test_owned_notes_follow_the_workflow():
    sc, it = synced()
    p, it = run(state("ship it"), sc, it)
    assert p["writes"][N] == "Phase: Implementation · Next: ship it · Spec: s"


def test_user_edited_notes_are_never_overwritten_and_reported_once():
    sc, it = synced()
    it["notes"] = "my own words"
    p1, it = run(state("ship it"), sc, it)
    assert N not in p1["writes"] and p1["conflicts"] == []
    assert {"kind": "notes", "text": "my own words"} in p1["changes"]
    p2, it = run(state("ship it later"), sc, it)
    assert N not in p2["writes"] and p2["changes"] == []


def test_user_stuck_with_changed_notes_settles_in_three_runs():
    sc, it = synced()
    it["status"] = "Stuck"
    text = state("ship it")                      # desired notes changed too
    p1, it = run(text, sc, it)
    assert p1["writes"] == {} and p1["isdd_updates"]["Workflow Status"] == "Blocked"
    text = state("ship it", status="Blocked", reason="blocker",
                 hook_notes=p1["isdd_updates"]["Hook Notes"])
    p2, it = run(text, sc, it)
    assert p2["writes"] == {} and p2["isdd_updates"] == {} and p2["changes"] == []
    p3, it = run(text, sc, it)
    assert p3["writes"] == {} and p3["isdd_updates"] == {} and p3["changes"] == []
