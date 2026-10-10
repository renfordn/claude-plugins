"""Persisted conflict answers (F1) and unlinked opt-out (F2) in the planner."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402
import store  # noqa: E402

S = planner.STATUS_COL


def state(phase="Implementation", status="In Progress"):
    return f"- Slug: s\n- Current Phase: {phase}\n- Workflow Status: {status}\n- Next Action: n\n"


def accepted(label, phase="Implementation", status="In Progress", **kw):
    sc = store.default_sidecar()
    sc.update(item_id="1", branch="claude/x",
              last_pushed={"status": label, "source": "user", "notes_hash": None, "code_link": None},
              accepted_fields={"phase": phase, "workflow_status": status}, **kw)
    return sc


def item(status):
    return {"id": "1", "status": status, "notes": "", "code_link": "", "updates": []}


def test_accepted_board_status_is_authoritative_while_isdd_unchanged():
    p = planner.plan(state(), accepted("Review"), None, item("Review"), "s")
    assert p["conflicts"] == [] and S not in p["writes"]
    assert p["snapshot"]["last_pushed"]["source"] == "user"
    assert p["desired"]["status"] == "Review"


def test_accepted_status_yields_once_isdd_phase_or_status_changes():
    p = planner.plan(state(status="Complete"), accepted("Review"), None, item("Review"), "s")
    assert p["writes"][S] == "In progress" and p["conflicts"] == []


def test_confirmed_done_keeps_done_and_suppresses_branch_gone():
    sc = accepted("Done", confirmed_done=True, pushed_head="h1")
    git = {"on_origin": False, "ahead": 0, "merged": False, "merge_subject": "", "origin_url": ""}
    p = planner.plan(state(status="Complete"), sc, git, item("Done"), "s")
    assert p["desired"]["status"] == "Done" and S not in p["writes"] and p["conflicts"] == []


def test_confirmed_done_does_not_survive_a_rewind():
    sc = accepted("Done", confirmed_done=True)
    p = planner.plan(state(phase="Design"), sc, None, item("Done"), "s")
    assert p["writes"][S] == "Gather Requirements"


def test_unlinked_sidecar_is_a_no_op_that_never_creates():
    sc = store.default_sidecar()
    sc["unlinked"] = True
    p = planner.plan(state(), sc, None, None, "s")
    assert p["skipped"] == "unlinked" and p["create"] is False and p["writes"] == {}
    assert p["snapshot"] is None and p["recreate"] is None


GIT_H1 = {"branch": "claude/x", "on_origin": True, "ahead": 1, "head": "h1", "merged": False,
          "merge_subject": "", "origin_url": ""}


def pinned(label, git):
    sc = accepted(label)
    sc["accepted_fields"] = dict(sc["accepted_fields"], git=planner.git_pin(git))
    return sc


def test_merge_derived_done_beats_an_accepted_status():
    merged = dict(GIT_H1, ahead=0, merged=True, merge_subject="Merge pull request #3 from o/claude/x")
    p = planner.plan(state(), pinned("Review", GIT_H1), merged, item("Review"), "s")
    assert p["desired"]["status"] == "Done" and p["writes"][S] == "Done"


def test_accept_lapses_when_git_moves_to_a_new_pushed_head():
    sc = pinned("In progress", GIT_H1)
    same = planner.plan(state(), sc, GIT_H1, item("In progress"), "s")
    assert S not in same["writes"] and same["conflicts"] == []
    moved = planner.plan(state(), sc, dict(GIT_H1, head="h2"), item("In progress"), "s")
    assert moved["writes"][S] == "Review"


def test_unknown_git_does_not_lapse_a_pinned_accept():
    unknown = {"on_origin": "unknown", "ahead": "unknown", "merged": "unknown", "head": "unknown"}
    p = planner.plan(state(), pinned("In progress", GIT_H1), unknown, item("In progress"), "s")
    assert S not in p["writes"] and p["conflicts"] == []
