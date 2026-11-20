"""Release 5 slice 1D (R19): every hook writer goes through scripts/nelly_store.py, so no
concurrent write is lost.

- seen_count bumps are a locked read-modify-write (update_entry): N concurrent bumps -> N.
- New entries are compare-and-swap writes (write_entry, expected "missing"): an existing entry
  with different content is never overwritten -- the new text lands in <memory_dir>/conflicts/.
- MEMORY.md index lines go through append_memory_line: no lost lines, no duplicates.
- A held store lock (StoreLocked) never blocks or crashes a hook: exit 0, no traceback, and the
  hook does not fall back to an unlocked write.

Hooks are driven as the harness does (JSON on stdin to a subprocess) with an isolated
CLAUDE_PLUGIN_DATA; concurrency uses real processes since the lock is a cross-process flock.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

import pytest

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(HOOKS_DIR, "..", "scripts")
AUTO_HOOK = os.path.join(HOOKS_DIR, "nelly_auto_extract.py")
COMMIT_HOOK = os.path.join(HOOKS_DIR, "nelly_commit_extract.py")
SESSION_END_HOOK = os.path.join(HOOKS_DIR, "nelly_session_end.py")

PYTEST_FAILURE_OUTPUT = """\
============================= FAILURES =============================
FAILED test_foo.py::test_foo - assert 1 == 2
1 failed, 2 passed in 0.05s
"""
AUTO_SLUG = "auto-test-foo-py-test-foo"

COMMIT_HASH = "abc1234def56"
COMMIT_OUTPUT = f"""\
[main {COMMIT_HASH}] Add store-safe writer
 2 files changed, 10 insertions(+)
 create mode 100644 src/a.py
"""
COMMIT_SLUG = f"git-pattern-{COMMIT_HASH[:12]}"

OTHER_CONTENT = (
    "---\nname: {slug}\ndescription: written by another session\nmetadata:\n"
    "  type: technique\n  confidence: explicit\n---\n\nHand-written content that must survive.\n"
)

_HOLD = """
import sys, time
sys.path.insert(0, %r)
import nelly_store
with nelly_store.lock(sys.argv[1]):
    open(sys.argv[2], "w").close()
    time.sleep(float(sys.argv[3]))
""" % SCRIPTS_DIR


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path):
    state = tmp_path / "session-state"
    state.mkdir()
    full = dict(os.environ)
    full.update({
        "HOME": str(tmp_path / "home"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "home" / ".claude" / "plugins" / "data" / "agent-nelly"),
        "NELLY_SESSION_STATE_DIR": str(state),
    })
    full.pop("NELLY_GATE", None)
    return full


@pytest.fixture
def cwd(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return str(d)


def _memory_dir(cwd, env):
    proc = subprocess.run([sys.executable, "nelly_memory.py", "--path", cwd], cwd=HOOKS_DIR,
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _run_hook(hook, payload, env):
    return subprocess.run([sys.executable, hook], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=60)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _conflicts(mem):
    d = os.path.join(mem, "conflicts")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def _stale_index(mem):
    """An index that exists but doesn't list the slug -- _entry_exists() trusts it, so the hook
    takes the new-entry path even though entries/<slug>.md is already on disk (the race window
    between two writers)."""
    _write(os.path.join(mem, "nelly-index.json"), "[]\n")


def _seen_count(path):
    m = re.search(r"^\s*seen_count:\s*(\d+)\s*$", _read(path), re.M)
    return int(m.group(1)) if m else None


def _bash_payload(cwd, stdout, command="pytest"):
    return {"tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "stderr": ""}, "cwd": cwd,
            "session_id": "store-test"}


def _transcript(tmp_path, cwd):
    path = tmp_path / "transcript.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": os.path.join(cwd, "src", "a.py")}}]}}) + "\n")
    return str(path)


def _session_end_payload(cwd, transcript):
    return {"session_id": "store-test", "transcript_path": transcript, "cwd": cwd,
            "hook_event_name": "SessionEnd", "reason": "other"}


def _handoff_slugs():
    now = datetime.now()
    return [f"session-handoff-{(now + timedelta(minutes=m)).strftime('%Y-%m-%d-%H%M')}"
            for m in (0, 1)]


@pytest.fixture
def hold_lock(tmp_path):
    """Hold <root>/.nelly.lock from another process for `seconds`; yields a starter."""
    holders = []

    def start(root, seconds=30.0):
        ready = str(tmp_path / f"ready-{len(holders)}")
        p = subprocess.Popen([sys.executable, "-c", _HOLD, root, ready, str(seconds)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        holders.append(p)
        deadline = time.time() + 15
        while not os.path.exists(ready):
            assert p.poll() is None, p.communicate()[1]
            assert time.time() < deadline, "holder never acquired the lock"
            time.sleep(0.02)
        return p

    yield start
    for p in holders:
        p.kill()
        p.communicate()


def _make_auto_entry(cwd, env):
    """Write the auto-extract entry once through the hook itself, then return its path."""
    proc = _run_hook(AUTO_HOOK, _bash_payload(cwd, PYTEST_FAILURE_OUTPUT), env)
    assert proc.returncode == 0, proc.stderr
    path = os.path.join(_memory_dir(cwd, env), "entries", AUTO_SLUG + ".md")
    assert os.path.isfile(path)
    assert _seen_count(path) == 1
    return path


# ---------------------------------------------------------------------------
# Test Intent 1: concurrent seen_count bumps are never lost
# ---------------------------------------------------------------------------

_BUMP_CODE = """
import sys
sys.path.insert(0, %r)
import nelly_auto_extract
cwd, slug, loops = sys.argv[1], sys.argv[2], int(sys.argv[3])
misses = 0
for _ in range(loops):
    if nelly_auto_extract._bump_seen_count_and_maybe_promote(cwd, slug) is None:
        misses += 1
print(misses)
""" % HOOKS_DIR


def test_concurrent_seen_count_bumps_are_all_counted(cwd, env):
    path = _make_auto_entry(cwd, env)
    procs_n, loops = 12, 30
    procs = [subprocess.Popen([sys.executable, "-c", _BUMP_CODE, cwd, AUTO_SLUG, str(loops)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
             for _ in range(procs_n)]
    results = [p.communicate(timeout=180) + (p.returncode,) for p in procs]
    for so, se, rc in results:
        assert rc == 0, se
    misses = sum(int(so.strip() or 0) for so, _se, _rc in results)
    assert misses == 0, f"{misses} bumps saw a missing/torn entry (unlocked read-modify-write)"
    assert _seen_count(path) == 1 + procs_n * loops
    assert "confidence: explicit" in _read(path)  # promoted once past the threshold


# ---------------------------------------------------------------------------
# Test Intent 2: new-entry writers are compare-and-swap (expected "missing")
# ---------------------------------------------------------------------------

def _assert_parked(mem, slug, marker):
    """Exactly one entries--<slug>.*.md sidecar holds the hook's text (nothing was dropped)."""
    sidecars = [n for n in _conflicts(mem) if n.startswith(f"entries--{slug}.")]
    assert len(sidecars) == 1, _conflicts(mem)
    assert marker in _read(os.path.join(mem, "conflicts", sidecars[0]))


def _assert_conflict_kept(mem, slug, original, marker):
    target = os.path.join(mem, "entries", slug + ".md")
    assert _read(target) == original, "existing entry was overwritten"
    sidecars = _conflicts(mem)
    assert len(sidecars) == 1, sidecars
    assert re.fullmatch(rf"entries--{re.escape(slug)}\.\d{{8}}T\d{{6}}\.\d+(-\d+)?\.md", sidecars[0])
    assert marker in _read(os.path.join(mem, "conflicts", sidecars[0]))


def test_commit_extract_existing_different_entry_goes_to_conflicts(cwd, env):
    mem = _memory_dir(cwd, env)
    original = OTHER_CONTENT.format(slug=COMMIT_SLUG)
    _write(os.path.join(mem, "entries", COMMIT_SLUG + ".md"), original)
    _stale_index(mem)
    proc = _run_hook(COMMIT_HOOK, _bash_payload(cwd, COMMIT_OUTPUT, "git commit -m x"), env)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    _assert_conflict_kept(mem, COMMIT_SLUG, original, "Add store-safe writer")


def test_commit_extract_missing_entry_is_written_without_sidecar(cwd, env):
    mem = _memory_dir(cwd, env)
    proc = _run_hook(COMMIT_HOOK, _bash_payload(cwd, COMMIT_OUTPUT, "git commit -m x"), env)
    assert proc.returncode == 0, proc.stderr
    assert "Add store-safe writer" in _read(os.path.join(mem, "entries", COMMIT_SLUG + ".md"))
    assert _conflicts(mem) == []


def test_commit_extract_identical_entry_leaves_no_sidecar(cwd, env):
    mem = _memory_dir(cwd, env)
    payload = _bash_payload(cwd, COMMIT_OUTPUT, "git commit -m x")
    assert _run_hook(COMMIT_HOOK, payload, env).returncode == 0
    before = _read(os.path.join(mem, "entries", COMMIT_SLUG + ".md"))
    _stale_index(mem)
    assert _run_hook(COMMIT_HOOK, payload, env).returncode == 0
    assert _read(os.path.join(mem, "entries", COMMIT_SLUG + ".md")) == before
    assert _conflicts(mem) == []


def test_auto_extract_existing_different_entry_goes_to_conflicts(cwd, env):
    mem = _memory_dir(cwd, env)
    original = OTHER_CONTENT.format(slug=AUTO_SLUG)
    _write(os.path.join(mem, "entries", AUTO_SLUG + ".md"), original)
    _stale_index(mem)
    proc = _run_hook(AUTO_HOOK, _bash_payload(cwd, PYTEST_FAILURE_OUTPUT), env)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    _assert_conflict_kept(mem, AUTO_SLUG, original, "pytest failure: test_foo.py::test_foo")


def test_auto_extract_missing_entry_is_written_without_sidecar(cwd, env):
    path = _make_auto_entry(cwd, env)
    assert "pytest failure" in _read(path)
    assert _conflicts(_memory_dir(cwd, env)) == []


def test_auto_extract_identical_entry_leaves_no_sidecar(cwd, env):
    path = _make_auto_entry(cwd, env)
    mem = _memory_dir(cwd, env)
    before = _read(path)
    _stale_index(mem)
    assert _run_hook(AUTO_HOOK, _bash_payload(cwd, PYTEST_FAILURE_OUTPUT), env).returncode == 0
    assert _read(path) == before
    assert _conflicts(mem) == []


def test_session_end_existing_different_entry_goes_to_conflicts(cwd, env, tmp_path):
    mem = _memory_dir(cwd, env)
    slugs = _handoff_slugs()  # this minute and the next, in case the clock rolls over
    originals = {}
    for slug in slugs:
        originals[slug] = OTHER_CONTENT.format(slug=slug)
        _write(os.path.join(mem, "entries", slug + ".md"), originals[slug])
    _stale_index(mem)
    proc = _run_hook(SESSION_END_HOOK, _session_end_payload(cwd, _transcript(tmp_path, cwd)), env)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    for slug in slugs:
        assert _read(os.path.join(mem, "entries", slug + ".md")) == originals[slug]
    sidecars = _conflicts(mem)
    assert len(sidecars) == 1, sidecars
    assert any(sidecars[0].startswith(f"entries--{s}.") for s in slugs), sidecars
    assert "Session handoff:" in _read(os.path.join(mem, "conflicts", sidecars[0]))


def test_session_end_missing_entry_is_written_without_sidecar(cwd, env, tmp_path):
    mem = _memory_dir(cwd, env)
    proc = _run_hook(SESSION_END_HOOK, _session_end_payload(cwd, _transcript(tmp_path, cwd)), env)
    assert proc.returncode == 0, proc.stderr
    written = [n for n in os.listdir(os.path.join(mem, "entries")) if n.startswith("session-handoff-")]
    assert len(written) == 1
    assert _conflicts(mem) == []


# ---------------------------------------------------------------------------
# Test Intent 3: MEMORY.md lines -- no lost lines, no duplicates
# ---------------------------------------------------------------------------

_INDEX_LINE_CODE = """
import sys
sys.path.insert(0, %r)
import nelly_memory
cwd, worker, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
for i in range(count):
    nelly_memory.write_index_line(cwd, f"w{worker}-entry-{i}", f"hook {worker}/{i}", "project")
""" % HOOKS_DIR


def test_concurrent_write_index_line_keeps_every_line(cwd, env):
    mem = _memory_dir(cwd, env)  # MEMORY.md header already exists
    workers, count = 8, 25
    procs = [subprocess.Popen([sys.executable, "-c", _INDEX_LINE_CODE, cwd, str(w), str(count)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
             for w in range(workers)]
    for p in procs:
        _so, se = p.communicate(timeout=180)
        assert p.returncode == 0, se
    text = _read(os.path.join(mem, "MEMORY.md"))
    assert text.startswith("# Agent Nelly Memory Index")
    lines = [ln for ln in text.splitlines() if ln.startswith("- [")]
    assert len(lines) == workers * count
    for w in range(workers):
        for i in range(count):
            assert sum(f"(entries/w{w}-entry-{i}.md)" in ln for ln in lines) == 1


def test_write_index_line_does_not_duplicate_an_existing_line(cwd, env):
    code = """
import sys
sys.path.insert(0, %r)
import nelly_memory
a = nelly_memory.write_index_line(sys.argv[1], "dup-entry", "same hook", "project", confidence="inferred")
b = nelly_memory.write_index_line(sys.argv[1], "dup-entry", "same hook", "project", confidence="inferred")
assert a == b, (a, b)
print(a)
""" % HOOKS_DIR
    proc = subprocess.run([sys.executable, "-c", code, cwd], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    line = proc.stdout.strip()
    text = _read(os.path.join(_memory_dir(cwd, env), "MEMORY.md"))
    assert text.splitlines().count(line) == 1


# ---------------------------------------------------------------------------
# Test Intent 6: a held store lock -> exit 0, no traceback, no unlocked fallback write
# ---------------------------------------------------------------------------

def test_auto_extract_bump_store_locked_exits_zero_without_unlocked_write(cwd, env, hold_lock):
    path = _make_auto_entry(cwd, env)
    before = _read(path)
    hold_lock(_memory_dir(cwd, env))
    start = time.time()
    proc = _run_hook(AUTO_HOOK, _bash_payload(cwd, PYTEST_FAILURE_OUTPUT), env)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr and "StoreLocked" not in proc.stderr, proc.stderr
    assert _read(path) == before, "seen_count bumped while another process held the store lock"
    assert time.time() - start < 30


def test_auto_extract_new_entry_store_locked_exits_zero_without_unlocked_write(cwd, env, hold_lock):
    mem = _memory_dir(cwd, env)
    hold_lock(mem)
    proc = _run_hook(AUTO_HOOK, _bash_payload(cwd, PYTEST_FAILURE_OUTPUT), env)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr and "StoreLocked" not in proc.stderr, proc.stderr
    assert not os.path.exists(os.path.join(mem, "entries", AUTO_SLUG + ".md")), \
        "entry written while another process held the store lock"
    _assert_parked(mem, AUTO_SLUG, "pytest failure: test_foo.py::test_foo")


def test_commit_extract_store_locked_exits_zero_without_unlocked_write(cwd, env, hold_lock):
    mem = _memory_dir(cwd, env)
    hold_lock(mem)
    proc = _run_hook(COMMIT_HOOK, _bash_payload(cwd, COMMIT_OUTPUT, "git commit -m x"), env)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr and "StoreLocked" not in proc.stderr, proc.stderr
    assert not os.path.exists(os.path.join(mem, "entries", COMMIT_SLUG + ".md")), \
        "entry written while another process held the store lock"
    _assert_parked(mem, COMMIT_SLUG, "Add store-safe writer")


def test_session_end_store_locked_exits_zero_without_unlocked_write(cwd, env, tmp_path, hold_lock):
    mem = _memory_dir(cwd, env)
    hold_lock(mem)
    proc = _run_hook(SESSION_END_HOOK, _session_end_payload(cwd, _transcript(tmp_path, cwd)), env)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr and "StoreLocked" not in proc.stderr, proc.stderr
    entries = os.path.join(mem, "entries")
    written = [n for n in os.listdir(entries) if n.startswith("session-handoff-")] \
        if os.path.isdir(entries) else []
    assert written == [], "handoff written while another process held the store lock"
    sidecars = _conflicts(mem)
    assert len(sidecars) == 1 and sidecars[0].startswith("entries--session-handoff-"), sidecars
    assert "Session handoff:" in _read(os.path.join(mem, "conflicts", sidecars[0]))


# ---------------------------------------------------------------------------
# _write_index_header never clobbers an existing MEMORY.md (deterministic race)
# ---------------------------------------------------------------------------

def test_write_index_header_does_not_clobber_when_exists_check_races(tmp_path, monkeypatch):
    """The unlocked exists() check can be stale (another writer created the file and appended a
    line in between). The creation must re-check under the lock and never replace the file."""
    sys.path.insert(0, HOOKS_DIR)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    import nelly_memory
    idx = tmp_path / "store" / "MEMORY.md"
    idx.parent.mkdir()
    idx.write_text("# Agent Nelly Memory Index\n\n- [A](entries/a.md) -- kept `[type:project]`\n")
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    nelly_memory._write_index_header(str(idx), "# Agent Nelly Memory Index\n\n")
    monkeypatch.undo()
    assert "(entries/a.md)" in idx.read_text()
    assert not (tmp_path / "store" / "conflicts").exists()


def test_write_index_header_creates_file_once_without_conflicts_dir(tmp_path):
    sys.path.insert(0, HOOKS_DIR)
    import nelly_memory
    idx = tmp_path / "store" / "MEMORY.md"
    idx.parent.mkdir()
    nelly_memory._write_index_header(str(idx), "# H\n")
    nelly_memory._write_index_header(str(idx), "# H2\n")
    assert idx.read_text() == "# H\n"
    assert not (tmp_path / "store" / "conflicts").exists()


# ---------------------------------------------------------------------------
# F3: create_entry holds one lock across entry write, index line and index upsert
# ---------------------------------------------------------------------------

_CREATE_CODE = """
import sys, os
sys.path.insert(0, %r)
import nelly_memory, nelly_store
cwd, slug = sys.argv[1], sys.argv[2]
mem = nelly_memory.memory_dir(cwd)
content = "---\\nname: %%s\\ndescription: d\\nmetadata:\\n  type: technique\\n---\\n\\nbody\\n" %% slug
held = []
orig = nelly_store.lock
import contextlib
@contextlib.contextmanager
def spy(root, timeout=2.0):
    held.append("in")
    with orig(root, timeout):
        yield
nelly_store.lock = spy
status = nelly_memory.create_entry(cwd, slug, content, "d", "technique", confidence="inferred")
print(status)
""" % HOOKS_DIR


def test_create_entry_statuses_and_index(cwd, env):
    def run(slug):
        p = subprocess.run([sys.executable, "-c", _CREATE_CODE, cwd, slug], capture_output=True,
                           text=True, env=env)
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()
    mem = _memory_dir(cwd, env)
    assert run("ce-one") == "written"
    assert run("ce-one") == "unchanged"
    text = _read(os.path.join(mem, "MEMORY.md"))
    assert text.count("(entries/ce-one.md)") == 1
    # unchanged entry whose index line went missing: the line is restored (idempotent)
    _write(os.path.join(mem, "MEMORY.md"), "# Agent Nelly Memory Index\n\n")
    assert run("ce-one") == "unchanged"
    assert _read(os.path.join(mem, "MEMORY.md")).count("(entries/ce-one.md)") == 1
    # different existing content -> conflict, entry intact, no index line for our text
    _write(os.path.join(mem, "entries", "ce-two.md"), "hand-written\n")
    assert run("ce-two") == "conflict"
    assert _read(os.path.join(mem, "entries", "ce-two.md")) == "hand-written\n"
    assert len(_conflicts(mem)) == 1


def test_create_entry_holds_one_lock_across_entry_line_and_index(tmp_path, monkeypatch):
    sys.path.insert(0, HOOKS_DIR)
    sys.path.insert(0, SCRIPTS_DIR)
    import nelly_memory
    import nelly_store
    import build_index
    monkeypatch.setattr(nelly_memory, "BASE", str(tmp_path / "base"))
    monkeypatch.setattr(nelly_memory, "SHARED_ROOT", None, raising=False)
    cwd = str(tmp_path / "proj")
    os.makedirs(cwd)
    root = nelly_memory.memory_dir(cwd)
    key = os.path.realpath(root)
    outer, seen = [], []
    real_lock, real_write, real_append, real_upsert = (
        nelly_store.lock, nelly_store.write_entry, nelly_store.append_memory_line,
        build_index.upsert_project_entry)

    import contextlib

    @contextlib.contextmanager
    def spy_lock(r, timeout=2.0):
        if os.path.realpath(r) == key and key not in nelly_store._held():
            outer.append(1)  # a fresh (outermost) acquisition of this store's lock
        with real_lock(r, timeout):
            yield

    def watch(name, real):
        def wrapper(*a, **k):
            seen.append((name, key in nelly_store._held()))
            return real(*a, **k)
        return wrapper

    monkeypatch.setattr(nelly_store, "lock", spy_lock)
    monkeypatch.setattr(nelly_store, "write_entry", watch("write_entry", real_write))
    monkeypatch.setattr(nelly_store, "append_memory_line", watch("append_memory_line", real_append))
    monkeypatch.setattr(build_index, "upsert_project_entry", watch("upsert", real_upsert))
    content = "---\nname: one-hold\ndescription: d\nmetadata:\n  type: technique\n---\n\nbody\n"
    assert nelly_memory.create_entry(cwd, "one-hold", content, "d", "technique") == "written"
    assert [n for n, _ in seen] == ["write_entry", "append_memory_line", "upsert"]
    assert all(held for _n, held in seen), seen  # each ran while the store lock was held
    assert len(outer) == 1, "lock was released and re-acquired between steps"


def test_write_index_header_leaves_unreadable_existing_index_alone(tmp_path):
    sys.path.insert(0, HOOKS_DIR)
    import nelly_memory
    idx = tmp_path / "store" / "MEMORY.md"
    idx.parent.mkdir()
    idx.write_text("# Agent Nelly Memory Index\n\n- [A](entries/a.md) -- kept `[type:project]`\n")
    idx.chmod(0)
    try:
        if os.access(str(idx), os.R_OK):
            pytest.skip("chmod 000 does not restrict reads here (root/non-POSIX)")
        nelly_memory._write_index_header(str(idx), "# Agent Nelly Memory Index\n\n")
    finally:
        idx.chmod(0o600)
    assert "(entries/a.md)" in idx.read_text()
