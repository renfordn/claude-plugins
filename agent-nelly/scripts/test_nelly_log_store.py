"""Release 5 slice 1D review fixes: append-only logs and merge edge cases go through nelly_store.

- append_log is a locked read-modify-write: concurrent appenders through every writer
  (auto-extract promotion log, cleanup log/history, weekly consolidation log) keep every block.
- _ensure_parent_store creates a header-only MEMORY.md without a fake conflict sidecar.
- merge_worktree_store keeps same-named conflict sidecars from both stores and never carries a
  worktree .nelly.lock into the parent.
"""
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.join(SCRIPTS_DIR, "..", "hooks")
sys.path.insert(0, SCRIPTS_DIR)
import nelly_cleanup  # noqa: E402
import nelly_store  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _env(tmp_path):
    full = dict(os.environ)
    full.update({
        "HOME": str(tmp_path / "home"),
        "CLAUDE_CONFIG_DIR": str(tmp_path / "home" / ".claude"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "home" / ".claude" / "plugins" / "data" / "agent-nelly"),
    })
    for k in ("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", "NELLY_SHARED_MEMORY_ROOT"):
        full.pop(k, None)
    return full


def test_append_log_writes_header_once_and_keeps_blocks(tmp_path):
    root = str(tmp_path / "store")
    log = os.path.join(root, "LOG.md")
    nelly_store.append_log(root, log, "one\n", header="# H\n")
    nelly_store.append_log(root, log, "two\n", header="# H\n")
    assert _read(log) == "# H\none\ntwo\n"


_LOG_WRITERS = """
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import nelly_auto_extract, nelly_cleanup, nelly_weekly_consolidate
cwd, store, kind, worker, count = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
for i in range(count):
    tag = f"{kind}-{worker}-{i}"
    if kind == "auto":
        nelly_auto_extract._append_promotion_log(cwd, tag, 3)
    elif kind == "cleanup":
        nelly_cleanup._log_action(store, "act", [f"Entry: {tag}"])
    else:
        nelly_weekly_consolidate._append_consolidation_log(store, [({"slug": tag}, 40)])
""" % (HOOKS_DIR, SCRIPTS_DIR)


def test_concurrent_log_appends_through_every_writer_keep_every_block(tmp_path):
    env = _env(tmp_path)
    cwd = str(tmp_path / "proj")
    os.makedirs(cwd)
    store = subprocess.run(
        [sys.executable, "nelly_memory.py", "--path", cwd], cwd=HOOKS_DIR, env=env,
        capture_output=True, text=True, check=True).stdout.strip()
    kinds, workers, count = ("auto", "cleanup", "weekly"), 3, 8
    procs = [subprocess.Popen([sys.executable, "-c", _LOG_WRITERS, cwd, store, k, str(w), str(count)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
             for k in kinds for w in range(workers)]
    for p in procs:
        _so, se = p.communicate(timeout=180)
        assert p.returncode == 0, se
    text = _read(os.path.join(store, "CONSOLIDATION-LOG.md"))
    assert text.count("# Consolidation Log") == 1
    for k in kinds:
        for w in range(workers):
            for i in range(count):
                assert text.count(f"{k}-{w}-{i}\n") == 1, f"lost or duplicated block {k}-{w}-{i}"


def test_cleanup_session_history_append_is_locked_log(tmp_path):
    store = str(tmp_path / "s")
    path = os.path.join(store, "SESSION-HISTORY.md")
    nelly_cleanup._append(path, "a\n", nelly_cleanup.SESSION_HISTORY_HEADER)
    nelly_cleanup._append(path, "b\n", nelly_cleanup.SESSION_HISTORY_HEADER)
    assert _read(path) == nelly_cleanup.SESSION_HISTORY_HEADER + "a\nb\n"


def test_one_consolidation_log_header_constant():
    import nelly_weekly_consolidate
    sys.path.insert(0, HOOKS_DIR)
    import nelly_auto_extract
    assert nelly_cleanup.CONSOLIDATION_LOG_HEADER is nelly_store.CONSOLIDATION_LOG_HEADER
    assert nelly_weekly_consolidate.CONSOLIDATION_LOG_HEADER is nelly_store.CONSOLIDATION_LOG_HEADER
    assert nelly_auto_extract._CONSOLIDATION_LOG_HEADER is nelly_store.CONSOLIDATION_LOG_HEADER


def test_ensure_parent_store_header_leaves_no_conflict_sidecar(tmp_path):
    parent = str(tmp_path / "mem" / "proj")
    nelly_cleanup._ensure_parent_store(parent, "/r/.claude/worktrees/wt1")
    assert _read(os.path.join(parent, "MEMORY.md")).startswith("# Agent Nelly Memory Index")
    assert not os.path.exists(os.path.join(parent, "conflicts"))


def test_merge_keeps_same_named_conflict_sidecars_and_drops_worktree_lock(tmp_path):
    base = str(tmp_path / "mem")
    parent = os.path.join(base, "proj")
    store = os.path.join(base, "proj-claude-worktrees-wt1")
    name = "entries--x.20260101T000000.1.md"
    _write(os.path.join(parent, "MEMORY.md"), "# Agent Nelly Memory Index\n\nProject: /p\n\n")
    _write(os.path.join(parent, "conflicts", name), "parent sidecar\n")
    _write(os.path.join(store, "MEMORY.md"), "# Agent Nelly Memory Index\n\n")
    _write(os.path.join(store, "conflicts", name), "worktree sidecar\n")
    _write(os.path.join(store, ".nelly.lock"), "worktree-lock-marker")
    nelly_cleanup.merge_worktree_store(store, "proj", "wt1", base=base)
    kept = sorted(os.listdir(os.path.join(parent, "conflicts")))
    assert len(kept) == 2 and name in kept, kept
    assert _read(os.path.join(parent, "conflicts", name)) == "parent sidecar\n"
    other = [k for k in kept if k != name][0]
    assert _read(os.path.join(parent, "conflicts", other)) == "worktree sidecar\n"
    # the parent may own its own (empty) lock file, but the worktree's is never carried over
    assert [n for n in os.listdir(parent) if n.startswith(".nelly")] in ([], [".nelly.lock"])
    lock = os.path.join(parent, ".nelly.lock")
    assert not os.path.exists(lock) or _read(lock) == ""
