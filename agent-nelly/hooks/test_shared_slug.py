"""Tests for hooks/shared_slug.py — the slug resolves from the git toplevel of cwd, so a
session whose cwd drifts into a repo subdirectory still maps to the repo's store, while a
linked worktree (its own toplevel) keeps its own `-claude-worktrees-<name>` slug."""
import json
import os
import subprocess
import sys

import pytest

from shared_slug import get_project_slug

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_slug_guard.py")


def _git(*args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git("-C", str(root), "init", "-q")
    _git("-C", str(root), "commit", "-q", "--allow-empty", "-m", "init")
    (root / "agent-nelly" / "hooks").mkdir(parents=True)
    return root


def _raw(path):
    import re
    return re.sub(r"[^A-Za-z0-9]+", "-", os.path.abspath(str(path))).strip("-").lower()


def test_subdirectory_maps_to_repo_slug(repo):
    assert get_project_slug(str(repo / "agent-nelly" / "hooks")) == _raw(repo)


def test_repo_root_slug_unchanged(repo):
    assert get_project_slug(str(repo)) == _raw(repo)


def test_worktree_keeps_own_slug(repo):
    wt = repo / ".claude" / "worktrees" / "wt1"
    _git("-C", str(repo), "worktree", "add", "-q", "--detach", str(wt))
    (wt / "scripts").mkdir()
    slug = get_project_slug(str(wt / "scripts"))
    assert slug == _raw(wt)
    assert slug.endswith("-repo-claude-worktrees-wt1")


def test_symlinked_cwd_into_repo_subdir_maps_to_repo(repo, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(repo / "agent-nelly" / "hooks")
    assert get_project_slug(str(link)) == _raw(os.path.realpath(repo))


def test_symlinked_repo_keeps_lexical_spelling(repo, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(repo)
    assert get_project_slug(str(alias / "agent-nelly")) == _raw(alias)


def test_non_repo_dir_falls_back_to_cwd(tmp_path):
    plain = tmp_path / "plain" / "sub"
    plain.mkdir(parents=True)
    assert get_project_slug(str(plain)) == _raw(plain)


def test_missing_dir_falls_back_to_cwd(tmp_path):
    missing = tmp_path / "does" / "not" / "exist"
    assert get_project_slug(str(missing)) == _raw(missing)


def test_guard_allows_repo_store_from_subdirectory(repo):
    import nelly_memory
    sub = str(repo / "agent-nelly")
    target = os.path.join(nelly_memory.BASE, _raw(repo), "entries", "note.md")
    proc = subprocess.run([sys.executable, GUARD], capture_output=True, text=True,
                          input=json.dumps({"tool_input": {"file_path": target}, "cwd": sub}))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""

    split = os.path.join(nelly_memory.BASE, _raw(repo) + "-agent-nelly", "entries", "note.md")
    proc = subprocess.run([sys.executable, GUARD], capture_output=True, text=True,
                          input=json.dumps({"tool_input": {"file_path": split}, "cwd": sub}))
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
