"""hooks/plan_board_sync.py -- verify: diff the board's records against local state."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import plan_board_sync  # noqa: E402

EMPTY = {"missing": [], "mismatched": [], "orphaned": []}


def test_empty_and_identical_maps_are_clean():
    assert plan_board_sync.diff_records({}, {}) == EMPTY
    assert plan_board_sync.diff_records({"p--a": "h1"}, {"p--a": "h1"}) == EMPTY


def test_each_category_alone():
    assert plan_board_sync.diff_records({"p--a": "h"}, {})["missing"] == ["p--a"]
    assert plan_board_sync.diff_records({"p--a": "h1"}, {"p--a": "h2"})["mismatched"] == ["p--a"]
    assert plan_board_sync.diff_records({}, {"p--z": "h"})["orphaned"] == ["p--z"]


def test_combined_and_sorted():
    local = {"p--c": "1", "p--a": "1", "p--b": "1"}
    board = {"p--b": "2", "p--z": "1", "p--y": "1", "p--c": "1"}
    assert plan_board_sync.diff_records(local, board) == {
        "missing": ["p--a"], "mismatched": ["p--b"], "orphaned": ["p--y", "p--z"]}
