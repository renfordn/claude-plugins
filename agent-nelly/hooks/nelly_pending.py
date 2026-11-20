#!/usr/bin/env python3
"""Pending findings queue: findings on uncommitted files, readiness, resolve (R18).

Records live at <memory dir>/pending-findings/<id>.json: {summary, paths, symbols, reason, branch,
head, hashes, id, captured}; id = SHA-256 of the record without id/captured, so duplicates
collapse. A record is "ready" when every path is tracked, its working bytes equal `git show
HEAD:<path>` and the captured hash; "changed" when a path's bytes differ from the captured hash
(or the file is gone) and it isn't ready; else "pending". Contract: INTEROP.md "Source evidence,
staleness, capture and safe writes".

All paths resolve from the git toplevel of --cwd (cwd itself outside a repo). The queue holds at most
50 records; the oldest, and records whose files vanished, are archived to resolved-findings/ with
outcome "expired".

CLI: `nelly_pending.py list [--cwd DIR]` prints JSON; `nelly_pending.py resolve <id>
verified|dismissed --evidence TEXT [--cwd DIR]`; `add --summary TEXT --paths P... [--symbols S...]
[--reason R] [--cwd DIR]` queues a finding and prints {"id"}. Exit: 0 ok, 2 usage, 3 refused (verified but not
ready, or no evidence), 4 unknown id, 5 plugin data dir unavailable. With no arguments it is a
fail-open hook stub.
"""
import argparse
import datetime
import hashlib
import json
import functools
import os
import re
import shlex
import subprocess
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "..", "scripts"))
try:
    import nelly_memory  # noqa: E402
except Exception as _exc:  # CLAUDE_PLUGIN_DATA unset: the CLI reports it cleanly (exit 5)
    nelly_memory, _IMPORT_ERROR = None, _exc
import nelly_store  # noqa: E402
import shared_slug  # noqa: E402

REASONS = ("uncommitted", "unverified", "conflict", "unavailable")
MAX_PATHS, MAX_SYMBOLS, MAX_SUMMARY = 12, 20, 500
MAX_QUEUE = 50
HINT_SECONDS = 0.5
_GIT_TIMEOUT = 2
PLUGIN_ROOT = os.path.abspath(os.path.join(_here, ".."))


def _cmd(script, *args):
    """Runnable shell command for a plugin script ("scripts/x.py", "hooks/y.py"): CLAUDE_PLUGIN_ROOT
    and CLAUDE_PLUGIN_DATA are unset in the model's own Bash, so use the absolute script path and
    pass the resolved data dir (and shared memory root when configured). Every argument is quoted."""
    data = os.path.dirname(nelly_memory.LOCAL_BASE)
    env = [f"CLAUDE_PLUGIN_DATA={shlex.quote(data)}"]
    if nelly_memory.SHARED_ROOT:
        env.append(f"CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT={shlex.quote(nelly_memory.SHARED_ROOT)}")
    parts = env + ["python3", shlex.quote(os.path.join(PLUGIN_ROOT, script))]
    return " ".join(parts + [shlex.quote(str(a)) for a in args])


def record_cmd(cwd, paths, description, body, symbols=(), slug="<kebab-slug>"):
    """Runnable `nelly_evidence.py record` command (see _cmd). cwd is the repo root the paths are
    relative to; slug defaults to a placeholder the model replaces."""
    args = ["record", "--cwd", cwd, "--slug", slug, "--type", "project", "--description", description,
            "--body", body, "--paths", *paths]
    if symbols:
        args += ["--symbols", *symbols]
    return _cmd("scripts/nelly_evidence.py", *args, "--basis", "observed")


@functools.lru_cache(maxsize=64)
def repo_root(cwd):
    """Git toplevel of cwd in cwd's own lexical spelling (so memory_dir/local_state_dir match the
    rest of the plugin), else cwd. Pending paths are relative to it."""
    return shared_slug.repo_root(cwd)


def _git(cwd, *args, binary=False):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, timeout=_GIT_TIMEOUT, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace").strip()


def _pending_dir(cwd, sub="pending-findings"):
    return os.path.join(nelly_memory.memory_dir(repo_root(cwd)), sub)


def _read_bytes(cwd, rel):
    try:
        with open(os.path.join(cwd, rel), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _record_id(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def add(cwd, summary, paths, symbols, reason):
    """Queue a finding; returns its id. Raises ValueError on limits/reason/unreadable path."""
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {REASONS}")
    if not 1 <= len(paths) <= MAX_PATHS:
        raise ValueError(f"paths must have 1..{MAX_PATHS} entries")
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"symbols must have at most {MAX_SYMBOLS} entries")
    cwd = repo_root(cwd)
    hashes = {}
    for rel in paths:
        data = _read_bytes(cwd, rel)
        if data is None:
            raise ValueError(f"cannot read {rel}")
        hashes[rel] = hashlib.sha256(data).hexdigest()
    body = {"summary": str(summary)[:MAX_SUMMARY], "paths": list(paths), "symbols": list(symbols),
            "reason": reason, "branch": _git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "",
            "head": _git(cwd, "rev-parse", "HEAD") or "", "hashes": hashes}
    pid = _record_id(body)
    path = os.path.join(_pending_dir(cwd), pid + ".json")
    if os.path.exists(path):
        return pid
    rec = dict(body, id=pid, captured=datetime.date.today().isoformat())
    root = nelly_memory.memory_dir(cwd)
    nelly_store.write_entry(root, path, json.dumps(rec, indent=2, sort_keys=True) + "\n",
                            nelly_store.MISSING)
    _prune(cwd)
    return pid


def _archive(cwd, rec, outcome, evidence=""):
    res = dict(rec, outcome=outcome, evidence=evidence, resolved=datetime.date.today().isoformat())
    nelly_store.atomic_write(os.path.join(_pending_dir(cwd, "resolved-findings"), rec["id"] + ".json"),
                             json.dumps(res, indent=2, sort_keys=True) + "\n")
    try:
        with nelly_store.lock(nelly_memory.memory_dir(repo_root(cwd))):
            os.unlink(os.path.join(_pending_dir(cwd), rec["id"] + ".json"))
    except OSError:
        pass


def _prune(cwd):
    """Expire records whose files vanished, then the oldest beyond MAX_QUEUE. Best effort."""
    try:
        keep = []
        for rec in list_pending(cwd):
            if all(os.path.exists(os.path.join(cwd, p)) for p in rec.get("paths", [])):
                keep.append(rec)
            else:
                _archive(cwd, rec, "expired", "source file no longer exists")
        for rec in keep[:max(0, len(keep) - MAX_QUEUE)]:  # list_pending is oldest first
            _archive(cwd, rec, "expired", "queue cap")
    except OSError:
        pass


def list_pending(cwd):
    d = _pending_dir(cwd)
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json") or name.startswith("."):
            continue
        try:
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("id"):
            out.append(rec)
    out.sort(key=lambda r: (r.get("captured", ""), r["id"]))
    return out


def readiness(cwd, rec):
    """'ready' | 'changed' | 'pending' (see module docstring)."""
    cwd = repo_root(cwd)
    ready, changed = True, False
    for rel, captured in (rec.get("hashes") or {}).items():
        data = _read_bytes(cwd, rel)
        if data is None or hashlib.sha256(data).hexdigest() != captured:
            changed, ready = True, False
            continue
        if _git(cwd, "show", f"HEAD:{rel}", binary=True) != data:
            ready = False
    if ready and not changed:
        return "ready"
    return "changed" if changed else "pending"


def session_hint(cwd):
    """SessionStart lines about pending findings (at most 2 ready, 2 changed)."""
    ready, changed = [], []
    deadline = time.monotonic() + HINT_SECONDS
    try:
        for rec in list_pending(cwd):
            if time.monotonic() > deadline:
                break
            if not all(os.path.exists(os.path.join(repo_root(cwd), p)) for p in rec.get("paths", [])):
                continue
            state = readiness(cwd, rec)
            if state == "ready" and len(ready) < 2:
                ready.append(rec)
            elif state == "changed" and len(changed) < 2:
                changed.append(rec)
            if len(ready) == 2 and len(changed) == 2:
                break
    except Exception:
        return []
    lines, root = [], repo_root(cwd)
    for label, outcome, recs in (("ready to verify", "verified", ready),
                                 ("changed since captured", "dismissed", changed)):
        for rec in recs:
            cmd = _cmd("hooks/nelly_pending.py", "resolve", rec["id"], outcome, "--evidence",
                       "<what you checked>", "--cwd", root)
            lines.append(f"Pending finding {rec['id'][:12]} ({label}): {str(rec.get('summary', ''))[:120]} "
                         f"[{outcome}: {cmd}]")
    return lines


def _resolve(cwd, pid, outcome, evidence):
    cwd = repo_root(cwd)
    rec = next((r for r in list_pending(cwd) if r["id"] == pid), None)
    if rec is None:
        print(f"unknown pending finding {pid}", file=sys.stderr)
        return 4
    if not evidence:
        print("--evidence is required", file=sys.stderr)
        return 3
    if evidence.startswith("<") and evidence.endswith(">"):
        print("--evidence is still the placeholder text; say what you actually checked", file=sys.stderr)
        return 3
    if outcome == "verified" and readiness(cwd, rec) != "ready":
        print("not ready: every path must be committed and unchanged since capture", file=sys.stderr)
        return 3
    _archive(cwd, rec, outcome, evidence)
    if outcome == "verified":
        summary = rec.get("summary", "")
        slug = (re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")[:40].strip("-") or "finding") \
            + "-" + pid[:6]
        print("Resolved. Record it with: " + record_cmd(
            cwd, rec.get("paths", []), " ".join(summary.split())[:200], summary,
            symbols=rec.get("symbols", []), slug=slug))
    else:
        print("Dismissed.")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if nelly_memory is None:
        print(f"agent-nelly: {_IMPORT_ERROR}", file=sys.stderr)
        return 5
    if not argv:  # hook stub: fail-open
        try:
            json.load(sys.stdin)
        except Exception:
            pass
        return 0
    ap = argparse.ArgumentParser(prog="nelly_pending.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--cwd", default=os.getcwd())
    p = sub.add_parser("resolve")
    p.add_argument("id")
    p.add_argument("outcome", choices=("verified", "dismissed"))
    p.add_argument("--evidence", default="")
    p.add_argument("--cwd", default=os.getcwd())
    p = sub.add_parser("add")
    p.add_argument("--cwd", default=os.getcwd())
    p.add_argument("--summary", required=True)
    p.add_argument("--paths", nargs="+", required=True)
    p.add_argument("--symbols", nargs="*", default=[])
    p.add_argument("--reason", default="uncommitted", choices=REASONS)
    args = ap.parse_args(argv)
    if args.cmd == "add":
        try:
            print(json.dumps({"id": add(args.cwd, args.summary, args.paths, args.symbols, args.reason)}))
        except (ValueError, OSError) as exc:
            print(f"nelly_pending: {exc}", file=sys.stderr)
            return 3
        return 0
    if args.cmd == "list":
        print(json.dumps([dict(r, readiness=readiness(args.cwd, r)) for r in list_pending(args.cwd)], indent=2))
        return 0
    return _resolve(args.cwd, args.id, args.outcome, args.evidence.strip())


if __name__ == "__main__":
    sys.exit(main())
