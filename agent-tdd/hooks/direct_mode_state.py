#!/usr/bin/env python3
"""State utilities for design-spec-direct's caller-owned loop.

Owns direct-mode-state.json read/write/per-slice status tracking, per
skills/design-spec-direct/SKILL.md's "Caller-owned loop" section. Lives alongside
tdd_state.py and shares its memory directory (same project, same plugin) rather than
introducing a second state root.
"""
import copy
import json
import os
import sys

_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from tdd_state import tdd_memory_dir

VALID_STATUSES = ("pending", "red_green_done", "awaiting_review", "blocked", "done")

_DEFAULT_SHAPE = {"mode": "direct", "tasks_file": None, "current_slice": None, "slices": []}


def direct_mode_memory_dir(cwd):
    return tdd_memory_dir(cwd)


def read_direct_mode_state(cwd):
    """Read direct-mode-state.json. Returns the default shape on missing/malformed/
    wrong-schema content."""
    path = os.path.join(direct_mode_memory_dir(cwd), "direct-mode-state.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("slices"), list):
            return copy.deepcopy(_DEFAULT_SHAPE)
        return data
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(_DEFAULT_SHAPE)


def write_direct_mode_state(cwd, data):
    """Write direct-mode-state.json, creating parent dirs as needed."""
    d = direct_mode_memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "direct-mode-state.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def set_slice_status(cwd, slice_id, status, risk_tier=None):
    """Update one slice's status, appending it if not already present, and advance
    current_slice to slice_id. Raises ValueError for a status outside VALID_STATUSES."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Unknown status {status!r}; must be one of {VALID_STATUSES}"
        )

    state = read_direct_mode_state(cwd)
    for slice_entry in state["slices"]:
        if slice_entry["id"] == slice_id:
            slice_entry["status"] = status
            if risk_tier is not None:
                slice_entry["risk_tier"] = risk_tier
            break
    else:
        state["slices"].append(
            {"id": slice_id, "status": status, "risk_tier": risk_tier}
        )

    state["current_slice"] = slice_id
    write_direct_mode_state(cwd, state)
    return state


def all_slices_done(cwd):
    """True only when at least one slice exists and every recorded slice is 'done'.
    Gate for calling design-spec-direct's `summary` mode."""
    slices = read_direct_mode_state(cwd)["slices"]
    return bool(slices) and all(s["status"] == "done" for s in slices)


def first_incomplete_slice_id(cwd, ordered_ids):
    """Given tasks.md's slice order, return the first id not recorded as 'done' —
    a slice absent from direct-mode-state.json entirely (never started) counts as
    incomplete. Returns None once every named id is done."""
    statuses = {s["id"]: s["status"] for s in read_direct_mode_state(cwd)["slices"]}
    for slice_id in ordered_ids:
        if statuses.get(slice_id) != "done":
            return slice_id
    return None
