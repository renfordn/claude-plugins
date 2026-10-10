"""planner rendering: Notes text, Code link, state hash."""
import os
import sys

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import planner  # noqa: E402


def test_notes_text_format():
    fields = {"current phase": "Design", "next action": "approve design", "slug": "2026-09-30-x"}
    assert planner.notes_text(fields, "fallback") == "Phase: Design · Next: approve design · Spec: 2026-09-30-x"
    assert planner.notes_text({"current phase": "Tasks"}, "dir-slug") == "Phase: Tasks · Next: None · Spec: dir-slug"


@pytest.mark.parametrize("url", [
    "git@github.com:renfordn/file-organiser.git",
    "https://github.com/renfordn/file-organiser.git",
    "https://github.com/renfordn/file-organiser",
    "ssh://git@github.com/renfordn/file-organiser.git",
])
def test_github_repo_from_origin_url(url):
    assert planner.github_repo(url) == "renfordn/file-organiser"


def test_github_repo_non_github_is_none():
    assert planner.github_repo("git@gitlab.com:a/b.git") is None
    assert planner.github_repo("unknown") is None
    assert planner.github_repo("https://notgithub.com/a/b.git") is None


def test_pr_url_only_when_merged():
    git = {"on_origin": True, "ahead": 1, "merged": False, "origin_url": "git@github.com:o/r.git",
           "merge_subject": "Merge pull request #26 from o/claude/x"}
    assert planner.code_link(git, "claude/x") == "https://github.com/o/r/tree/claude/x"


def test_code_link_prefers_pr_url_then_tree_url():
    base = {"on_origin": True, "ahead": 0, "merged": True, "origin_url": "git@github.com:o/r.git"}
    pr = dict(base, merge_subject="Merge pull request #26 from o/claude/x")
    assert planner.code_link(pr, "claude/x") == "https://github.com/o/r/pull/26"
    tree = dict(base, merge_subject="")
    assert planner.code_link(tree, "claude/x") == "https://github.com/o/r/tree/claude/x"
    assert planner.code_link(tree, None) is None
    assert planner.code_link({"on_origin": "unknown", "origin_url": "unknown"}, "claude/x") is None


def test_state_hash_is_stable_16_hex():
    h = planner.state_hash("abc")
    assert h == planner.state_hash("abc") != planner.state_hash("abd")
    assert len(h) == 16 and int(h, 16) >= 0


def test_notes_text_shows_slice_progress_when_known():
    fields = {"current phase": "Implementation", "next action": "Slice 2"}
    assert planner.notes_text(fields, "s", slices="1/2").endswith(" · Spec: s · Slices: 1/2")
    assert "Slices" not in planner.notes_text(fields, "s")
