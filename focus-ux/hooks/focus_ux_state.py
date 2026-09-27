"""Per-session checkpoint-push state for focus-ux hooks (stdlib only, fail open).

State lives at ${CLAUDE_PLUGIN_DATA}/checkpoint-push/<session_id>.json with the shape
{"opted_in": bool, "pending": nonce|None, "last": {"type","id","ts"}|None,
"rule_injected": bool}. `rule_injected` tracks whether checkpoint_optin.py has already injected
the R1 additionalContext rule for this session, independent of `opted_in`, so the rule is
injected exactly once per session regardless of whether opt-in came from the prompt marker or a
persistent FOCUS_UX_CHECKPOINT_PUSH=1 env var (review New-F3/F1). Without CLAUDE_PLUGIN_DATA
there is no state: loads return defaults and saves are no-ops.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time

STATE_DIRNAME = "checkpoint-push"
LOG_NAME = "checkpoint-push.log"
HEX8 = re.compile(r"^[0-9a-f]{8}$")
# Same contract parse_ack() enforces on an incoming ack -- a state file's `last` is written by
# this codebase from an already-validated ack, but is re-validated on load too (review New-F1):
# a tampered or corrupted state file must not let an unsanitized last.id/last.type reach a
# Stop-1 reason. A field that fails its check invalidates the whole `last`, not just itself.
_LAST_ID_RE = re.compile(r"^[a-z0-9:_-]{1,48}$")
_LAST_TYPE_RE = re.compile(r"^(input|gate|done|step)$")  # _handle_stop2 never persists "none"


def defaults():
    return {"opted_in": False, "pending": None, "last": None, "rule_injected": False}


def _data_dir(env):
    return (env or {}).get("CLAUDE_PLUGIN_DATA") or None


def _safe_id(session_id):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or "")) or "unknown"


def _ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def _valid_last(last):
    if not isinstance(last, dict):
        return None
    t, i, ts = last.get("type"), last.get("id"), last.get("ts")
    if not (isinstance(t, str) and _LAST_TYPE_RE.match(t)):
        return None
    if not (isinstance(i, str) and _LAST_ID_RE.match(i)):
        return None
    if not (isinstance(ts, str) and ts):
        return None
    return {"type": t, "id": i, "ts": ts}


def state_path(session_id, env):
    data = _data_dir(env)
    if not data:
        return None
    return os.path.join(data, STATE_DIRNAME, _safe_id(session_id) + ".json")


def load_state(session_id, env):
    state = defaults()
    path = state_path(session_id, env)
    if not path:
        return state
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return state
    if not isinstance(data, dict):
        return state
    if isinstance(data.get("opted_in"), bool):
        state["opted_in"] = data["opted_in"]
    pending = data.get("pending")
    if isinstance(pending, str) and HEX8.match(pending):
        state["pending"] = pending
    last = _valid_last(data.get("last"))
    if last is not None:
        state["last"] = last
    if isinstance(data.get("rule_injected"), bool):
        state["rule_injected"] = data["rule_injected"]
    return state


def save_state(session_id, state, env):
    """Atomic write (temp file in the same dir + os.replace). Returns True on success."""
    path = state_path(session_id, env)
    if not path:
        return False
    d = os.path.dirname(path)
    if not _ensure_dir(d):
        return False
    tmp = None
    try:
        mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else None
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError):
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return False


def log(msg, env):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}\n"
    data = _data_dir(env)
    if data and _ensure_dir(data):
        try:
            with open(os.path.join(data, LOG_NAME), "a", encoding="utf-8") as fh:
                fh.write(line)
            return
        except OSError:
            pass
    sys.stderr.write("focus-ux checkpoint-push: " + line)


PRUNE_AGE_SECONDS = 7 * 86400


def prune(env, now=None):
    """Remove checkpoint-push/*.json state files older than 7 days. Never raises."""
    data = _data_dir(env)
    if not data:
        return
    cutoff = (now if now is not None else time.time()) - PRUNE_AGE_SECONDS
    try:
        entries = list(os.scandir(os.path.join(data, STATE_DIRNAME)))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.name.endswith(".json") and entry.is_file() and entry.stat().st_mtime < cutoff:
                os.unlink(entry.path)
        except OSError:
            pass
