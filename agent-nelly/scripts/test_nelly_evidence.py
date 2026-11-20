"""Tests for scripts/nelly_evidence.py -- record / refresh source evidence on memory entries (R16, R17)."""
import json
import os
import subprocess
import sys
from datetime import date

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_evidence.py")
HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nelly_memory  # noqa: E402
import research_digest  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    (r / "src" / "a.py").write_text("print('a')\n")
    (r / "src" / "b.py").write_text("print('b')\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "init")
    return r


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *map(str, args)], capture_output=True, text=True)


def record(repo, *extra, slug="a-fact", paths=("src/a.py",), **kw):
    args = ["record", "--cwd", repo, "--slug", slug, "--type", "reference", "--description", "A fact: it works",
            "--body", "Why: x", "--paths", *paths, "--basis", "observed", *extra]
    return cli(*args)


def entry_file(repo, slug="a-fact"):
    return nelly_memory.entry_path(str(repo), slug)


def index(repo):
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        return {r["slug"]: r for r in json.load(fh)}


def test_record_writes_evidence_entry_and_index(repo):
    proc = record(repo, "--symbols", "main", "helper", "--unknowns", "perf not checked")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "written"
    text = open(entry_file(repo)).read()
    blob = research_digest.blob_hash_file(str(repo / "src" / "a.py"))
    assert blob == git(repo, "hash-object", "src/a.py")
    assert f"name: a-fact\n" in text
    assert f"{{path: src/a.py, hash: {blob}}}" in text
    assert f"revision: {git(repo, 'rev-parse', 'HEAD')}" in text
    assert f"verified: {date.today().isoformat()}" in text
    assert "basis: observed" in text and "last_referenced:" in text
    assert "perf not checked" in text and "main" in text
    rec = index(repo)["a-fact"]
    assert rec["sources"] == [{"path": "src/a.py", "hash": blob}]
    assert rec["revision"] == git(repo, "rev-parse", "HEAD")
    assert rec["basis"] == "observed" and rec["symbols"] == ["main", "helper"]
    assert "a-fact" in open(os.path.join(nelly_memory.memory_dir(str(repo)), "MEMORY.md")).read()


def test_record_identical_is_unchanged_different_is_conflict(repo):
    assert record(repo).returncode == 0
    again = record(repo)
    assert again.returncode == 0 and json.loads(again.stdout)["status"] == "unchanged"
    other = record(repo, paths=("src/a.py", "src/b.py"))
    assert other.returncode == 3
    sidecar = json.loads(other.stdout)["path"]
    assert os.path.isfile(sidecar) and "conflicts" in sidecar
    assert "src/b.py" not in open(entry_file(repo)).read()


def test_record_refuses_modified_staged_untracked_paths(repo):
    (repo / "src" / "a.py").write_text("changed\n")
    proc = record(repo)
    assert proc.returncode == 2 and "nelly_pending.py add" in proc.stderr
    git(repo, "add", "src/a.py")
    assert record(repo).returncode == 2
    (repo / "src" / "new.py").write_text("x\n")
    assert record(repo, slug="n", paths=("src/new.py",)).returncode == 2
    assert not os.path.exists(entry_file(repo))


@pytest.mark.parametrize("bad", ["/abs/a.py", "../x.py", "~/x.py", "src/missing.py"])
def test_record_refuses_bad_paths(repo, bad):
    assert record(repo, paths=(bad,)).returncode == 2


def test_record_outside_git_uses_unknown_revision(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "f.txt").write_text("hi\n")
    assert record(d, paths=("f.txt",)).returncode == 0
    assert "revision: unknown" in open(entry_file(d)).read()


def test_record_requires_confidence_for_error_prevention(repo):
    proc = cli("record", "--cwd", repo, "--slug", "e", "--type", "error-prevention", "--description", "d",
               "--body", "b", "--paths", "src/a.py", "--basis", "observed")
    assert proc.returncode == 2 and "confidence" in proc.stderr


def _stale_entry(repo):
    """Record both paths, change both files + commit, then mark both stale like the freshness hook."""
    assert record(repo, paths=("src/a.py", "src/b.py")).returncode == 0
    (repo / "src" / "a.py").write_text("print('a2')\n")
    (repo / "src" / "b.py").write_text("print('b2')\n")
    git(repo, "commit", "-aqm", "change")
    path = entry_file(repo)
    text = open(path).read().replace(
        "---\n\n", "  stale: true\n  stale_since: 2026-11-01\n  stale_paths: [src/a.py, src/b.py]\n---\n\n", 1)
    with open(path, "w") as fh:
        fh.write(text)
    return path


def refresh(repo, *paths):
    return cli("refresh", "--cwd", repo, "--slug", "a-fact", "--paths", *paths)


def test_refresh_clears_only_checked_paths_and_keeps_stale_while_others_remain(repo):
    path = _stale_entry(repo)
    old_rev = open(path).read().split("revision: ")[1].split("\n")[0]
    proc = refresh(repo, "src/a.py")
    assert proc.returncode == 0, proc.stderr
    text = open(path).read()
    new_a = git(repo, "hash-object", "src/a.py")
    old_b_hash = research_digest.blob_hash(b"print('b')\n")
    assert f"{{path: src/a.py, hash: {new_a}}}" in text
    assert f"hash: {old_b_hash}" in text  # b untouched
    assert "stale: true" in text and "stale_since: 2026-11-01" in text
    assert "stale_paths: [src/b.py]" in text
    assert f"revision: {old_rev}" in text  # partial refresh: b was not re-hashed, so keep revision
    rec = index(repo)["a-fact"]
    assert rec["stale"] is True and rec["stale_paths"] == ["src/b.py"]

    assert refresh(repo, "src/b.py").returncode == 0
    text = open(path).read()
    assert "stale" not in text.replace("stale_", "x")  # no stale / stale_since / stale_paths lines left
    assert "stale_since" not in text and "stale_paths" not in text and "stale:" not in text
    assert "stale" not in index(repo)["a-fact"] or index(repo)["a-fact"]["stale"] is False


def test_refresh_rejects_path_not_in_sources_and_missing_entry(repo):
    _stale_entry(repo)
    before = open(entry_file(repo)).read()
    proc = refresh(repo, "src/other.py")
    assert proc.returncode == 2 and "src/other.py" in proc.stderr
    assert open(entry_file(repo)).read() == before
    assert cli("refresh", "--cwd", repo, "--slug", "nope", "--paths", "src/a.py").returncode == 2


def test_refresh_handles_block_form_sources(repo):
    assert record(repo).returncode == 0
    path = entry_file(repo)
    blob = git(repo, "hash-object", "src/a.py")
    text = open(path).read().replace(f"sources: [{{path: src/a.py, hash: {blob}}}]",
                                     "sources:\n    - path: src/a.py\n      hash: 0000")
    with open(path, "w") as fh:
        fh.write(text)
    assert refresh(repo, "src/a.py").returncode == 0
    assert index(repo)["a-fact"]["sources"] == [{"path": "src/a.py", "hash": blob}]


def test_store_locked_exits_75(repo, monkeypatch):
    import nelly_evidence
    import nelly_store

    def boom(*a, **k):
        raise nelly_store.StoreLocked("held")
    monkeypatch.setattr(nelly_store, "update_entry", boom)
    assert nelly_evidence.main(["refresh", "--cwd", str(repo), "--slug", "a-fact", "--paths", "src/a.py"]) == 75


def _commit_sub(repo):
    sub = repo / "sub"
    sub.mkdir()
    (sub / "x.py").write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "sub")
    return sub


def test_record_from_subdir_stores_repo_root_relative_path(repo):
    sub = _commit_sub(repo)
    proc = record(sub, paths=("x.py",))
    assert proc.returncode == 0, proc.stderr
    assert "{path: sub/x.py, hash: " in open(entry_file(sub)).read()
    assert index(sub)["a-fact"]["sources"][0]["path"] == "sub/x.py"


def test_refresh_from_subdir_matches_root_relative_sources(repo):
    sub = _commit_sub(repo)
    assert record(sub, paths=("x.py",)).returncode == 0
    (sub / "x.py").write_text("y\n")
    git(repo, "commit", "-aqm", "chg")
    proc = cli("refresh", "--cwd", sub, "--slug", "a-fact", "--paths", "x.py")
    assert proc.returncode == 0, proc.stderr
    assert git(repo, "hash-object", "sub/x.py") in open(entry_file(sub)).read()


@pytest.mark.parametrize("dirty", ["modify", "stage", "untracked"])
def test_refresh_refuses_dirty_path_and_leaves_entry_unchanged(repo, dirty):
    assert record(repo).returncode == 0
    before = open(entry_file(repo)).read()
    if dirty == "untracked":
        git(repo, "rm", "-q", "--cached", "src/a.py")
    else:
        (repo / "src" / "a.py").write_text("changed\n")
        if dirty == "stage":
            git(repo, "add", "src/a.py")
    proc = refresh(repo, "src/a.py")
    assert proc.returncode == 2 and "nelly_pending.py add" in proc.stderr
    assert open(entry_file(repo)).read() == before


@pytest.mark.parametrize("slug", ["f 2", "Bad Slug", "a/b", "-x"])
def test_record_rejects_unclean_or_conflict_copy_slugs(repo, slug):
    assert record(repo, slug=slug).returncode == 2


@pytest.mark.parametrize("name", ["[id].py", "my file.py"])
def test_record_accepts_glob_and_space_paths_when_clean(repo, name):
    (repo / "src" / name).write_text("z\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "odd")
    proc = record(repo, paths=("src/" + name,))
    assert proc.returncode == 0, proc.stderr
    assert index(repo)["a-fact"]["sources"][0]["path"] == "src/" + name


def test_record_unchanged_still_restores_memory_line(repo):
    assert record(repo).returncode == 0
    mem = os.path.join(nelly_memory.memory_dir(str(repo)), "MEMORY.md")
    lines = [ln for ln in open(mem).read().splitlines() if "a-fact" not in ln]
    with open(mem, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    proc = record(repo)
    assert json.loads(proc.stdout)["status"] == "unchanged"
    assert "a-fact" in open(mem).read()


def test_refresh_drop_paths(repo):
    path = _stale_entry(repo)
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/b.py")
    assert proc.returncode == 2  # source still exists
    git(repo, "rm", "-q", "src/b.py")
    git(repo, "commit", "-qm", "rm b")
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/b.py")
    assert proc.returncode == 0, proc.stderr
    text = open(path).read()
    assert "src/b.py" not in text
    assert "stale_paths: [src/a.py]" in text and "stale: true" in text
    assert [s["path"] for s in index(repo)["a-fact"]["sources"]] == ["src/a.py"]
    assert refresh(repo, "src/a.py").returncode == 0
    assert "stale" not in open(path).read()


def test_refresh_drop_paths_refuses_last_source_and_unknown_path(repo):
    assert record(repo).returncode == 0
    git(repo, "rm", "-q", "src/a.py")
    git(repo, "commit", "-qm", "rm a")
    before = open(entry_file(repo)).read()
    last = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/a.py")
    assert last.returncode == 2 and "archive" in last.stderr
    nope = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/zzz.py")
    assert nope.returncode == 2
    assert open(entry_file(repo)).read() == before


def _rev_verified(path):
    text = open(path).read()
    return (text.split("revision: ")[1].split("\n")[0], text.split("verified: ")[1].split("\n")[0])


def _age_verified(path):
    text = open(path).read()
    old = text.split("verified: ")[1].split("\n")[0]
    with open(path, "w") as fh:
        fh.write(text.replace(f"verified: {old}", "verified: 2000-01-01"))


def test_refresh_drop_only_keeps_revision_and_verified(repo):
    path = _stale_entry(repo)
    _age_verified(path)
    before = _rev_verified(path)
    git(repo, "rm", "-q", "src/b.py")
    git(repo, "commit", "-qm", "rm b")
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/b.py")
    assert proc.returncode == 0, proc.stderr
    assert _rev_verified(path) == before == (before[0], "2000-01-01")


def test_refresh_partial_keeps_revision_and_verified_and_full_updates_them(repo):
    path = _stale_entry(repo)
    _age_verified(path)
    before = _rev_verified(path)
    assert refresh(repo, "src/a.py").returncode == 0
    assert _rev_verified(path) == before
    assert refresh(repo, "src/a.py", "src/b.py").returncode == 0
    assert _rev_verified(path) == (git(repo, "rev-parse", "HEAD"), date.today().isoformat())


def test_refresh_drop_plus_rehash_of_all_remaining_updates_revision(repo):
    path = _stale_entry(repo)
    _age_verified(path)
    git(repo, "rm", "-q", "src/b.py")
    git(repo, "commit", "-qm", "rm b")
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--paths", "src/a.py", "--drop-paths", "src/b.py")
    assert proc.returncode == 0, proc.stderr
    assert _rev_verified(path) == (git(repo, "rev-parse", "HEAD"), date.today().isoformat())


def test_refresh_drop_paths_refuses_path_deleted_locally_but_still_in_head(repo):
    path = _stale_entry(repo)
    os.remove(repo / "src" / "b.py")  # deleted in the working tree only
    before = open(path).read()
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/b.py")
    assert proc.returncode == 2 and "HEAD" in proc.stderr
    assert open(path).read() == before


def test_refresh_handles_blank_line_inside_block_stale_paths(repo):
    path = _stale_entry(repo)
    text = open(path).read().replace(
        "stale_paths: [src/a.py, src/b.py]\n", "stale_paths:\n    - src/a.py\n\n    - src/b.py\n")
    with open(path, "w") as fh:
        fh.write(text)
    assert refresh(repo, "src/a.py", "src/b.py").returncode == 0
    fm = open(path).read().split("---")[1]
    assert "stale" not in fm and "    - src/b.py" not in fm


def test_record_file_relevance_from_subdir_surfaces_for_edits_from_root_and_subdir(repo):
    proc = cli("record", "--cwd", repo / "src", "--slug", "a-notes", "--type", "file-relevance",
               "--description", "notes on a", "--body", "Why: x", "--paths", "a.py", "--basis", "observed")
    assert proc.returncode == 0, proc.stderr
    line = next(ln for ln in open(os.path.join(nelly_memory.memory_dir(str(repo)), "MEMORY.md"))
                if "a-notes" in ln)
    assert "files:yes" in line and "paths:src/a.py" in line
    hook = os.path.join(HOOKS, "nelly_proactive_surface.py")
    for cwd in (repo, repo / "src"):
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "src" / "a.py")},
                   "cwd": str(cwd)}
        out = subprocess.run([sys.executable, hook], input=json.dumps(payload), capture_output=True,
                             text=True)
        assert out.returncode == 0, out.stderr
        reason = json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "notes on a" in reason, (cwd, out.stdout)


# --- review fixes F2 / F7 / cleanups ---

def _mark_stale_text(path, stale):
    text = open(path).read().replace(
        "---\n\n", f"  stale: true\n  stale_since: 2026-11-01\n  stale_paths: [{stale}]\n---\n\n", 1)
    with open(path, "w") as fh:
        fh.write(text)


def test_partial_refresh_advances_revision_when_untouched_sources_are_current_at_head(repo):
    assert record(repo, paths=("src/a.py", "src/b.py")).returncode == 0
    path = entry_file(repo)
    _age_verified(path)
    (repo / "src" / "a.py").write_text("print('a2')\n")  # only a changed; b matches its stored hash
    git(repo, "commit", "-aqm", "change a")
    _mark_stale_text(path, "src/a.py")
    assert refresh(repo, "src/a.py").returncode == 0
    assert _rev_verified(path) == (git(repo, "rev-parse", "HEAD"), date.today().isoformat())
    assert "stale" not in open(path).read().split("---")[1]


def test_drop_only_refresh_advances_when_remaining_sources_are_current_at_head(repo):
    assert record(repo, paths=("src/a.py", "src/b.py")).returncode == 0
    path = entry_file(repo)
    _age_verified(path)
    git(repo, "rm", "-q", "src/b.py")
    git(repo, "commit", "-qm", "rm b")
    _mark_stale_text(path, "src/b.py")
    proc = cli("refresh", "--cwd", repo, "--slug", "a-fact", "--drop-paths", "src/b.py")
    assert proc.returncode == 0, proc.stderr
    assert _rev_verified(path) == (git(repo, "rev-parse", "HEAD"), date.today().isoformat())


def test_partial_refresh_keeps_revision_when_an_untouched_source_differs_at_head(repo):
    assert record(repo, paths=("src/a.py", "src/b.py")).returncode == 0
    path = entry_file(repo)
    _age_verified(path)
    before = _rev_verified(path)
    (repo / "src" / "a.py").write_text("print('a2')\n")
    (repo / "src" / "b.py").write_text("print('b2')\n")
    git(repo, "commit", "-aqm", "change both")
    _mark_stale_text(path, "src/a.py, src/b.py")
    assert refresh(repo, "src/a.py").returncode == 0
    assert _rev_verified(path) == before


def _hold(root, ready, release):
    import nelly_store
    with nelly_store.lock(root):
        ready.set()
        release.wait(15)


def test_record_with_store_lock_held_elsewhere_exits_75_and_writes_nothing(repo):
    import multiprocessing
    root = nelly_memory.memory_dir(str(repo))
    ready, release = multiprocessing.Event(), multiprocessing.Event()
    holder = multiprocessing.Process(target=_hold, args=(root, ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        proc = record(repo)
        assert proc.returncode == 75, (proc.stdout, proc.stderr)
    finally:
        release.set()
        holder.join(10)
    assert not os.path.exists(entry_file(repo))
    memory_md = os.path.join(root, "MEMORY.md")
    assert not os.path.exists(memory_md) or "a-fact" not in open(memory_md).read()


def test_file_relevance_paths_with_whitespace_are_not_indexed_in_memory_md(repo):
    (repo / "src" / "a b.py").write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "space")
    proc = cli("record", "--cwd", repo, "--slug", "ab-notes", "--type", "file-relevance",
               "--description", "notes", "--body", "Why: x", "--paths", "src/a b.py", "src/a.py",
               "--basis", "observed")
    assert proc.returncode == 0, proc.stderr
    line = next(ln for ln in open(os.path.join(nelly_memory.memory_dir(str(repo)), "MEMORY.md"))
                if "ab-notes" in ln)
    assert "files:yes" in line and "paths:src/a.py]" in line and "a b.py" not in line


@pytest.mark.parametrize("flag,value", [("--description", "<desc>"), ("--body", "<body>"),
                                        ("--slug", "<kebab-slug>"), ("--cwd", "<repo root>")])
def test_record_rejects_placeholder_values(repo, flag, value):
    args = {"--cwd": str(repo), "--slug": "a-fact", "--type": "reference", "--description": "d",
            "--body": "b", "--paths": "src/a.py", "--basis": "observed"}
    args[flag] = value
    proc = cli("record", *[x for kv in args.items() for x in kv])
    assert proc.returncode == 2 and "placeholder" in proc.stderr
    assert not os.path.exists(entry_file(repo))
