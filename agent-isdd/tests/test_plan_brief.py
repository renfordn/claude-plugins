"""hooks/plan_brief.py -- script-built per-feature brief from the state files."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import plan_brief  # noqa: E402


def _w(feature, rel, text):
    path = os.path.join(str(feature), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


REQ = """# Requirements

## Status

- Phase: Requirements
- State: Approved
- Last Updated: 2026-10-02

## Open Gaps

- [x] Sync on/off decided
- [ ] Brief Board URL discoverable
- [ ] Window size

## Approval Checkpoint

- [ ] not a gap
"""


def test_goal_comes_from_state_fields(tmp_path):
    assert plan_brief.parse_brief(str(tmp_path), {"goal": "Ship it"})["goal"] == "Ship it"


def test_requirements_state_and_unchecked_gaps(tmp_path):
    _w(tmp_path, "requirements/requirements.md", REQ)
    r = plan_brief.parse_brief(str(tmp_path), {})["requirements"]
    assert r == {"state": "Approved", "openGaps": ["Brief Board URL discoverable", "Window size"]}


def test_missing_or_garbage_requirements_omit_the_section(tmp_path):
    assert "requirements" not in plan_brief.parse_brief(str(tmp_path), {})
    _w(tmp_path, "requirements/requirements.md", "\x00\x01 not markdown ###")
    assert "requirements" not in plan_brief.parse_brief(str(tmp_path), {})


def test_unreadable_file_never_raises(tmp_path):
    os.makedirs(tmp_path / "requirements" / "requirements.md")  # a directory, not a file
    assert plan_brief.parse_brief(str(tmp_path), {}) == {"goal": ""}


DESIGN = """# Design

## Status
- State: Draft

## Design Summary
Schema 2 adds a brief.
Second line of summary.

## Risks / Tradeoffs
- Hook cannot call MCP
- [ ] Wider triggers add reminders

## Open Questions
- [ ] Doc size limit?
- [x] Resolved question
"""


def test_design_state_summary_risks_questions(tmp_path):
    _w(tmp_path, "design/design.md", DESIGN)
    d = plan_brief.parse_brief(str(tmp_path), {})["design"]
    assert d["state"] == "Draft"
    assert d["summary"] == "Schema 2 adds a brief. Second line of summary."
    assert d["risks"] == [{"text": "Hook cannot call MCP"}, {"text": "Wider triggers add reminders"}]
    assert d["openQuestions"] == ["Doc size limit?"]


def test_design_accepts_risks_and_tradeoffs_heading_and_missing_file(tmp_path):
    _w(tmp_path, "design/design.md", "## Status\n- State: Approved\n\n## Risks And Tradeoffs\n- one\n")
    assert plan_brief.parse_brief(str(tmp_path), {})["design"]["risks"] == [{"text": "one"}]
    assert "design" not in plan_brief.parse_brief(str(tmp_path / "nope"), {})


TASKS = """# Tasks

## Slice 1: First behavior

**Kind:** feature
**Risk Tier:** standard

## Slice 2: Second behavior

**Risk Tier:** high-risk

## Slice 3: Third behavior
"""


def test_slices_from_tasks_with_unknown_done(tmp_path):
    _w(tmp_path, "tasks/tasks.md", TASKS)
    s = plan_brief.parse_brief(str(tmp_path), {})["slices"]
    assert s["total"] == 3 and s["done"] is None
    assert s["items"] == [{"n": 1, "title": "First behavior", "tier": "standard"},
                          {"n": 2, "title": "Second behavior", "tier": "high-risk"},
                          {"n": 3, "title": "Third behavior", "tier": ""}]


def test_done_counted_only_with_direct_mode_state(tmp_path):
    _w(tmp_path, "tasks/tasks.md", TASKS)
    _w(tmp_path, "direct-mode-state.json", json.dumps({"slices": [
        {"id": "Slice 1", "status": "done"}, {"id": "Slice 2", "status": "awaiting_review"}]}))
    assert plan_brief.parse_brief(str(tmp_path), {})["slices"]["done"] == 1


def test_closed_feature_counts_every_slice_as_done(tmp_path):
    _w(tmp_path, "tasks/tasks.md", TASKS)
    for fields in ({"workflow status": "Complete"}, {"current phase": "Complete"}):
        s = plan_brief.parse_brief(str(tmp_path), fields)["slices"]
        assert s["total"] == 3 and s["done"] == 3


def test_closed_feature_ignores_a_stale_direct_mode_state(tmp_path):
    _w(tmp_path, "tasks/tasks.md", TASKS)
    _w(tmp_path, "direct-mode-state.json", json.dumps({"slices": [{"id": "Slice 1", "status": "done"}]}))
    assert plan_brief.parse_brief(str(tmp_path), {"workflow status": "Complete"})["slices"]["done"] == 3


def test_open_feature_without_progress_state_stays_unknown(tmp_path):
    _w(tmp_path, "tasks/tasks.md", TASKS)
    s = plan_brief.parse_brief(str(tmp_path), {"workflow status": "In Progress", "current phase": "Implementation"})["slices"]
    assert s["done"] is None


def test_malformed_direct_mode_state_and_no_tasks(tmp_path):
    assert "slices" not in plan_brief.parse_brief(str(tmp_path), {})
    _w(tmp_path, "tasks/tasks.md", TASKS)
    _w(tmp_path, "direct-mode-state.json", "{oops")
    assert plan_brief.parse_brief(str(tmp_path), {})["slices"]["done"] is None


RECAP_H2 = """# Recap

## Open Items

- [ ] Question: Fate of the old board?
- [x] Closed thing

## Decisions Made

- Merge into Plan Board (user).
- Keep Brief Board.

## Technical Debt
- [ ] Exact slice progress marker
"""

RECAP_H3 = """# Recap

## Notes

### Open Questions
- [ ] Is the limit 8 KB?

### Risks
- [ ] Hook is reminder only
- [x] done risk

### Decisions Made
- Use headings.
"""


def test_recap_h2_shape(tmp_path):
    _w(tmp_path, "recap/recap.md", RECAP_H2)
    b = plan_brief.parse_brief(str(tmp_path), {})
    assert b["decisions"] == ["Merge into Plan Board (user).", "Keep Brief Board."]
    assert b["openItems"] == [{"kind": "Open Items", "text": "Question: Fate of the old board?"},
                              {"kind": "Technical Debt", "text": "Exact slice progress marker"}]


def test_recap_h3_shape(tmp_path):
    _w(tmp_path, "recap/recap.md", RECAP_H3)
    b = plan_brief.parse_brief(str(tmp_path), {})
    assert b["decisions"] == ["Use headings."]
    assert b["openItems"] == [{"kind": "Open Questions", "text": "Is the limit 8 KB?"},
                              {"kind": "Risks", "text": "Hook is reminder only"}]


def test_no_recap_omits_both(tmp_path):
    b = plan_brief.parse_brief(str(tmp_path), {})
    assert "decisions" not in b and "openItems" not in b


def _big(tmp_path):
    long = "x" * 1000
    _w(tmp_path, "requirements/requirements.md",
       "## Status\n- State: Approved\n## Open Gaps\n" + "".join(f"- [ ] gap {i} {long}\n" for i in range(50)))
    _w(tmp_path, "design/design.md",
       "## Status\n- State: Approved\n## Design Summary\n" + long + "\n## Risks And Tradeoffs\n"
       + "".join(f"- risk {i} {long}\n" for i in range(50))
       + "## Open Questions\n" + "".join(f"- q {i} {long}\n" for i in range(50)))
    _w(tmp_path, "tasks/tasks.md", "".join(f"## Slice {i}: {long}\n**Risk Tier:** standard\n" for i in range(1, 51)))
    _w(tmp_path, "recap/recap.md",
       "## Decisions Made\n" + "".join(f"- d {i} {long}\n" for i in range(50))
       + "## Open Items\n" + "".join(f"- [ ] o {i} {long}\n" for i in range(50)))
    return plan_brief.parse_brief(str(tmp_path), {"goal": long})


def test_caps_bound_lists_items_and_whole_brief(tmp_path):
    b = _big(tmp_path)
    assert len(json.dumps(b)) <= plan_brief.BRIEF_CAP
    assert plan_brief.BRIEF_CAP <= 6144
    lists = [b["requirements"]["openGaps"], b["design"]["risks"], b["design"]["openQuestions"],
             b["slices"]["items"], b["decisions"], b["openItems"]]
    for lst in lists:
        assert 1 <= len(lst) <= 8
    assert b["slices"]["total"] == 50  # counts are never clipped
    assert b["decisions"][0].endswith("…") and len(b["decisions"][0]) <= 160


def test_every_section_survives_clipping(tmp_path):
    b = _big(tmp_path)
    assert set(b) == {"goal", "requirements", "design", "slices", "decisions", "openItems"}
    assert b["design"]["summary"].endswith("…")


def test_small_brief_is_not_clipped(tmp_path):
    _w(tmp_path, "recap/recap.md", RECAP_H2)
    assert plan_brief.parse_brief(str(tmp_path), {"goal": "g"})["decisions"][0] == "Merge into Plan Board (user)."
