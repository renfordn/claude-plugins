"""planner.normalize_item + candidates: Backlog To do items with no linked feature."""
import json
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402


def raw(id_, name, status, group="Backlog"):
    return {"id": id_, "name": name, "group": {"id": "topics", "title": group},
            "updated_at": "t",
            "column_values": [{"id": planner.STATUS_COL, "text": status},
                              {"id": planner.NOTES_COL, "text": "n"},
                              {"id": planner.LINK_COL, "text": ""}],
            "updates": [{"id": "u1", "text_body": "hi", "created_at": "c"}]}


def test_normalize_item_maps_raw_monday_columns():
    it = planner.normalize_item(raw(5, "[p] X", "Review"))
    assert it == {"id": "5", "name": "[p] X", "group": "Backlog", "status": "Review", "notes": "n",
                  "code_link": "", "updated_at": "t", "created_at": None, "project": None,
                  "updates": [{"id": "u1", "body": "hi", "created_at": "c"}]}
    assert planner.normalize_item({"id": "7", "status": "Done"})["status"] == "Done"


def test_candidates_are_unlinked_undismissed_backlog_todo_items():
    items = [raw("1", "[p] linked", "To do"), raw("2", "[p] free", "To do"),
             raw("3", "[p] doing", "In progress"), raw("4", "[p] elsewhere", "To do", group="Done"),
             raw("5", "[p] dismissed", "To do")]
    assert planner.candidates(items, linked_ids=["1"], dismissed=["5"]) == [{"id": "2", "name": "[p] free"}]


LIVE = json.loads("""{"id":"3251090620","name":"[file-organiser] \u2026","created_at":"2026-09-30T10:00:00Z","updated_at":"2026-09-30T11:00:00Z","column_values":{"text_mm7nz61n":null,"color_mm7na652":"To do","long_text_mm7nzhmb":"\u2026","dropdown_mm7na5br":"file-organiser","color_mm7n3b93":"Chore"},"group":{"id":"topics","title":"Backlog"}}""")


def test_normalize_item_accepts_live_dict_column_values_and_attached_updates():
    it = planner.normalize_item(dict(LIVE, updates=[{"id": 9, "body": "b", "created_at": "c"}]))
    assert it["id"] == "3251090620" and it["group"] == "Backlog"
    assert it["status"] == "To do" and it["notes"] == "\u2026" and it["code_link"] is None
    assert it["updates"] == [{"id": "9", "body": "b", "created_at": "c"}]
    assert it["created_at"] == "2026-09-30T10:00:00Z" and it["project"] == "file-organiser"
    assert planner.candidates([LIVE], linked_ids=[]) == [{"id": "3251090620", "name": "[file-organiser] \u2026"}]


def test_normalize_item_keeps_project_and_created_at_from_normalized_dicts():
    it = planner.normalize_item({"id": "7", "project": "p", "created_at": "2026-01-01T00:00:00Z"})
    assert (it["project"], it["created_at"]) == ("p", "2026-01-01T00:00:00Z")
