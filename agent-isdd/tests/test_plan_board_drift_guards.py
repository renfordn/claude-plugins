"""Drift guards: bare `Field:` state lines parse, and verify flags Unknown and stale open cards."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import plan_board  # noqa: E402
import plan_board_sync  # noqa: E402
import sdd_state  # noqa: E402

BARE = "# Workflow State\nFeature: X\nCurrent Phase: Implementation\nWorkflow Status: Complete\nNext Action: None\nNote: not a field\n"


def test_bare_known_fields_parse_in_both_parsers(tmp_path):
    f = plan_board.parse_fields(BARE)
    assert f["current phase"] == "Implementation" and f["workflow status"] == "Complete"
    assert "note" not in f
    p = tmp_path / "workflow-state.md"
    p.write_text(BARE)
    assert sdd_state.parse_state(str(p))["workflow status"] == "Complete"
    assert sdd_state.is_complete_state(str(p))


def test_bullet_field_still_wins_over_later_bare_line():
    f = plan_board.parse_fields("- Workflow Status: In Progress\nWorkflow Status: Complete\n")
    assert f["workflow status"] == "In Progress"


def test_attention_flags_unknown_and_stale_open_cards():
    docs = {
        "p--unknown": {"status": "Unknown", "phase": "Unknown", "updatedAt": "2026-11-01"},
        "p--stale": {"status": "In Progress", "phase": "Implementation", "updatedAt": "2026-10-01",
                     "lastImplDay": "2026-10-05"},
        "p--fresh": {"status": "In Progress", "phase": "Implementation", "updatedAt": "2026-10-01",
                     "lastImplDay": "2026-10-30"},
        "p--done": {"status": "Complete", "phase": "Implementation", "updatedAt": "2026-09-01"},
    }
    out = plan_board_sync.attention(docs, today="2026-11-02", stale_days=14)
    assert out == {"unknown": ["p--unknown"], "stale": ["p--stale"]}
