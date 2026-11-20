"""Release 5 slice 1D (R19): script writers go through scripts/nelly_store.py.

- nelly_populate_from_git writes new entries compare-and-swap (expected "missing"): an existing
  entry with different content survives and the new text lands in <memory_dir>/conflicts/.
- nelly_cleanup / nelly_weekly_consolidate MEMORY.md rewrites run under nelly_store.lock and
  replace the file atomically (new inode, no .tmp left behind).
- nelly_cleanup's cache-subdir merge keeps newest-wins at the canonical name and keeps the
  older differing copy in <store>/conflicts/ as `<subdir>--<name>--<label>.md` (never inside the
  cache subdir, where build_index would index it as a duplicate record).
"""
import datetime
import os
import re
import subprocess
import sys
import time

import pytest

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.join(SCRIPTS_DIR, "..", "hooks")
POPULATE = os.path.join(SCRIPTS_DIR, "nelly_populate_from_git.py")

sys.path.insert(0, SCRIPTS_DIR)
import nelly_cleanup  # noqa: E402
import nelly_weekly_consolidate  # noqa: E402

TODAY = datetime.date(2026, 10, 30)
OLD = time.mktime(datetime.date(2026, 9, 1).timetuple())

OTHER_CONTENT = (
    "---\nname: {slug}\ndescription: written by another session\nmetadata:\n"
    "  type: technique\n  confidence: explicit\n---\n\nHand-written content that must survive.\n"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _tmp_files(root):
    return [os.path.join(d, f) for d, _dirs, files in os.walk(root) for f in files
            if f.endswith(".tmp")]


def _conflicts(mem):
    d = os.path.join(mem, "conflicts")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


# ---------------------------------------------------------------------------
# Test Intent 2: nelly_populate_from_git is compare-and-swap
# ---------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path):
    full = dict(os.environ)
    full.update({
        "HOME": str(tmp_path / "home"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "home" / ".claude" / "plugins" / "data" / "agent-nelly"),
    })
    return full


def _memory_dir(repo, env):
    proc = subprocess.run([sys.executable, "nelly_memory.py", "--path", repo], cwd=HOOKS_DIR,
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = str(tmp_path / "repo")
    os.makedirs(os.path.join(r, "src"))
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _write(os.path.join(r, "src", "a.py"), "x = 1\n")
    _git(r, "add", "src/a.py")
    _git(r, "commit", "-q", "-m", "Seed store-safe populate")
    return r


def _slug(repo):
    return f"git-pattern-{_git(repo, 'rev-parse', 'HEAD')[:12]}"


def _populate(repo, env):
    proc = subprocess.run([sys.executable, POPULATE, "--repo", repo], capture_output=True,
                          text=True, env=env, timeout=120)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    return proc


def _stale_index(mem):
    """Index present but missing the slug: _entry_exists() trusts it, so populate takes the
    new-entry path although entries/<slug>.md is already on disk (the two-writer race)."""
    _write(os.path.join(mem, "nelly-index.json"), "[]\n")


def test_populate_existing_different_entry_goes_to_conflicts(repo, env):
    mem = _memory_dir(repo, env)
    slug = _slug(repo)
    target = os.path.join(mem, "entries", slug + ".md")
    original = OTHER_CONTENT.format(slug=slug)
    _write(target, original)
    _stale_index(mem)
    _populate(repo, env)
    assert _read(target) == original, "existing entry was overwritten"
    sidecars = _conflicts(mem)
    assert len(sidecars) == 1, sidecars
    assert re.fullmatch(rf"entries--{re.escape(slug)}\.\d{{8}}T\d{{6}}\.\d+(-\d+)?\.md", sidecars[0])
    assert "Seed store-safe populate" in _read(os.path.join(mem, "conflicts", sidecars[0]))


def test_populate_missing_entry_is_written_without_sidecar(repo, env):
    mem = _memory_dir(repo, env)
    _populate(repo, env)
    assert "Seed store-safe populate" in _read(os.path.join(mem, "entries", _slug(repo) + ".md"))
    assert _conflicts(mem) == []


def test_populate_identical_entry_leaves_no_sidecar(repo, env):
    mem = _memory_dir(repo, env)
    _populate(repo, env)
    target = os.path.join(mem, "entries", _slug(repo) + ".md")
    before = _read(target)
    _stale_index(mem)
    _populate(repo, env)
    assert _read(target) == before
    assert _conflicts(mem) == []


# ---------------------------------------------------------------------------
# Test Intent 4: MEMORY.md rewrites run under nelly_store.lock and are atomic
# ---------------------------------------------------------------------------

# Another writer doing a locked read-modify-write of MEMORY.md (append_memory_line style): it
# reads under the lock, holds it briefly, then writes back what it read plus its own line. A
# rewrite that skips the lock runs inside that window and is clobbered.
_LOCKED_APPENDER = """
import sys, time
sys.path.insert(0, %r)
import nelly_store
root, ready, line = sys.argv[1], sys.argv[2], sys.argv[3]
mem = root + "/MEMORY.md"
with nelly_store.lock(root):
    old = open(mem, encoding="utf-8").read()
    open(ready, "w").close()
    time.sleep(0.8)
    with open(mem, "w", encoding="utf-8") as fh:
        fh.write(old + line + "\\n")
""" % SCRIPTS_DIR

HOLDER_LINE = "- [Holder](entries/holder.md) — concurrent writer `[type:project]`"


def _start_locked_appender(root, tmp_path):
    ready = str(tmp_path / "appender-ready")
    p = subprocess.Popen([sys.executable, "-c", _LOCKED_APPENDER, root, ready, HOLDER_LINE],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 15
    while not os.path.exists(ready):
        assert p.poll() is None, p.communicate()[1]
        assert time.time() < deadline, "appender never acquired the lock"
        time.sleep(0.02)
    return p


def _finish(p):
    _so, se = p.communicate(timeout=30)
    assert p.returncode == 0, se


def _store_with_lines(tmp_path, entry_names):
    store = str(tmp_path / "mem" / "proj")
    lines = "".join(f"- [{n}](entries/{n}.md) — hook `[type:project]`\n" for n in entry_names)
    _write(os.path.join(store, "MEMORY.md"),
           "# Agent Nelly Memory Index\n\nProject: /p\n\n" + lines)
    return store


def _old_handoff(store):
    name = "session-handoff-2026-09-01-1000"
    _write(os.path.join(store, "entries", name + ".md"),
           f"---\nname: {name}\ndescription: Session ended -- active files: a.py\n"
           "metadata:\n  type: technique\n---\nbody\n", mtime=OLD)
    return name


def _rollup(store):
    return nelly_cleanup.roll_up_session_handoffs(store, TODAY, keep=0, min_age_days=14)


def test_cleanup_memory_md_rewrite_waits_for_store_lock(tmp_path):
    name = "session-handoff-2026-09-01-1000"
    store = _store_with_lines(tmp_path, ["keep-me", name])
    _old_handoff(store)
    p = _start_locked_appender(store, tmp_path)
    try:
        assert _rollup(store) == [name + ".md"]
    finally:
        _finish(p)
    lines = _read(os.path.join(store, "MEMORY.md")).splitlines()
    assert HOLDER_LINE in lines, "concurrent locked writer's line was lost"
    assert not any(f"(entries/{name}.md)" in ln for ln in lines), \
        "rolled-up handoff line resurrected: the rewrite ran outside nelly_store.lock"
    assert any("(entries/keep-me.md)" in ln for ln in lines)


def test_cleanup_memory_md_rewrite_is_atomic(tmp_path):
    name = "session-handoff-2026-09-01-1000"
    store = _store_with_lines(tmp_path, ["keep-me", name])
    _old_handoff(store)
    mem_md = os.path.join(store, "MEMORY.md")
    inode = os.stat(mem_md).st_ino
    _rollup(store)
    text = _read(mem_md)
    assert f"(entries/{name}.md)" not in text and "(entries/keep-me.md)" in text
    assert os.stat(mem_md).st_ino != inode, "MEMORY.md truncated in place, not atomically replaced"
    assert _tmp_files(store) == []


def test_weekly_memory_md_rewrite_waits_for_store_lock(tmp_path):
    store = _store_with_lines(tmp_path, ["keep-me", "stale-lesson"])
    p = _start_locked_appender(store, tmp_path)
    try:
        nelly_weekly_consolidate._remove_index_line(store, "stale-lesson")
    finally:
        _finish(p)
    lines = _read(os.path.join(store, "MEMORY.md")).splitlines()
    assert HOLDER_LINE in lines, "concurrent locked writer's line was lost"
    assert not any("(entries/stale-lesson.md)" in ln for ln in lines), \
        "removed line resurrected: the rewrite ran outside nelly_store.lock"
    assert any("(entries/keep-me.md)" in ln for ln in lines)


def test_weekly_memory_md_rewrite_is_atomic(tmp_path):
    store = _store_with_lines(tmp_path, ["keep-me", "stale-lesson"])
    mem_md = os.path.join(store, "MEMORY.md")
    inode = os.stat(mem_md).st_ino
    nelly_weekly_consolidate._remove_index_line(store, "stale-lesson")
    text = _read(mem_md)
    assert "(entries/stale-lesson.md)" not in text and "(entries/keep-me.md)" in text
    assert os.stat(mem_md).st_ino != inode, "MEMORY.md truncated in place, not atomically replaced"
    assert _tmp_files(store) == []


# ---------------------------------------------------------------------------
# Test Intent 5: cache-subdir merge keeps the older differing copy as a --<label> sidecar
# ---------------------------------------------------------------------------

CACHE_SUBDIRS = [nelly_cleanup.SUMMARY_SUBDIR, nelly_cleanup.DIGEST_SUBDIR]


def _merge_setup(tmp_path, subdir, parent_text, parent_mtime, wt_text, wt_mtime):
    base = str(tmp_path / "mem")
    parent = os.path.join(base, "proj")
    _write(os.path.join(parent, "MEMORY.md"), "# Agent Nelly Memory Index\n\nProject: /p\n\n")
    _write(os.path.join(parent, "entries", subdir, "cached.md"), parent_text, mtime=parent_mtime)
    store = os.path.join(base, "proj-claude-worktrees-wt1")
    _write(os.path.join(store, "MEMORY.md"), "# Agent Nelly Memory Index\n\n")
    _write(os.path.join(store, "entries", subdir, "cached.md"), wt_text, mtime=wt_mtime)
    nelly_cleanup.merge_worktree_store(store, "proj", "wt1", base=base)
    return parent


def _cache(parent, subdir):
    return os.path.join(parent, "entries", subdir)


@pytest.mark.parametrize("subdir", CACHE_SUBDIRS)
def test_cache_merge_worktree_newer_wins_and_parent_copy_kept_in_conflicts(tmp_path, subdir):
    parent = _merge_setup(tmp_path, subdir, "parent: older\n", OLD, "wt: newer\n", OLD + 1000)
    assert _read(os.path.join(_cache(parent, subdir), "cached.md")) == "wt: newer\n"
    assert os.listdir(_cache(parent, subdir)) == ["cached.md"]  # nothing indexable besides canonical
    assert _conflicts(parent) == [f"{subdir}--cached--wt1.md"]
    assert _read(os.path.join(parent, "conflicts", f"{subdir}--cached--wt1.md")) == "parent: older\n"


@pytest.mark.parametrize("subdir", CACHE_SUBDIRS)
def test_cache_merge_parent_newer_wins_and_worktree_copy_kept_in_conflicts(tmp_path, subdir):
    parent = _merge_setup(tmp_path, subdir, "parent: newer\n", OLD + 1000, "wt: older\n", OLD)
    assert _read(os.path.join(_cache(parent, subdir), "cached.md")) == "parent: newer\n"
    assert os.listdir(_cache(parent, subdir)) == ["cached.md"]
    assert _conflicts(parent) == [f"{subdir}--cached--wt1.md"]
    assert _read(os.path.join(parent, "conflicts", f"{subdir}--cached--wt1.md")) == "wt: older\n"


@pytest.mark.parametrize("subdir", CACHE_SUBDIRS)
def test_cache_merge_sidecar_name_is_unique(tmp_path, subdir):
    base = str(tmp_path / "mem")
    taken = os.path.join(base, "proj", "conflicts", f"{subdir}--cached--wt1.md")
    _write(taken, "earlier sidecar\n", mtime=OLD)
    parent = _merge_setup(tmp_path, subdir, "parent: older\n", OLD, "wt: newer\n", OLD + 1000)
    assert _read(taken) == "earlier sidecar\n"
    assert _read(os.path.join(parent, "conflicts", f"{subdir}--cached--wt1-2.md")) == "parent: older\n"
    assert _read(os.path.join(_cache(parent, subdir), "cached.md")) == "wt: newer\n"


@pytest.mark.parametrize("subdir", CACHE_SUBDIRS)
def test_cache_merge_identical_copies_leave_no_sidecar(tmp_path, subdir):
    parent = _merge_setup(tmp_path, subdir, "same\n", OLD, "same\n", OLD + 1000)
    assert os.listdir(_cache(parent, subdir)) == ["cached.md"]
    assert _read(os.path.join(_cache(parent, subdir), "cached.md")) == "same\n"
    assert _conflicts(parent) == []
