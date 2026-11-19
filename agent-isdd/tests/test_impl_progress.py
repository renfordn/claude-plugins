"""Implementation progress per feature: agent-TDD and code-reviewer reports reach the boards.

agent-TDD's own tdd-progress.json is per project, not per feature, and workflow-state.md is not
touched between slices, so neither board moved during implementation. subagent_report.py now
records each report in <feature>/impl-progress.json; the Plan Board counts slices from it and the
end-of-turn gate treats a new report as a change.
"""
import json
import os
import subprocess
import sys
import time

import hook_test_utils as h

sys.path.insert(0, h.HOOKS_DIR)
import impl_progress  # noqa: E402
import plan_board  # noqa: E402

TASKS = "# Tasks\n\n## Slice 1: first\n\n**Risk Tier:** standard\n\n## Slice 2: second\n\n**Risk Tier:** standard\n"


def tdd(phase, body):
    return f"<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:{phase}-->\n**Plan** — {body}\n"


def test_reports_are_folded_into_per_slice_status(tmp_path):
    d = str(tmp_path)
    assert impl_progress.record(d, tdd("green_pause", "Slice 2: second behaviour"))
    assert impl_progress.summary(d)["done"] == 0
    assert impl_progress.record(d, tdd("refactor_complete", "Slice 2: second behaviour"))
    s = impl_progress.summary(d)
    assert s["done"] == 1 and s["slices"] == {"2": "refactor_complete"}
    assert impl_progress.record(d, "<!--CODE-REVIEWER-REPORT-->\n**Verdict:** clear\n")
    assert impl_progress.load(d)["events"][-1]["kind"] == "review"
    assert impl_progress.record(d, tdd("all_slices_complete", "all done"))
    assert impl_progress.summary(d)["allComplete"] is True
    assert not impl_progress.record(d, "an unrelated subagent's answer")


def _feature(home, repo):
    spec = h.feature_spec_dir(home, repo, "2026-10-09-impl")
    state = h.seed_state_file(spec, title="Impl", slug="2026-10-09-impl",
                              current_phase="Implementation", workflow_status="In Progress")
    h.seed_feature_artifact(spec, "tasks/tasks.md", TASKS)
    h.seed_plan_board_url(os.path.dirname(os.path.dirname(spec)))
    return spec, state


def _subagent_stop(home, repo, report):
    payload = {"cwd": repo, "hook_event_name": "SubagentStop", "last_assistant_message": report}
    r = subprocess.run(["python3", os.path.join(h.HOOKS_DIR, "subagent_report.py")],
                       input=json.dumps(payload), capture_output=True, text=True,
                       env=h._hook_env({"HOME": home}), timeout=10)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["systemMessage"] if r.stdout.strip() else ""


def test_a_slice_report_updates_the_feature_and_asks_for_the_plan_board_sync():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        spec, state = _feature(home, repo)
        msg = _subagent_stop(home, repo, tdd("refactor_complete", "Slice 1: first"))
        assert os.path.isfile(os.path.join(spec, "impl-progress.json"))
        assert "Plan Board" in msg
        doc = plan_board.build_doc(state, project="p")
        assert doc["brief"]["slices"]["done"] == 1 and doc["brief"]["slices"]["total"] == 2


def test_end_of_turn_gate_fires_on_a_new_report_even_when_the_state_file_is_old():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        spec, state = _feature(home, repo)
        old = time.time() - 3 * 86400
        os.utime(state, (old, old))
        _subagent_stop(home, repo, tdd("refactor_complete", "Slice 1: first"))
        r = subprocess.run(["python3", os.path.join(h.HOOKS_DIR, "stop_check.py")],
                           input=json.dumps({"cwd": repo}), capture_output=True, text=True,
                           env=h._hook_env({"HOME": home}), timeout=10)
        assert json.loads(r.stdout).get("decision") == "block"


def test_slice_number_comes_from_the_plan_section_first(tmp_path):
    report = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:refactor_complete-->\n"
              "Follows Slice 1's review.\n\n**Plan**\nSlice 3: the third behaviour\n")
    impl_progress.record(str(tmp_path), report)
    assert impl_progress.summary(str(tmp_path))["slices"] == {"3": "refactor_complete"}


def test_a_report_that_changes_nothing_visible_does_not_change_the_record(tmp_path):
    """The page shows the slice count, not the last event, so tdd/review reports alternating must not
    make the record stale (each stale record costs a board write and blocks the stop)."""
    spec = str(tmp_path / "spec" / "2026-10-09-impl")
    state = h.seed_state_file(spec, title="Impl", slug="2026-10-09-impl",
                              current_phase="Implementation", workflow_status="In Progress")
    h.seed_feature_artifact(spec, "tasks/tasks.md", TASKS)
    assert impl_progress.record(spec, tdd("green_pause", "Slice 1: first"))
    before = plan_board.build_doc(state, project="p")
    assert impl_progress.record(spec, "<!--CODE-REVIEWER-REPORT-->\n**Verdict:** clear\n")
    assert impl_progress.record(spec, tdd("green_pause", "Slice 1: first"))
    after = plan_board.build_doc(state, project="p")
    assert "lastImplEvent" not in after
    assert after["contentHash"] == before["contentHash"]
    assert impl_progress.record(spec, tdd("refactor_complete", "Slice 1: first"))
    assert plan_board.build_doc(state, project="p")["contentHash"] != before["contentHash"]


def test_record_carries_the_last_report_day_only_so_it_changes_once_a_day(tmp_path):
    spec = str(tmp_path / "spec" / "2026-10-09-impl")
    state = h.seed_state_file(spec, title="Impl", slug="2026-10-09-impl",
                              current_phase="Implementation", workflow_status="In Progress")
    assert "lastImplDay" not in plan_board.build_doc(state, project="p")
    assert impl_progress.record(spec, tdd("green_pause", "Slice 1: first"))
    first = plan_board.build_doc(state, project="p")
    assert first["lastImplDay"] == time.strftime("%Y-%m-%d", time.gmtime())
    assert impl_progress.record(spec, "<!--CODE-REVIEWER-REPORT-->\n**Verdict:** clear\n")
    assert plan_board.build_doc(state, project="p")["contentHash"] == first["contentHash"]
    # a report on a later day changes the record (rewrite the stored timestamps to yesterday first)
    data = impl_progress.load(spec)
    for e in data["events"]:
        e["at"] = "2026-10-01T09:00:00Z"
    with open(impl_progress.path(spec), "w") as fh:
        json.dump(data, fh)
    old = plan_board.build_doc(state, project="p")
    assert old["lastImplDay"] == "2026-10-01" and old["contentHash"] != first["contentHash"]


def test_marker_beats_title_alnum_and_case_normalised(tmp_path):
    d = str(tmp_path)
    assert impl_progress.record(d, tdd("green_pause", "Slice 2F2: x\n<!--SLICE-ID: 3-->"))
    assert impl_progress.record(d, tdd("green_pause", "Slice 2f2: alnum"))
    assert impl_progress.record(d, tdd("green_pause", "Slice 9: y\n<!--SLICE-ID: 2F2-->"))
    assert impl_progress.summary(d)["slices"] == {"3": "green_pause", "2F2": "green_pause"}


def test_review_reports_never_write_a_reviewed_map_and_leave_workflow_state_alone(tmp_path):
    d = str(tmp_path)
    scoped = "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=4-->\n**Plan**\nReuses Slice 1 helper\n"
    assert impl_progress.record(d, scoped)
    assert impl_progress.record(d, "<!--CODE-REVIEWER-REPORT-->\nReviewed Slice 5 prose only\n")
    for _ in range(impl_progress.MAX_EVENTS + 5):
        impl_progress.record(d, tdd("green_pause", "Slice 1: churn"))
    assert "reviewed" not in impl_progress.load(d)  # review_tracking is the sole reviewed writer
    assert not os.path.exists(os.path.join(d, "workflow-state.json"))


def test_same_line_plan_heading_forms_key_tdd_reports_but_not_reviews(tmp_path):
    for i, sep in enumerate(["\u2014", "\u2013", "-", ":"]):
        d = str(tmp_path / str(i))
        os.makedirs(d)
        impl_progress.record(d, "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                                "**Plan** %s Slice 2: x\nReuses Slice 1.\n" % sep)
        assert impl_progress.summary(d)["slices"] == {"2": "green_pause"}, sep
    d = str(tmp_path / "r")
    os.makedirs(d)
    impl_progress.record(d, "<!--CODE-REVIEWER-REPORT-->\n**Plan** \u2014 Slice 2: x\n")
    assert not impl_progress.load(d).get("reviewed")


def test_progress_writes_go_through_the_locked_update_json(tmp_path):
    from unittest import mock
    import sdd_state
    d = str(tmp_path)
    with mock.patch.object(sdd_state, "locked_rewrite_text", wraps=sdd_state.locked_rewrite_text) as m:
        assert impl_progress.record(d, tdd("green_pause", "Slice 1: x"))
    assert m.called
    assert impl_progress.summary(d)["slices"] == {"1": "green_pause"}


def test_record_folds_into_the_file_as_read_under_the_lock(tmp_path):
    """A write landing between record()'s start and its locked rewrite must survive."""
    from unittest import mock
    import sdd_state
    d = str(tmp_path)
    assert impl_progress.record(d, tdd("green_pause", "Slice 1: x"))
    real = sdd_state.locked_rewrite_text

    def racing(path, fn, **kw):
        real(path, lambda _t: json.dumps({"slices": {"1": "green_pause", "9": "refactor_complete"},
                                          "allComplete": False, "events": []}))
        return real(path, fn, **kw)

    with mock.patch.object(sdd_state, "locked_rewrite_text", side_effect=racing):
        assert impl_progress.record(d, tdd("green_pause", "Slice 2: y"))
    assert impl_progress.summary(d)["slices"] == {"1": "green_pause", "9": "refactor_complete",
                                                  "2": "green_pause"}
