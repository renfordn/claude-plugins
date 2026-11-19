#!/usr/bin/env python3
"""Shared state utilities for the agent-tdd plugin.

Owns:
  - TDD memory directory derivation (<memory root>/agent-tdd-state/<project-slug>/; the shared_memory_root when set, else ${CLAUDE_PLUGIN_DATA})
  - tdd-progress.json read/write (slice tracking)

Intentionally self-contained: slug algorithm is copied verbatim from
agent-isdd/hooks/sdd_memory.py rather than imported, to avoid a cross-plugin
dependency. The two modules must stay in sync if the slug algorithm ever changes.
"""
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None
import json
import os
import re
import subprocess
import sys
import tempfile

# path_resolution.py lives alongside this file (a per-plugin copy -- see its own
# docstring for why it isn't imported from a monorepo-relative shared/ directory).
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from path_resolution import get_memory_root, get_legacy_subdir_path

# The shared memory root when configured (same store as agent-nelly/agent-isdd, so slices and
# review gates are visible across identities and machines), else ${CLAUDE_PLUGIN_DATA}.
BASE = get_legacy_subdir_path(get_memory_root("agent-tdd"), "agent-tdd-state")


def _repo_root(cwd):
    """The git toplevel containing cwd, or cwd itself outside a repo (or if git is missing).

    git reports the toplevel as a realpath, so prefer the lexical ancestor of cwd that resolves
    to it: that keeps cwd's spelling (e.g. /tmp vs /private/tmp on macOS) and so the slug. When
    cwd was reached through a symlink from outside the repo, no ancestor matches and git's
    toplevel is used. A linked worktree is its own toplevel, so it keeps its own slug.
    """
    absp = os.path.abspath(cwd)
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        proc = subprocess.run(["git", "-C", absp, "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=5, env=env)
    except (OSError, subprocess.SubprocessError):
        return absp
    top = proc.stdout.strip()
    if proc.returncode != 0 or not top:
        return absp
    real_top = os.path.realpath(top)
    d = absp
    while True:
        if os.path.realpath(d) == real_top:
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return top
        d = parent


def project_slug(cwd):
    """Deterministic collision-resistant slug from the project path (git toplevel of cwd).
    Algorithm is identical to agent-isdd/hooks/sdd_memory.py — kept in sync manually.
    """
    absp = _repo_root(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def tdd_memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def progress_path(cwd):
    """tdd-progress.json under the main-checkout state dir (shared by linked worktrees)."""
    return os.path.join(tdd_memory_dir(state_cwd(cwd)), "tdd-progress.json")


def read_tdd_progress(cwd):
    """Read tdd-progress.json. Returns {"slices": []} on missing or malformed file."""
    data = _read_progress_file(progress_path(cwd))
    # Read-only migration fallback: state written before per-main-checkout sharing lives under
    # the worktree's own slug. Merge its slices (never deleted); shared-state ids win.
    legacy_path = os.path.join(tdd_memory_dir(cwd), "tdd-progress.json")
    if legacy_path != progress_path(cwd):
        seen = {s.get("id") for s in data["slices"] if isinstance(s, dict)}
        for s in _read_progress_file(legacy_path)["slices"]:
            if not isinstance(s, dict) or s.get("id") not in seen:
                data["slices"].append(s)
    return data


def _read_progress_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("slices"), list):
            return {"slices": []}
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return {"slices": []}


def write_tdd_progress(cwd, data):
    """Write tdd-progress.json, creating parent dirs as needed."""
    update_json(progress_path(cwd), lambda _old: data)


TAIL_BYTES = 32768


def extract_last_assistant_text(transcript_path):
    """Tail-read transcript JSONL and return the last assistant message text.
    Returns (text, truncated) where truncated=True means the file was larger than
    TAIL_BYTES so the head of the file was not read.
    """
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - TAIL_BYTES)
            fh.seek(start)
            raw = fh.read()
    except OSError:
        return "", False

    truncated = start > 0
    lines = raw.split(b"\n")
    if truncated:
        lines = lines[1:]  # drop potentially partial first line

    blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else None
        role = ev.get("type") or (msg.get("role") if msg else "")
        is_assistant = role == "assistant" or (msg and msg.get("role") == "assistant")
        if not is_assistant:
            continue
        content = msg.get("content") if msg else ev.get("content")
        if isinstance(content, str):
            blocks.append(content)
        elif isinstance(content, list):
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            joined = "\n".join(p for p in parts if p)
            if joined:
                blocks.append(joined)

    return (blocks[-1].strip() if blocks else ""), truncated


def update_json(path, fn):
    """Locked read-modify-write of a JSON file. Missing/corrupt -> {}. Returns the new data."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    lock = None
    try:
        if fcntl is not None:
            lock = open(path + ".lock", "a")
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        try:
            mode = os.stat(path).st_mode & 0o777
        except OSError:
            mode = 0o644
        data = fn(data)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return data
    finally:
        if lock is not None:
            lock.close()


def state_cwd(cwd):
    """Main worktree toplevel for cwd (so linked worktrees share state); cwd on any failure."""
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        proc = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                              cwd=cwd, capture_output=True, text=True, timeout=5, env=env)
        common = proc.stdout.strip().rstrip("/")
        if proc.returncode == 0 and os.path.basename(common) == ".git":
            return os.path.dirname(common)
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd

