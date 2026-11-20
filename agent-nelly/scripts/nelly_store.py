#!/usr/bin/env python3
"""Shared store primitives: advisory lock, atomic writes, compare-and-swap entry writes,
locked read-modify-write, index upsert, MEMORY.md line append. All writes run under
lock(root) (an flock on <root>/.nelly.lock; a no-op where fcntl is unavailable)."""
import contextlib
import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None

MISSING = "missing"
LOCK_NAME = ".nelly.lock"

# The one CONSOLIDATION-LOG.md header, shared by every writer (auto-extract promotions, cleanup,
# weekly consolidation).
CONSOLIDATION_LOG_HEADER = (
    "# Consolidation Log\n\n"
    "Append-only history of consolidation-related actions taken against this "
    "project's memory store, including auto-promotions by the auto-extract hooks and "
    "archives/merges by the scheduled consolidation scripts. Never edit or remove a prior "
    "entry -- archived/superseded files remain fully readable, not deleted.\n\n"
    "## Log\n"
)


class StoreLocked(TimeoutError):  # an OSError, so best-effort `except OSError` callers cope
    """The store lock could not be acquired within the timeout."""


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return MISSING


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


_tls = threading.local()


def _held():
    if not hasattr(_tls, "held"):
        _tls.held = {}
    return _tls.held


@contextlib.contextmanager
def lock(root, timeout=2.0):
    """Cross-process advisory lock, reentrant per thread (keyed by realpath(root)).
    Only flock contention (EWOULDBLOCK/EAGAIN) is retried until timeout; any other flock
    error (ENOTSUP/ENOLCK on network filesystems) degrades to the unlocked no-op path."""
    if fcntl is None:
        yield
        return
    os.makedirs(root, exist_ok=True)
    key = os.path.realpath(root)
    held = _held()
    if key in held:
        held[key] += 1
        try:
            yield
        finally:
            held[key] -= 1
            if not held[key]:
                del held[key]
        return
    lockpath = os.path.join(root, LOCK_NAME)
    deadline = time.monotonic() + timeout
    fd = None
    while fd is None:
        cand = os.open(lockpath, os.O_RDWR | os.O_CREAT, 0o666)
        try:
            while True:
                try:
                    fcntl.flock(cand, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise StoreLocked(f"store lock held: {root}")
                    time.sleep(0.02)
                except OSError:
                    os.close(cand)
                    cand = None
                    break
            if cand is None:  # locking unsupported here: proceed unlocked
                yield
                return
            try:  # lock file replaced/removed while we waited: our lock guards an orphan inode
                same = os.fstat(cand).st_ino == os.stat(lockpath).st_ino
            except OSError:
                same = False
            if same:
                fd, cand = cand, None
            elif time.monotonic() >= deadline:
                raise StoreLocked(f"store lock file kept changing: {root}")
        finally:
            if cand is not None:
                os.close(cand)
    held[key] = 1
    try:
        yield
    finally:
        del held[key]
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write(path, text):
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            mode = os.stat(path).st_mode & 0o7777
        except OSError:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _sidecar_stem(root, path):
    rel = os.path.relpath(path, root)
    if rel.startswith("..") or os.path.isabs(rel):
        rel = os.path.basename(path)
    if rel.endswith(".md"):
        rel = rel[:-3]
    return rel.replace(os.sep, "--")


def _write_sidecar(root, stem, text, ext=".md"):
    """Create root/conflicts/<stem>.<UTC ts>.<pid>[-N]<ext> exclusively (O_EXCL), so two
    writers can never claim the same name, with or without the store lock."""
    d = os.path.join(root, "conflicts")
    os.makedirs(d, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    base = f"{stem}.{stamp}.{os.getpid()}"
    n = 1
    while True:
        cand = os.path.join(d, base + ("" if n == 1 else f"-{n}") + ext)
        try:
            fd = os.open(cand, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            n += 1
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        return cand


def _write_entry_locked(root, path, text, expected_sha):
    current = file_sha(path)
    if current == text_sha(text):
        return {"status": "unchanged", "path": path}
    if expected_sha is None or expected_sha == current:
        atomic_write(path, text)
        return {"status": "written", "path": path}
    return {"status": "conflict", "path": _write_sidecar(root, _sidecar_stem(root, path), text)}


def write_entry(root, path, text, expected_sha):
    try:
        with lock(root):
            return _write_entry_locked(root, path, text, expected_sha)
    except StoreLocked:
        # Never drop the caller's text: park it as a conflict sidecar, entry untouched.
        return {"status": "conflict", "path": _write_sidecar(root, _sidecar_stem(root, path), text)}


def update_entry(root, path, fn, timeout=2.0):
    """fn(old_text|None) -> new text, or None for no change. Returns "written"|"unchanged".
    `timeout` is the lock wait; StoreLocked propagates when it expires."""
    with lock(root, timeout):
        old = _read_text(path)
        new = fn(old)
        if new is None or new == old:
            return "unchanged"
        atomic_write(path, new)
        return "written"


def append_log(root, path, block, header=None, timeout=2.0):
    """Append `block` to an append-only log under the store lock (header first when the file is
    new). A locked read-modify-write, so it never loses a concurrent append."""
    def fn(old):
        base = old if old is not None else (header or "")
        return base + block
    return update_entry(root, path, fn, timeout)


def park_sidecar(root, stem, text, ext=".md"):
    """Keep `text` as root/conflicts/<stem>.<ts>.<pid>[-N]<ext>; returns the path."""
    return _write_sidecar(root, stem, text, ext=ext)


def serialize_index(records):
    """The one nelly-index.json serializer (sorted by slug, indent=2, trailing newline)."""
    return json.dumps(sorted(records, key=lambda r: r["slug"]), indent=2) + "\n"


def upsert_index(root, fn, name="nelly-index.json"):
    index_path = os.path.join(root, name)
    with lock(root):
        records = []
        raw = _read_text(index_path)
        if raw is not None:
            try:
                records = json.loads(raw)
                if not isinstance(records, list):
                    raise ValueError("index is not a list")
            except ValueError:  # includes JSONDecodeError: keep the unreadable file, start empty
                _write_sidecar(root, os.path.splitext(name)[0], raw, ext=os.path.splitext(name)[1])
                records = []
        result = fn(records)
        records = records if result is None else result
        atomic_write(index_path, serialize_index(records))
        return sorted(records, key=lambda r: r["slug"])


def append_memory_line(root, line):
    mem = os.path.join(root, "MEMORY.md")
    with lock(root):
        old = _read_text(mem) or ""
        if line in old.splitlines():
            return False
        if old and not old.endswith("\n"):
            old += "\n"
        atomic_write(mem, old + line + "\n")
        return True
