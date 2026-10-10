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
