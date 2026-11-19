import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import baseline  # noqa: E402
import sdd_state  # noqa: E402

EMPTY = baseline.EMPTY


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    state = tmp_path / "workflow-state.json"
    state.write_text("{}")
    return repo, str(state)


def test_record_stores_branch_head_dirty(tmp_path):
    repo, state = make_repo(tmp_path)
    (repo / "a.txt").write_text("changed")
    baseline.record(str(repo), state)
    b = sdd_state.read_baseline(state)
    assert b["branch"] == "main"
    assert len(b["head"]) == 40
    assert b["dirty_files"] == ["a.txt"]


def test_diff_empty_when_unchanged(tmp_path):
    repo, state = make_repo(tmp_path)
    baseline.record(str(repo), state)
    assert baseline.diff(str(repo), state) == EMPTY


def test_diff_reports_branch_head_and_files(tmp_path):
    repo, state = make_repo(tmp_path)
    baseline.record(str(repo), state)
    old = sdd_state.read_baseline(state)
    git(repo, "checkout", "-qb", "feature")
    (repo / "b.txt").write_text("b")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "more")
    (repo / "a.txt").write_text("dirty")
    d = baseline.diff(str(repo), state)
    assert d["branch_changed"] == ["main", "feature"]
    assert d["head_moved"][0] == old["head"] and d["head_moved"][1] != old["head"]
    assert d["files_changed"] == ["a.txt", "b.txt"]


def test_preexisting_dirty_not_reported(tmp_path):
    repo, state = make_repo(tmp_path)
    (repo / "a.txt").write_text("dirty")
    baseline.record(str(repo), state)
    assert baseline.diff(str(repo), state)["files_changed"] == []


def test_fail_open(tmp_path):
    notrepo = tmp_path / "nr"
    notrepo.mkdir()
    state = tmp_path / "s.json"
    state.write_text("{}")
    assert baseline.record(str(notrepo), str(state)) is None
    assert sdd_state.read_baseline(str(state)) is None
    assert baseline.diff(str(notrepo), str(state)) == EMPTY
    assert baseline.diff(str(tmp_path / "missing"), str(tmp_path / "none.json")) == EMPTY


def test_predirty_file_changed_or_cleaned_is_reported(tmp_path):
    repo, state = make_repo(tmp_path)
    (repo / "a.txt").write_text("dirty1")
    (repo / "c.txt").write_text("c")
    baseline.record(str(repo), state)
    assert sdd_state.read_baseline(state)["dirty_hashes"]["a.txt"]
    (repo / "a.txt").write_text("dirty2")
    (repo / "c.txt").unlink()
    assert baseline.diff(str(repo), state)["files_changed"] == ["a.txt", "c.txt"]


def test_unreachable_old_head_marks_incomplete(tmp_path):
    repo, state = make_repo(tmp_path)
    baseline.record(str(repo), state)
    sdd_state.update_json(state, lambda d: dict(
        d, baseline=dict(d["baseline"], head="a" * 40)))
    d = baseline.diff(str(repo), state)
    assert d["incomplete"] is True
    assert d["head_moved"][0] == "a" * 40


def test_snapshot_rename_and_space_paths(tmp_path):
    repo, state = make_repo(tmp_path)
    git(repo, "mv", "a.txt", "new name.txt")
    (repo / "u v.txt").write_text("x")
    branch, head, dirty = baseline._snapshot(str(repo), baseline.time.monotonic() + 3)
    assert {"a.txt", "new name.txt", "u v.txt"} <= set(dirty)


def test_snapshot_none_when_git_fails(tmp_path):
    assert baseline._snapshot(str(tmp_path), baseline.time.monotonic() + 3) is None
    assert baseline._snapshot(str(tmp_path), baseline.time.monotonic() - 1) is None
