import os
import sys

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)
import markers  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("<!--SLICE-ID: 3-->\nSlice 4: t", "3"),
    ("Slice 4: title\nmore", "4"),
    ("<!--X-->\n\nSlice 4: title", "4"),
    ("intro\nSlice 4: title", None),
    ("## Slice 12ab: title", "12AB"),
    ("**Plan** Slice 0a: x", "0A"),
    ("**Plan**\nSlice 2F2: x\n**Handoff Facts**\n- Slice 1: y", "2F2"),
    ("**Plan**\nAdd x\n**Handoff Facts**\n- Slice 1: y", None),
    ("**Plan**\n- Slice 1: helper\nSlice 3: mine", "1"),
    ("## Plan\n\nSlice 5: x", "5"),
    ('**Plan**\nAdd "Slice 1: x"\nSlice 2: y', None),
    ("reusing Slice 1's helper", None),
    ("<!--SLICE-ID: 2f2-->", "2F2"),
    ("", None),
    (None, None),
])
def test_parse_slice_id_strict(text, expected):
    assert markers.parse_slice_id_strict(text) == expected


def test_id_widened_and_normalized():
    assert markers.SLICE_TITLE_RE.match("Slice 2F2: x").group(1) == "2F2"
    assert markers.parse_review_scope("<!--REVIEW-SCOPE: slice=2F2-->") == "2F2"
    assert markers.parse_slice_id("see Slice 2F2 here") == "2F2"
    assert markers.normalize_slice_id("12ab") == "12AB"


def test_prose_only_matches_display_parser():
    assert markers.parse_slice_id_strict("see Slice 7 here") is None
    assert markers.parse_slice_id("see Slice 7 here") == "7"


def test_public_marker_re():
    assert markers.SLICE_ID_MARKER_RE.search("<!--SLICE-ID: 2F2-->").group(1) == "2F2"


@pytest.mark.parametrize("name", ["review_gate.py", "tdd_subagent_stop.py"])
def test_hooks_use_public_api(name):
    src = open(os.path.join(HOOKS, name), encoding="utf-8").read()
    assert "_MARKER_RE" not in src
    assert "def _strict_slice_id" not in src
    assert "parse_slice_id_strict" in src


def test_parse_review_scopes_lists_and_repeats():
    assert markers.parse_review_scopes("<!--REVIEW-SCOPE: slice=2, 3,11b-->") == ["2", "3", "11B"]
    assert markers.parse_review_scopes("<!--REVIEW-SCOPE: slice=2-->\n<!-- REVIEW-SCOPE: slice=3 -->") == ["2", "3"]
    assert markers.parse_review_scopes("Slice 3 in prose") == []
    assert markers.parse_review_scope("<!--REVIEW-SCOPE: slice=2,3-->") is None   # single parser unchanged
