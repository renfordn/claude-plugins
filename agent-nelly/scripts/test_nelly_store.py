"""Release 5 slice 0: nelly_store -- compare-and-swap entry writes, locked read-modify-write,
MEMORY.md line append, lock contention, atomic writes. Concurrency is exercised with real
processes (subprocess), since the lock is a cross-process advisory flock."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import pytest

import build_index
import nelly_store

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _conflict_files(root):
    d = os.path.join(root, "conflicts")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def _tmp_files(root):
    found = []
    for dirpath, _dirs, files in os.walk(root):
        found += [os.path.join(dirpath, f) for f in files if f.endswith(".tmp")]
    return found


def _run_procs(code, args_list, timeout=60):
    """Start one python process per args tuple running `code` (with scripts/ on sys.path),
    all at once; return their (returncode, stdout, stderr)."""
    prelude = f"import sys; sys.path.insert(0, {SCRIPTS_DIR!r})\n"
    procs = [subprocess.Popen([sys.executable, "-c", prelude + code, *map(str, args)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for args in args_list]
    out = []
    for p in procs:
        so, se = p.communicate(timeout=timeout)
        out.append((p.returncode, so, se))
    return out


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "store"
    r.mkdir()
    return str(r)


# ---------------------------------------------------------------------------
# hashes
# ---------------------------------------------------------------------------

def test_missing_constant_and_hashes(root):
    assert nelly_store.MISSING == "missing"
    p = os.path.join(root, "a.md")
    assert nelly_store.file_sha(p) == "missing"
    _write(p, "héllo\n")
    assert nelly_store.file_sha(p) == _sha("héllo\n")
    assert nelly_store.text_sha("héllo\n") == _sha("héllo\n")


# ---------------------------------------------------------------------------
# write_entry: compare-and-swap (Test Intent 1-3)
# ---------------------------------------------------------------------------

_SIDECAR_RE = r"^{}\.\d{{8}}T\d{{6}}\.\d+(?:-\d+)?\.md$"
# F10: sidecar names keep the entry's directory relative to root, "/" -> "--".


def test_write_with_matching_hash_writes(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "base\n")
    res = nelly_store.write_entry(root, p, "new\n", _sha("base\n"))
    assert res == {"status": "written", "path": p}
    assert _read(p) == "new\n"
    assert _conflict_files(root) == []


def test_write_with_stale_hash_leaves_file_and_saves_sidecar(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "theirs\n")
    res = nelly_store.write_entry(root, p, "mine\n", _sha("base\n"))
    assert res["status"] == "conflict"
    assert _read(p) == "theirs\n"  # entry untouched
    assert os.path.dirname(res["path"]) == os.path.join(root, "conflicts")
    assert re.match(_SIDECAR_RE.format("entries--fact"), os.path.basename(res["path"]))
    assert _read(res["path"]) == "mine\n"


def test_two_conflicts_in_same_second_get_unique_sidecars(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "theirs\n")
    r1 = nelly_store.write_entry(root, p, "mine-1\n", _sha("base\n"))
    r2 = nelly_store.write_entry(root, p, "mine-2\n", _sha("base\n"))
    assert r1["status"] == r2["status"] == "conflict"
    assert r1["path"] != r2["path"]
    assert _read(r1["path"]) == "mine-1\n"
    assert _read(r2["path"]) == "mine-2\n"
    assert len(_conflict_files(root)) == 2


def test_unconditional_write_with_none_expected(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "anything\n")
    res = nelly_store.write_entry(root, p, "new\n", None)
    assert res == {"status": "written", "path": p}
    assert _read(p) == "new\n"


def test_already_desired_text_is_unchanged_even_with_stale_hash(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "desired\n")
    res = nelly_store.write_entry(root, p, "desired\n", _sha("something-else\n"))
    assert res == {"status": "unchanged", "path": p}
    assert _read(p) == "desired\n"
    assert _conflict_files(root) == []


def test_create_only_writes_missing_file_and_parent_dirs(root):
    p = os.path.join(root, "entries", "sub", "new.md")
    res = nelly_store.write_entry(root, p, "fresh\n", "missing")
    assert res == {"status": "written", "path": p}
    assert _read(p) == "fresh\n"


def test_create_only_on_existing_different_file_conflicts(root):
    p = os.path.join(root, "entries", "new.md")
    _write(p, "someone-else\n")
    res = nelly_store.write_entry(root, p, "fresh\n", nelly_store.MISSING)
    assert res["status"] == "conflict"
    assert _read(p) == "someone-else\n"
    assert re.match(_SIDECAR_RE.format("entries--new"), os.path.basename(res["path"]))
    assert _read(res["path"]) == "fresh\n"


def test_create_only_on_existing_identical_file_is_unchanged(root):
    p = os.path.join(root, "entries", "new.md")
    _write(p, "fresh\n")
    res = nelly_store.write_entry(root, p, "fresh\n", "missing")
    assert res["status"] == "unchanged"
    assert _conflict_files(root) == []


_WRITE_ENTRY_CODE = """
import json, nelly_store
root, path, text, expected = sys.argv[1:5]
print(json.dumps(nelly_store.write_entry(root, path, text, expected)))
"""


def test_two_updates_with_same_base_preserve_loser(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "base\n")
    base = _sha("base\n")
    results = _run_procs(_WRITE_ENTRY_CODE,
                         [(root, p, "from-A\n", base), (root, p, "from-B\n", base)])
    for rc, _so, se in results:
        assert rc == 0, se
    outs = [json.loads(so) for _rc, so, _se in results]
    assert sorted(o["status"] for o in outs) == ["conflict", "written"]
    winner = next(o for o in outs if o["status"] == "written")
    loser = next(o for o in outs if o["status"] == "conflict")
    survivors = {_read(p), _read(loser["path"])}
    assert survivors == {"from-A\n", "from-B\n"}
    assert winner["path"] == p
    assert len(_conflict_files(root)) == 1


# ---------------------------------------------------------------------------
# update_entry / upsert_index: locked read-modify-write (Test Intent 4)
# ---------------------------------------------------------------------------

def test_update_entry_passes_old_text_and_writes(root):
    p = os.path.join(root, "entries", "fact.md")
    seen = []

    def fn(old):
        seen.append(old)
        return "v1\n"

    assert nelly_store.update_entry(root, p, fn) == "written"
    assert seen == [None]
    assert _read(p) == "v1\n"
    assert nelly_store.update_entry(root, p, lambda old: old + "v2\n") == "written"
    assert _read(p) == "v1\nv2\n"


def test_update_entry_none_from_fn_is_unchanged(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "keep\n")
    assert nelly_store.update_entry(root, p, lambda old: None) == "unchanged"
    assert _read(p) == "keep\n"


_COUNTER_CODE = """
import nelly_store
root, path = sys.argv[1:3]
for _ in range(5):
    nelly_store.update_entry(root, path, lambda old: str(int(old or "0") + 1))
"""


def test_concurrent_update_entry_loses_no_increment(root):
    p = os.path.join(root, "entries", "counter.md")
    results = _run_procs(_COUNTER_CODE, [(root, p)] * 8)
    for rc, _so, se in results:
        assert rc == 0, se
    assert _read(p) == "40"
    assert _tmp_files(root) == []


def test_upsert_index_missing_or_corrupt_starts_empty_and_matches_write_index_format(root):
    seen = []

    def add(records):
        seen.append(list(records))
        return records + [{"slug": "b", "x": 1}, {"slug": "a", "x": 2}]

    new = nelly_store.upsert_index(root, add)
    assert seen == [[]]
    idx = os.path.join(root, "nelly-index.json")
    ref = os.path.join(root, "ref.json")
    build_index._write_index(ref, [{"slug": "b", "x": 1}, {"slug": "a", "x": 2}])
    assert _read(idx) == _read(ref)
    assert sorted(r["slug"] for r in new) == ["a", "b"]

    _write(idx, "{not json")
    seen.clear()
    nelly_store.upsert_index(root, lambda records: seen.append(list(records)) or records)
    assert seen == [[]]


def test_upsert_index_custom_name(root):
    nelly_store.upsert_index(root, lambda r: r + [{"slug": "z"}], name="other.json")
    with open(os.path.join(root, "other.json")) as fh:
        assert json.load(fh) == [{"slug": "z"}]
    assert not os.path.exists(os.path.join(root, "nelly-index.json"))


_UPSERT_CODE = """
import nelly_store
root, i = sys.argv[1:3]
nelly_store.upsert_index(root, lambda recs: recs + [{"slug": "s" + i, "stale_paths": ["p" + i]}])
"""


def test_concurrent_writes_preserve_every_stale_path(root):
    results = _run_procs(_UPSERT_CODE, [(root, i) for i in range(8)])
    for rc, _so, se in results:
        assert rc == 0, se
    with open(os.path.join(root, "nelly-index.json")) as fh:
        records = json.load(fh)
    assert sorted(r["slug"] for r in records) == sorted(f"s{i}" for i in range(8))
    assert sorted(p for r in records for p in r["stale_paths"]) == sorted(
        f"p{i}" for i in range(8))


# ---------------------------------------------------------------------------
# append_memory_line (Test Intent 5)
# ---------------------------------------------------------------------------

def test_append_memory_line_creates_file_and_dedupes(root):
    mem = os.path.join(root, "MEMORY.md")
    assert nelly_store.append_memory_line(root, "- [a](a.md) -- x") is True
    assert _read(mem) == "- [a](a.md) -- x\n"
    assert nelly_store.append_memory_line(root, "- [a](a.md) -- x") is False
    assert _read(mem) == "- [a](a.md) -- x\n"


def test_append_memory_line_puts_line_on_its_own_line(root):
    mem = os.path.join(root, "MEMORY.md")
    _write(mem, "# Index\n- old")  # no trailing newline
    assert nelly_store.append_memory_line(root, "- new") is True
    assert _read(mem).splitlines() == ["# Index", "- old", "- new"]
    assert _read(mem).endswith("- new\n")


def test_append_memory_line_substring_is_not_a_duplicate(root):
    mem = os.path.join(root, "MEMORY.md")
    _write(mem, "- new line extended\n")
    assert nelly_store.append_memory_line(root, "- new line") is True
    assert _read(mem).splitlines() == ["- new line extended", "- new line"]


_APPEND_CODE = """
import nelly_store
root = sys.argv[1]
nelly_store.append_memory_line(root, "- same line")
"""


def test_concurrent_append_memory_line_appends_once(root):
    results = _run_procs(_APPEND_CODE, [(root,)] * 8)
    for rc, _so, se in results:
        assert rc == 0, se
    assert _read(os.path.join(root, "MEMORY.md")).splitlines().count("- same line") == 1


# ---------------------------------------------------------------------------
# lock contention (Test Intent 6)
# ---------------------------------------------------------------------------

_HOLD_CODE = """
import time, nelly_store
root, ready = sys.argv[1:3]
with nelly_store.lock(root):
    open(ready, "w").close()
    time.sleep(10)
"""


def test_lock_raises_store_locked_when_held_by_other_process(root, tmp_path):
    assert issubclass(nelly_store.StoreLocked, Exception)
    ready = str(tmp_path / "ready")
    prelude = f"import sys; sys.path.insert(0, {SCRIPTS_DIR!r})\n"
    holder = subprocess.Popen([sys.executable, "-c", prelude + _HOLD_CODE, root, ready],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 15
        while not os.path.exists(ready):
            assert holder.poll() is None, holder.communicate()[1]
            assert time.time() < deadline, "holder never acquired the lock"
            time.sleep(0.02)
        assert os.path.exists(os.path.join(root, ".nelly.lock"))
        start = time.time()
        with pytest.raises(nelly_store.StoreLocked):
            with nelly_store.lock(root, timeout=0.3):
                pass
        assert time.time() - start >= 0.25
    finally:
        holder.kill()
        holder.communicate()
    # released once the holder is gone
    with nelly_store.lock(root, timeout=2.0):
        pass


# ---------------------------------------------------------------------------
# atomic writes (Test Intent 7)
# ---------------------------------------------------------------------------

def test_atomic_write_creates_parents_and_leaves_no_tmp(root):
    p = os.path.join(root, "a", "b", "c.md")
    nelly_store.atomic_write(p, "x\n")
    assert _read(p) == "x\n"
    assert _tmp_files(root) == []


def test_atomic_write_keeps_existing_mode(root):
    p = os.path.join(root, "m.md")
    _write(p, "old\n")
    os.chmod(p, 0o640)
    nelly_store.atomic_write(p, "new\n")
    assert _read(p) == "new\n"
    assert os.stat(p).st_mode & 0o7777 == 0o640
    assert _tmp_files(root) == []


def test_write_entry_paths_leave_no_tmp_and_keep_mode(root):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "base\n")
    os.chmod(p, 0o640)
    nelly_store.write_entry(root, p, "new\n", _sha("base\n"))
    nelly_store.write_entry(root, p, "loser\n", _sha("base\n"))  # conflict sidecar
    nelly_store.update_entry(root, p, lambda old: old + "more\n")
    nelly_store.upsert_index(root, lambda r: r)
    nelly_store.append_memory_line(root, "- l")
    assert os.stat(p).st_mode & 0o7777 == 0o640
    assert _tmp_files(root) == []


# ---------------------------------------------------------------------------
# review round 1 (F1, F3-F8, F10)
# ---------------------------------------------------------------------------
import contextlib
import errno

import path_resolution


def test_f1_corrupt_index_preserved_as_sidecar(root):
    idx = os.path.join(root, "nelly-index.json")
    _write(idx, "{not json")
    nelly_store.upsert_index(root, lambda r: r + [{"slug": "a"}])
    side = [f for f in _conflict_files(root) if f.startswith("nelly-index.") and f.endswith(".json")]
    assert len(side) == 1
    assert _read(os.path.join(root, "conflicts", side[0])) == "{not json"
    with open(idx) as fh:
        assert json.load(fh) == [{"slug": "a"}]


def test_f1_write_index_is_atomic(root, monkeypatch):
    idx = os.path.join(root, "nelly-index.json")
    build_index._write_index(idx, [{"slug": "a"}])
    before = _read(idx)

    def boom(*a, **k):
        raise RuntimeError("mid-write")

    monkeypatch.setattr(json, "dump", boom)
    monkeypatch.setattr(json, "dumps", boom)
    with pytest.raises(RuntimeError):
        build_index._write_index(idx, [{"slug": "b"}])
    assert _read(idx) == before
    assert _tmp_files(root) == []


def test_f1_build_and_upsert_run_under_store_lock(tmp_path, monkeypatch):
    import nelly_memory
    base = str(tmp_path / "mem")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    cwd = str(tmp_path / "proj")
    entries = nelly_memory.ensure_entries_dir(cwd)
    d = nelly_memory.memory_dir(cwd)
    ent = os.path.join(entries, "x.md")
    _write(ent, "---\nname: x\ndescription: d\n---\n")
    calls = []
    real = nelly_store.lock

    @contextlib.contextmanager
    def spy(r, timeout=2.0):
        calls.append(r)
        with real(r, timeout):
            yield

    monkeypatch.setattr(nelly_store, "lock", spy)
    build_index.build_project_index(cwd)
    assert d in calls
    calls.clear()
    build_index.upsert_project_entry(cwd, ent)
    assert d in calls


def test_f3_lock_is_reentrant_in_process(root):
    p = os.path.join(root, "entries", "e.md")
    with nelly_store.lock(root, timeout=0.3):
        assert nelly_store.write_entry(root, p, "x\n", None)["status"] == "written"
        nelly_store.upsert_index(root, lambda r: r + [{"slug": "a"}])
        assert nelly_store.append_memory_line(root, "- l") is True
        assert nelly_store.update_entry(root, p, lambda o: o + "y\n") == "written"
        with nelly_store.lock(root, timeout=0.3):
            pass
    assert _read(p) == "x\ny\n"


def test_f4_lock_timeout_saves_text_as_conflict_sidecar(root, monkeypatch):
    p = os.path.join(root, "entries", "fact.md")
    _write(p, "theirs\n")

    @contextlib.contextmanager
    def locked(r, timeout=2.0):
        raise nelly_store.StoreLocked("held")
        yield

    monkeypatch.setattr(nelly_store, "lock", locked)
    res = nelly_store.write_entry(root, p, "mine\n", None)
    assert res["status"] == "conflict"
    assert os.path.dirname(res["path"]) == os.path.join(root, "conflicts")
    assert _read(res["path"]) == "mine\n"
    assert _read(p) == "theirs\n"


def test_f5_non_contention_flock_error_falls_back_to_noop(root, monkeypatch):
    def bad(fd, op):
        raise OSError(errno.ENOLCK, "no locks")

    monkeypatch.setattr(nelly_store.fcntl, "flock", bad)
    start = time.time()
    with nelly_store.lock(root, timeout=5.0):
        pass
    assert time.time() - start < 1.0


def test_f6_replaced_lock_file_is_reacquired(root, monkeypatch):
    real = nelly_store.fcntl.flock
    state = {"n": 0}

    def flaky(fd, op):
        state["n"] += 1
        if state["n"] == 1:
            os.unlink(os.path.join(root, ".nelly.lock"))
        return real(fd, op)

    monkeypatch.setattr(nelly_store.fcntl, "flock", flaky)
    with nelly_store.lock(root, timeout=2.0):
        assert os.path.exists(os.path.join(root, ".nelly.lock"))
        assert os.fstat(os.open(os.path.join(root, ".nelly.lock"), os.O_RDONLY)).st_ino
    assert state["n"] >= 2


def test_f6_gitignore_covers_lock_and_tmp():
    lines = path_resolution.SHARED_ROOT_GITIGNORE.splitlines()
    assert ".nelly.lock" in lines
    assert ".*.tmp" in lines


def test_f7_atomic_write_failure_cleans_tmp_and_keeps_original(root, monkeypatch):
    p = os.path.join(root, "a.md")
    _write(p, "old\n")

    def boom(a, b):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        nelly_store.atomic_write(p, "new\n")
    assert _read(p) == "old\n"
    assert _tmp_files(root) == []


def test_f7_nelly_memory_atomic_write_delegates():
    import nelly_memory
    assert nelly_memory.atomic_write.__module__ in ("nelly_store",) or \
        nelly_memory.atomic_write is nelly_store.atomic_write


_DISTINCT_APPEND_CODE = """
import nelly_store
root, i = sys.argv[1:3]
for k in range(25):
    nelly_store.append_memory_line(root, "- line " + i + "." + str(k))
"""


def test_f8_concurrent_distinct_appends_all_present(root):
    results = _run_procs(_DISTINCT_APPEND_CODE, [(root, i) for i in range(8)])
    for rc, _so, se in results:
        assert rc == 0, se
    lines = _read(os.path.join(root, "MEMORY.md")).splitlines()
    assert sorted(lines) == sorted(f"- line {i}.{k}" for i in range(8) for k in range(25))


def test_f10_sidecar_name_keeps_directory_and_outside_root_falls_back(root, tmp_path):
    p = os.path.join(root, "entries", "sub", "fact.md")
    _write(p, "theirs\n")
    res = nelly_store.write_entry(root, p, "mine\n", _sha("base\n"))
    assert re.match(_SIDECAR_RE.format("entries--sub--fact"), os.path.basename(res["path"]))
    outside = str(tmp_path / "elsewhere" / "o.md")
    _write(outside, "theirs\n")
    res = nelly_store.write_entry(root, outside, "mine\n", _sha("base\n"))
    assert re.match(_SIDECAR_RE.format("o"), os.path.basename(res["path"]))


def test_f14_store_locked_is_an_oserror():
    assert issubclass(nelly_store.StoreLocked, OSError)


def test_f13_inode_mismatch_retry_honors_deadline(root, monkeypatch):
    real_stat = os.stat

    class _Fake:
        st_ino = -1

    def fake(path, *a, **k):
        if str(path).endswith(".nelly.lock"):
            return _Fake()
        return real_stat(path, *a, **k)

    monkeypatch.setattr(os, "stat", fake)
    start = time.time()
    with pytest.raises(nelly_store.StoreLocked):
        with nelly_store.lock(root, timeout=0.3):
            pass
    assert time.time() - start < 3


def test_f12_entry_is_parsed_inside_the_lock(tmp_path, monkeypatch):
    import nelly_memory
    base = str(tmp_path / "mem")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    cwd = str(tmp_path / "proj")
    ent = os.path.join(nelly_memory.ensure_entries_dir(cwd), "x.md")
    _write(ent, "---\nname: x\ndescription: d\n---\n")
    state = {"in_lock": False, "parsed_in_lock": None}
    real_lock, real_parse = nelly_store.lock, build_index._record_for_entry_file

    @contextlib.contextmanager
    def spy(r, timeout=2.0):
        with real_lock(r, timeout):
            state["in_lock"] = True
            try:
                yield
            finally:
                state["in_lock"] = False

    def parse(*a, **k):
        state["parsed_in_lock"] = state["in_lock"]
        return real_parse(*a, **k)

    monkeypatch.setattr(nelly_store, "lock", spy)
    monkeypatch.setattr(build_index, "_record_for_entry_file", parse)
    build_index.upsert_project_entry(cwd, ent)
    assert state["parsed_in_lock"] is True


def test_f6_scaffold_appends_missing_gitignore_lines_idempotently(root):
    gi = os.path.join(root, ".gitignore")
    _write(gi, "mine\nnelly-index.json\n")
    path_resolution.ensure_shared_root_scaffold(root)
    path_resolution.ensure_shared_root_scaffold(root)
    # Only patterns added after the first scaffold are appended (F16): a shipped line the
    # user removed (here hotspots.json) stays removed; each added line appears exactly once.
    assert _read(gi).splitlines() == ["mine", "nelly-index.json", ".nelly.lock", ".*.tmp"]


def test_update_entry_and_append_log_accept_a_lock_timeout(tmp_path):
    import inspect
    assert inspect.signature(nelly_store.update_entry).parameters["timeout"].default == 2.0
    assert inspect.signature(nelly_store.append_log).parameters["timeout"].default == 2.0
