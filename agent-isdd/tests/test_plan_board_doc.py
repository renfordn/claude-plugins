"""hooks/plan_board.py -- turn a feature's workflow-state.md into one Plan Board record.

The Plan Board is a single living Artifact page that reads a `plans` collection. Each feature is
one small JSON document, built by this script (never hand-written by the model), so the board
stays accurate whenever the workflow moves.
"""
import json
import os
import re
import subprocess
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import plan_board  # noqa: E402

STATE = """# Workflow State: Sort Queue

## Feature

- Title: Admin/Review Nav Redesign
- Slug: 2026-09-28-admin-nav-queue-redesign
- Goal: Get every video correctly sorted faster -- replace the legacy
  7-page nav with a unified, confidence-ranked Sort Queue.
- Intent Hash: abc123
- Intent Alignment Status: aligned

## Current State

- Current Phase: Implementation
- Track: Standard
- Previous Phase: Design
- Workflow Status: Paused
- Pause Reason: Slices 1-133 shipped; remaining phases deferred by user decision.
- Next Action: Ask the user which deferred phase to slice next
  or close the feature.

## Ownership

- Current Owner: User
- Implementation Requested: Yes

## Last Updated

- Date: 2026-09-29
"""


def _write(tmp_path, text, name="workflow-state.md"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def _swap(text, **fields):
    for key, val in fields.items():
        pretty = key.replace("_", " ").title()
        text = re.sub(rf"(?m)^- {re.escape(pretty)}: .*$", f"- {pretty}: {val}", text, count=1)
    return text


def test_parse_fields_joins_indented_continuation_lines():
    fields = plan_board.parse_fields(STATE)
    assert fields["goal"] == (
        "Get every video correctly sorted faster -- replace the legacy "
        "7-page nav with a unified, confidence-ranked Sort Queue."
    )
    assert fields["next action"] == "Ask the user which deferred phase to slice next or close the feature."


def test_parse_fields_first_occurrence_wins():
    text = "- Title: First\n- Title: Second\n"
    assert plan_board.parse_fields(text)["title"] == "First"


def test_doc_carries_the_feature_summary(tmp_path):
    doc = plan_board.build_doc(_write(tmp_path, STATE), project="file-organiser")
    assert doc["schema"] == 1
    assert doc["title"] == "Admin/Review Nav Redesign"
    assert doc["slug"] == "2026-09-28-admin-nav-queue-redesign"
    assert doc["project"] == "file-organiser"
    assert doc["track"] == "Standard"
    assert doc["phase"] == "Implementation"
    assert doc["status"] == "Paused"
    assert doc["pauseReason"].startswith("Slices 1-133 shipped")
    assert doc["nextAction"] == "Ask the user which deferred phase to slice next or close the feature."
    assert doc["implementationRequested"] is True
    assert doc["updatedAt"] == "2026-09-29"
    assert doc["goal"].startswith("Get every video correctly sorted faster")


def test_paused_phase_is_marked_paused_not_active(tmp_path):
    doc = plan_board.build_doc(_write(tmp_path, STATE), project="p")
    assert [(p["name"], p["state"]) for p in doc["phases"]] == [
        ("Requirements", "done"), ("Design", "done"), ("Tasks", "done"), ("Implementation", "paused"),
    ]


def test_in_progress_design_marks_later_phases_pending(tmp_path):
    text = _swap(STATE, current_phase="Design", workflow_status="In Progress")
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert [p["state"] for p in doc["phases"]] == ["done", "active", "pending", "pending"]


def test_complete_implementation_marks_every_phase_done(tmp_path):
    text = _swap(STATE, workflow_status="Complete")
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert [p["state"] for p in doc["phases"]] == ["done"] * 4


def test_current_phase_complete_marks_every_phase_done(tmp_path):
    text = _swap(STATE, current_phase="Complete", workflow_status="Complete")
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert [p["state"] for p in doc["phases"]] == ["done"] * 4
    assert doc["phase"] == "Complete"


def test_fast_track_skips_the_tasks_phase(tmp_path):
    text = _swap(STATE, track="Fast", current_phase="Implementation", workflow_status="In Progress")
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    states = {p["name"]: p["state"] for p in doc["phases"]}
    assert states["Tasks"] == "skipped"
    assert states["Implementation"] == "active"


def test_unknown_phase_leaves_every_phase_pending(tmp_path):
    text = _swap(STATE, current_phase="Nonsense", workflow_status="In Progress")
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert [p["state"] for p in doc["phases"]] == ["pending"] * 4


def test_long_text_is_cut_with_an_ellipsis(tmp_path):
    long = "word " * 300
    text = _swap(STATE, goal=long, next_action=long)
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert len(doc["goal"]) <= plan_board.GOAL_MAX and doc["goal"].endswith("…")
    assert len(doc["nextAction"]) <= plan_board.NEXT_MAX and doc["nextAction"].endswith("…")


def test_doc_id_uses_only_characters_a_db_path_allows(tmp_path):
    text = _swap(STATE, slug="2026/09 28: weird ünïcode slug!")
    doc = plan_board.build_doc(_write(tmp_path, text), project="My Project/Name")
    assert re.fullmatch(r"[A-Za-z0-9_\-.~:@+]{1,200}", doc["id"]), doc["id"]
    assert "/" not in doc["id"]


def test_doc_id_is_stable_for_the_same_feature(tmp_path):
    a = plan_board.build_doc(_write(tmp_path, STATE), project="file-organiser")
    b = plan_board.build_doc(_write(tmp_path, STATE), project="file-organiser")
    assert a["id"] == b["id"] == "file-organiser--2026-09-28-admin-nav-queue-redesign"


def test_missing_fields_do_not_crash(tmp_path):
    doc = plan_board.build_doc(_write(tmp_path, "- Title: Only a title\n"), project="p")
    assert doc["title"] == "Only a title"
    assert doc["phase"] == "Unknown" and doc["status"] == "Unknown"
    assert doc["goal"] == "" and doc["nextAction"] == "" and doc["pauseReason"] == ""
    assert doc["implementationRequested"] is None


def test_unreadable_file_returns_none(tmp_path):
    assert plan_board.build_doc(str(tmp_path / "nope.md"), project="p") is None


def test_doc_is_small_enough_to_write_by_hand_if_needed(tmp_path):
    long = "word " * 500
    text = _swap(STATE, goal=long, next_action=long, pause_reason=long)
    doc = plan_board.build_doc(_write(tmp_path, text), project="p")
    assert len(json.dumps(doc)) < 4096


def test_cli_doc_prints_the_record_as_json(tmp_path):
    path = _write(tmp_path, STATE)
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "plan_board.py"), "doc", path, "--project", "file-organiser"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["id"] == "file-organiser--2026-09-28-admin-nav-queue-redesign"


def test_cli_doc_on_a_missing_file_fails_clearly(tmp_path):
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "plan_board.py"), "doc", str(tmp_path / "nope.md")],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 1
    assert "nope.md" in result.stderr


def test_cli_doc_out_writes_the_record_to_a_file_and_prints_only_its_id(tmp_path):
    """ArtifactData can send a record from a local file, so the model never pastes JSON by hand."""
    state = _write(tmp_path, STATE)
    out = tmp_path / "record.json"
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "plan_board.py"), "doc", state,
         "--project", "file-organiser", "--out", str(out)],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "file-organiser--2026-09-28-admin-nav-queue-redesign"
    assert json.loads(out.read_text())["title"] == "Admin/Review Nav Redesign"


def test_the_templates_own_pause_statuses_show_the_phase_as_paused(tmp_path):
    """workflow-state.md's template defines In Progress | Blocked | Awaiting Confirmation |
    Awaiting Implementation Request | Complete, so those must read as paused, not active."""
    for status in ("Awaiting Confirmation", "Awaiting Implementation Request", "Blocked", "Paused"):
        text = _swap(STATE, current_phase="Design", workflow_status=status)
        doc = plan_board.build_doc(_write(tmp_path, text), project="p")
        assert [p["state"] for p in doc["phases"]] == ["done", "paused", "pending", "pending"], status
