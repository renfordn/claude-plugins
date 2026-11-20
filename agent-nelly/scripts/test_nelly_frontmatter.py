"""Tests for scripts/nelly_frontmatter.py -- the one frontmatter line-editing module (slice 2D)."""
import pytest

import nelly_frontmatter as fm


def lines(text):
    return text.splitlines(keepends=True)


def test_key_extent_block_list_looks_past_blank_and_comment_lines():
    ls = lines("metadata:\n  stale_paths:\n    - a\n\n    # note\n    - b\n  next: 1\n")
    assert fm.key_extent(ls, "stale_paths") == (1, 6, "  ")


def test_key_extent_excludes_trailing_blank_lines_and_zero_indent_items():
    ls = lines("  k:\n  - a\n  - b\n\n  other: 1\n")
    assert fm.key_extent(ls, "k")[:2] == (0, 3)
    flow = lines("  k: [a]\n  - not mine\n")
    assert fm.key_extent(flow, "k")[:2] == (0, 1)


def test_key_extent_flow_value_takes_deeper_lines_only():
    ls = lines("  k: v\n    cont\n  other: 1\n")
    assert fm.key_extent(ls, "k")[:2] == (0, 2)


@pytest.mark.parametrize("value,expected", [
    ("src/a.py", "src/a.py"), ("a b", '"a b"'), ('q"x', '"q\\"x"'), ("b\\s", '"b\\\\s"'),
    ("a,b", '"a,b"'), ("", '""'),
])
def test_quote(value, expected):
    assert fm.quote(value) == expected


def test_flow_list_quotes_items():
    assert fm.flow_list(["a.py", "b c.py"]) == '[a.py, "b c.py"]'


def test_set_key_replaces_whole_block_extent_inside_metadata_only():
    ls = lines("name: x\nmetadata:\n  type: t\n  k:\n    - a\n\n    - b\n  z: 1\n")
    fm.set_key(ls, "k", "[c]")
    assert "".join(ls) == "name: x\nmetadata:\n  type: t\n  k: [c]\n  z: 1\n"


def test_set_key_ignores_same_named_key_outside_metadata_or_deeper():
    ls = lines("k: top\nmetadata:\n  type: t\n  sources:\n    k: nested\n")
    fm.set_key(ls, "k", "new")
    assert "".join(ls) == "k: top\nmetadata:\n  type: t\n  sources:\n    k: nested\n  k: new\n"


def test_set_key_remove_and_anchor_and_missing_anchor():
    ls = lines("metadata:\n  a: 1\n  b: 2\n")
    fm.set_key(ls, "c", "3", anchor="a")
    assert "".join(ls) == "metadata:\n  a: 1\n  c: 3\n  b: 2\n"
    fm.set_key(ls, "a", None)
    assert "".join(ls) == "metadata:\n  c: 3\n  b: 2\n"
    with pytest.raises(ValueError):
        fm.set_key(ls, "d", "4", anchor="nope")


def test_child_indent_is_first_non_blank_non_comment_metadata_line():
    ls = lines("metadata:\n\n# top comment\n    # deep comment\n    type: t\n    a: 1\n")
    fm.set_key(ls, "k", "v")
    assert ls[-1] == "    k: v\n"


def test_set_key_without_metadata_block_raises():
    with pytest.raises(ValueError):
        fm.set_key(lines("name: x\n"), "k", "v")


def test_set_key_handles_lines_without_newlines():
    ls = ["metadata:", "  a: 1"]
    fm.set_key(ls, "b", "2")
    assert ls == ["metadata:", "  a: 1", "  b: 2"]


def test_set_key_crlf_keeps_line_endings():
    ls = ["---\r\n", "metadata:\r\n", "  a: 1\r\n", "  k: old\r\n", "---\r\n"][1:4]
    fm.set_key(ls, "k", "new")
    fm.set_key(ls, "z", "9")
    assert "".join(ls) == "metadata:\r\n  a: 1\r\n  k: new\r\n  z: 9\r\n"


def test_column_zero_comment_between_metadata_keys_then_top_level_key():
    ls = lines("name: x\nmetadata:\n  a: 1\n# note\n  b: 2\ntags: [t]\n")
    fm.set_key(ls, "k", "v")
    assert "".join(ls) == "name: x\nmetadata:\n  a: 1\n# note\n  b: 2\n  k: v\ntags: [t]\n"
    fm.set_key(ls, "b", None)
    assert "".join(ls) == "name: x\nmetadata:\n  a: 1\n# note\n  k: v\ntags: [t]\n"
