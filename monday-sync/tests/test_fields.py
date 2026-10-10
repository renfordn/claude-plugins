"""fields.parse_fields is the one shared workflow-state parser."""
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import fields  # noqa: E402
import planner  # noqa: E402


def test_planner_reexports_fields_parse_fields():
    assert planner.parse_fields is fields.parse_fields


def test_field_names_are_case_insensitive():
    assert fields.parse_fields("- current phase: Design\n- WORKFLOW STATUS: Blocked\n") == {
        "current phase": "Design", "workflow status": "Blocked"}


def test_read_fields_and_feature_title(tmp_path):
    d = tmp_path / "2026-x"
    d.mkdir()
    assert fields.read_fields(str(d)) == {} and fields.feature_title(str(d)) == "2026-x"
    (d / "workflow-state.md").write_text("- Title: T\n- Current Phase: Design\n")
    assert fields.read_fields(str(d))["current phase"] == "Design"
    assert fields.feature_title(str(d)) == "T"


def test_slice_progress_from_tasks_and_impl_progress(tmp_path):
    import json
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "tasks.md").write_text("## Slice 1: a\n\n## Slice 2: b\n")
    assert fields.slice_progress(str(tmp_path)) is None
    (tmp_path / "impl-progress.json").write_text(json.dumps(
        {"slices": {"1": "refactor_complete", "2": "green_pause"}, "allComplete": False}))
    assert fields.slice_progress(str(tmp_path)) == "1/2"
    (tmp_path / "impl-progress.json").write_text(json.dumps({"slices": {}, "allComplete": True}))
    assert fields.slice_progress(str(tmp_path)) == "2/2"
