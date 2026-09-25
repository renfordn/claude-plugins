"""Slice 11: worktree-store merge folds entries/research-digest/ by newest-mtime-wins.

Mirrors test_nelly_cleanup.py's summary-subdir tests (:113, :151). The subdir name is
hardcoded as the literal "research-digest" so these fail on behavior, not ImportError."""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_cleanup  # noqa: E402

TODAY = datetime.date(2026, 10, 30)
OLD = time.mktime(datetime.date(2026, 9, 1).timetuple())
DIGEST = "research-digest"


def _write(path, text, mtime=OLD):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.utime(path, (mtime, mtime))


def _entry(name, desc):
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: project\n---\nbody\n"


def _store(base, slug, project_path):
    d = os.path.join(base, slug)
    _write(os.path.join(d, "MEMORY.md"), f"# Agent Nelly Memory Index\n\nProject: {project_path}\n\n")
    return d


def _age_all(root_dir):
    for root, _, files in os.walk(root_dir):
        for f in files:
            os.utime(os.path.join(root, f), (OLD, OLD))


def _no_rename_copies(root_dir):
    """Names (files OR directories) carrying a clash-rename label, e.g. research-digest--wt1."""
    return [n for _, dirs, files in os.walk(root_dir) for n in dirs + files if "--wt1" in n]


def test_worktree_store_merges_digest_subdir_moved_and_newest_wins(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    parent_slug = nelly_cleanup.get_project_slug(repo)
    parent = _store(base, parent_slug, repo)
    digest_dir = os.path.join(parent, "entries", DIGEST)
    _write(os.path.join(digest_dir, "research-digest-b.md"),
           _entry("research-digest-b", "parent: stale"), mtime=OLD)

    wt_path = f"{repo}/.claude/worktrees/wt1"
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    wt_digest_dir = os.path.join(wt, "entries", DIGEST)
    _write(os.path.join(wt_digest_dir, "research-digest-a.md"),
           _entry("research-digest-a", "only in wt"))
    _write(os.path.join(wt_digest_dir, "research-digest-b.md"),
           _entry("research-digest-b", "wt: fresher"))
    _age_all(wt)
    newer = OLD + 1000  # still far past WORKTREE_IDLE_DAYS, just newer than the parent's copy
    os.utime(os.path.join(wt_digest_dir, "research-digest-b.md"), (newer, newer))

    result = nelly_cleanup.run_cleanup(TODAY, base=base)

    assert not os.path.exists(wt)
    assert [m["parent"] for m in result["merged"]] == [parent_slug]
    assert sorted(os.listdir(digest_dir)) == ["research-digest-a.md", "research-digest-b.md"]
    assert "only in wt" in open(os.path.join(digest_dir, "research-digest-a.md")).read()
    assert "wt: fresher" in open(os.path.join(digest_dir, "research-digest-b.md")).read()
    assert _no_rename_copies(parent) == []
    assert result["merged"][0]["moved"] == [
        "research-digest/research-digest-a.md", "research-digest/research-digest-b.md"]


def test_worktree_store_digest_subdir_keeps_newer_parent_copy_on_clash(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    parent_slug = nelly_cleanup.get_project_slug(repo)
    parent = _store(base, parent_slug, repo)
    digest_dir = os.path.join(parent, "entries", DIGEST)
    newer = OLD + 1000
    _write(os.path.join(digest_dir, "research-digest-b.md"),
           _entry("research-digest-b", "parent: fresher"), mtime=newer)

    wt_path = f"{repo}/.claude/worktrees/wt1"
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    wt_digest_dir = os.path.join(wt, "entries", DIGEST)
    _write(os.path.join(wt_digest_dir, "research-digest-b.md"),
           _entry("research-digest-b", "wt: stale"))
    _age_all(wt)

    nelly_cleanup.run_cleanup(TODAY, base=base)

    assert not os.path.exists(wt)
    assert os.listdir(digest_dir) == ["research-digest-b.md"]
    assert "parent: fresher" in open(os.path.join(digest_dir, "research-digest-b.md")).read()
    assert _no_rename_copies(parent) == []
    assert "merged-worktree-store" in open(os.path.join(parent, "CONSOLIDATION-LOG.md")).read()


def test_worktree_only_digest_subdir_moves_into_parent_without_one(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    parent_slug = nelly_cleanup.get_project_slug(repo)
    parent = _store(base, parent_slug, repo)

    wt_path = f"{repo}/.claude/worktrees/wt1"
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    _write(os.path.join(wt, "entries", DIGEST, "research-digest-a.md"),
           _entry("research-digest-a", "only in wt"))
    _age_all(wt)

    nelly_cleanup.run_cleanup(TODAY, base=base)

    digest_dir = os.path.join(parent, "entries", DIGEST)
    assert not os.path.exists(wt)
    assert os.path.isdir(digest_dir)
    assert os.listdir(digest_dir) == ["research-digest-a.md"]
    assert "only in wt" in open(os.path.join(digest_dir, "research-digest-a.md")).read()
    assert _no_rename_copies(parent) == []


def test_digest_merge_skips_atomic_write_orphans_and_ds_store(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    parent = _store(base, nelly_cleanup.get_project_slug(repo), repo)
    wt_path = f"{repo}/.claude/worktrees/wt1"
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    wt_digest_dir = os.path.join(wt, "entries", DIGEST)
    _write(os.path.join(wt_digest_dir, "research-digest-a.md"), _entry("research-digest-a", "a"))
    _write(os.path.join(wt_digest_dir, ".abc123.tmp"), "partial")
    _write(os.path.join(wt_digest_dir, ".DS_Store"), "finder")
    _age_all(wt)

    result = nelly_cleanup.run_cleanup(TODAY, base=base)

    assert not os.path.exists(wt)
    assert os.listdir(os.path.join(parent, "entries", DIGEST)) == ["research-digest-a.md"]
    assert result["merged"][0]["moved"] == ["research-digest/research-digest-a.md"]
