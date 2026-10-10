"""planner.parse_fields + desired_status: design.md Status mapping table."""
import os
import sys

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402

STATE = """# Workflow State: X

## Feature

- Title: monday.com board sync
- Goal: Keep the board in step
  with isdd phases.

## Current State

- Current Phase: Implementation
- Workflow Status: In Progress
- Next Action: build it
- Current Phase: Design
"""

UNPUSHED = {"on_origin": False, "ahead": 0, "merged": False}
REVIEW = {"on_origin": True, "ahead": 2, "merged": False}
MERGED = {"on_origin": True, "ahead": 0, "merged": True, "merge_subject": "Merge pull request #1 from o/x"}
UNKNOWN = {"on_origin": "unknown", "ahead": "unknown", "merged": "unknown"}
GIT_PUSHED = {"last_pushed": {"status": "Review", "source": "git"}}


def f(phase, status="In Progress"):
    return {"current phase": phase, "workflow status": status}


def test_parse_fields_first_wins_and_joins_continuations():
    fields = planner.parse_fields(STATE)
    assert fields["current phase"] == "Implementation"
    assert fields["goal"] == "Keep the board in step with isdd phases."
    assert fields["title"] == "monday.com board sync"


@pytest.mark.parametrize("fields,git,sidecar,expected", [
    (f("Implementation", "Blocked"), MERGED, None, ("Stuck", "phase", True)),
    (f("Requirements"), None, None, ("Gather Requirements", "phase", True)),
    (f("Design"), None, None, ("Gather Requirements", "phase", True)),
    (f("Design"), MERGED, GIT_PUSHED, ("Gather Requirements", "phase", True)),  # rewind ignores git (F5)
    (f("Tasks"), REVIEW, None, ("Implementation Ready", "phase", True)),
    (f("Design", "Awaiting Implementation Request"), None, None,
     ("Implementation Ready", "phase", True)),                         # planning done
    (f("Requirements", "Awaiting Implementation Request"), None, None,
     ("Implementation Ready", "phase", True)),
    (f("Tasks", "Blocked"), None, None, ("Stuck", "phase", True)),
    (f("Implementation"), MERGED, None, ("Done", "git", True)),
    (f("Complete", "Complete"), MERGED, None, ("Done", "git", True)),
    (f("Implementation", "Complete"), REVIEW, None, ("Review", "git", True)),
    (f("Implementation"), {"on_origin": True, "ahead": 0, "merged": False}, None,
     ("In progress", "phase", True)),                                  # 0 ahead is not Review
    (f("Implementation"), UNKNOWN, GIT_PUSHED, ("Review", "git", False)),  # F4 keep, no write
    (f("Implementation"), None, GIT_PUSHED, ("Review", "git", False)),
    (f("Implementation"), UNKNOWN, {"last_pushed": {"status": "To do", "source": "phase"}},
     ("In progress", "phase", True)),
    (f("Implementation"), UNPUSHED, None, ("In progress", "phase", True)),
    (f("Implementation", "Complete"), None, None, ("In progress", "phase", True)),
    (f(""), REVIEW, GIT_PUSHED, ("Review", "phase", False)),           # F1 unknown phase keeps
    (f("Weird"), None, None, (None, "phase", False)),
    (f("Implementation"), {"on_origin": True, "ahead": 0, "merged": True, "merge_subject": ""},
     None, ("In progress", "phase", True)),                            # F3 merged needs evidence
    (f("Implementation"), {"on_origin": False, "ahead": 0, "merged": True, "merge_subject": ""},
     {"pushed_head": "abc"}, ("Done", "git", True)),
])
def test_desired_status_mapping_table(fields, git, sidecar, expected):
    d = planner.desired_status(fields, git, sidecar)
    assert (d["status"], d["source"], d["write"]) == expected


def test_branch_gone_unmerged_stays_review_with_flag():
    d = planner.desired_status(f("Implementation"), UNPUSHED, {"pushed_head": "abc"})
    assert (d["status"], d["source"], d["flag"]) == ("Review", "git", "branch_gone")
