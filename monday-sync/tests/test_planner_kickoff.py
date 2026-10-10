"""planner.kickoff_candidates: which Gather Requirements ticket a scheduled kickoff poll starts."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402

NOW = "2026-10-01T12:00:00Z"
MAP = {"file-organiser": "~/Codebase/AI/file-organiser"}
GR = "Gather Requirements"


def item(id_, status=GR, project="file-organiser", created="2026-09-30T10:00:00Z", notes="",
         link=None, updates=(), updated="2026-09-30T11:00:00Z"):
    return {"id": id_, "name": f"[{project}] T{id_}", "created_at": created, "updated_at": updated,
            "column_values": {planner.STATUS_COL: status, planner.NOTES_COL: notes,
                              planner.LINK_COL: link, planner.PROJECT_COL: project},
            "group": {"id": "topics", "title": "Backlog"}, "updates": list(updates)}


def pick_id(out):
    return (out["pick"] or {}).get("id")


def test_picks_oldest_eligible_ticket_with_attempt_1():
    out = planner.kickoff_candidates(
        [item("2", created="2026-09-30T10:00:00Z"), item("1", created="2026-09-29T10:00:00Z")],
        NOW, MAP)
    assert out == {"pick": {"id": "1", "name": "[file-organiser] T1", "project": "file-organiser",
                            "repo_path": "~/Codebase/AI/file-organiser", "attempt": 1},
                   "needs_project": [], "stuck": []}


def test_only_unlinked_gather_requirements_tickets_are_eligible():
    items = [item("1", status="To do"), item("2", notes="Phase: Design · Next: x · Spec: s"),
             item("3", link="https://github.com/o/r/tree/b")]
    assert planner.kickoff_candidates(items, NOW, MAP) == {"pick": None, "needs_project": [], "stuck": []}


def test_oldest_falls_back_to_updated_at_then_id():
    items = [item("9", created=None, updated="2026-09-29T00:00:00Z"),
             item("8", created=None, updated="2026-09-30T00:00:00Z")]
    assert pick_id(planner.kickoff_candidates(items, NOW, MAP)) == "9"
    items = [item("12", created=None, updated=None), item("11", created=None, updated=None)]
    assert pick_id(planner.kickoff_candidates(items, NOW, MAP)) == "11"


def upd(id_, body, at="2026-10-01T11:00:00Z"):
    return {"id": id_, "body": body, "created_at": at}


NEEDS = "🤖 isdd kickoff needs-project: set the Project label"


def test_missing_or_unmapped_project_is_reported_once_and_never_picked():
    items = [item("1", project=None), item("2", project="elsewhere"), item("3", project="")]
    assert planner.kickoff_candidates(items, NOW, MAP) == {
        "pick": None, "needs_project": ["1", "2", "3"], "stuck": []}


def test_needs_project_marker_skips_silently_until_the_project_is_mapped():
    marked = [upd("u1", f"<p>{NEEDS}</p>")]
    out = planner.kickoff_candidates([item("1", project="elsewhere", updates=marked)], NOW, MAP)
    assert out == {"pick": None, "needs_project": [], "stuck": []}
    out = planner.kickoff_candidates([item("1", updates=marked)], NOW, MAP)
    assert pick_id(out) == "1" and out["pick"]["attempt"] == 1


def test_marker_must_start_the_update_body():
    quoted = [upd("u1", f"fyi: {NEEDS}")]
    out = planner.kickoff_candidates([item("1", project=None, updates=quoted)], NOW, MAP)
    assert out["needs_project"] == ["1"]


STARTED = "🤖 isdd kickoff started (attempt 1)"


def run(*updates, now=NOW):
    return planner.kickoff_candidates([item("1", updates=updates)], now, MAP)


def test_done_marker_is_never_picked_again():
    assert run(upd("u1", STARTED, "2026-09-30T09:00:00Z"),
               upd("u2", "🤖 isdd kickoff done: spec/2026-09-30-x")) == {
        "pick": None, "needs_project": [], "stuck": []}


def test_started_within_3h_is_in_flight_and_skipped_including_the_boundary():
    assert run(upd("u1", STARTED, "2026-10-01T11:00:00Z"))["pick"] is None
    assert run(upd("u1", STARTED, "2026-10-01T09:00:00Z"))["pick"] is None     # exactly 3h


def test_one_stale_started_marker_retries_as_attempt_2():
    out = run(upd("u1", f"<p>{STARTED}</p>", "2026-10-01T08:59:59Z"))
    assert out["pick"]["attempt"] == 2 and out["stuck"] == []


def test_second_stale_start_is_stuck_but_a_fresh_second_attempt_is_in_flight():
    first = upd("u1", STARTED, "2026-10-01T05:00:00Z")
    assert run(first, upd("u2", STARTED, "2026-10-01T08:00:00Z")) == {
        "pick": None, "needs_project": [], "stuck": ["1"]}
    assert run(first, upd("u2", STARTED, "2026-10-01T11:30:00Z")) == {
        "pick": None, "needs_project": [], "stuck": []}


def test_missing_or_unparsable_marker_time_counts_as_stale():
    assert run(upd("u1", STARTED, None))["pick"]["attempt"] == 2
    assert run(upd("u1", STARTED, "garbage"))["pick"]["attempt"] == 2


def test_user_retry_update_resets_earlier_markers():
    dead = [upd("u1", STARTED, "2026-10-01T01:00:00Z"), upd("u2", STARTED, "2026-10-01T05:00:00Z")]
    assert run(*dead)["stuck"] == ["1"]
    retry = upd("u3", "<p>ISDD Kickoff Retry - fixed the notes</p>", "2026-10-01T06:00:00Z")
    out = run(*dead, retry)
    assert out["pick"]["attempt"] == 1 and out["stuck"] == []
    done = upd("u0", "🤖 isdd kickoff done: spec/x", "2026-09-30T00:00:00Z")
    assert run(done, retry)["pick"]["attempt"] == 1
    assert run(*dead, retry, upd("u4", STARTED, "2026-10-01T11:00:00Z"))["pick"] is None


def test_retry_text_must_start_the_update():
    dead = [upd("u1", STARTED, "2026-10-01T01:00:00Z"), upd("u2", STARTED, "2026-10-01T05:00:00Z")]
    assert run(*dead, upd("u3", "please isdd kickoff retry", "2026-10-01T06:00:00Z"))["stuck"] == ["1"]


def test_oldest_compares_real_times_across_utc_offsets():
    items = [item("1", created="2026-09-30T09:00:00Z"), item("2", created="2026-09-30T10:00:00+02:00")]
    assert pick_id(planner.kickoff_candidates(items, NOW, MAP)) == "2"      # 08:00Z is older


def test_spec_index_excludes_tickets_already_linked_by_item_id_or_name():
    items = [item("1"), item("2"), item("3", project=None), item("4")]
    items[1]["name"] = "[file-organiser]   t2 "                 # name match is whitespace/case-insensitive
    items[2]["name"] = "[file-organiser] T3"
    index = [{"title": "T2", "item_id": None, "dir": "~/r/spec/2026-09-01-t2"},
             {"title": "T3", "item_id": None, "dir": "~/r/spec/2026-09-01-t3"},
             {"title": "Other", "item_id": 1, "dir": "~/r/spec/2026-09-01-other"}]
    out = planner.kickoff_candidates(items, NOW, MAP, spec_index=index)
    assert out == {"pick": dict(out["pick"], id="4"), "needs_project": [], "stuck": []}
    assert pick_id(planner.kickoff_candidates(items, NOW, MAP)) == "1"           # no index: old rule


def test_ticket_name_key_normalizes_whitespace_and_case():
    assert planner.ticket_name_key(" [P]  My   Title ") == planner.ticket_name_key("[p] my title")
