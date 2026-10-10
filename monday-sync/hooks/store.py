"""monday-sync storage: per-feature monday.json sidecar and the plugin's store.json. Stdlib only."""
import json
import os
import tempfile

SIDECAR = "monday.json"
BOARD_ID = 5105170755


def default_sidecar():
    return {
        "schema": 1, "item_id": None, "board_id": BOARD_ID, "project": None,
        "repo_path": None, "branch": None, "pushed_head": None, "recreated_from": None,
        "last_pushed": None, "last_seen_board": None, "synced_fields": None,
        "state_hash": None, "synced_at": None,
        "unlinked": False, "confirmed_done": False, "accepted_fields": None, "syncing_since": None,
    }


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def atomic_write_json(path, data):
    """Write JSON via a unique tmp file + os.replace. Returns False (no tmp left) if it couldn't save."""
    directory = os.path.dirname(path) or "."
    tmp = None
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError):
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False


def load_sidecar(feature_dir):
    """<feature>/monday.json merged over the schema-1 default; the default when absent or invalid."""
    sc = default_sidecar()
    data = _read_json(os.path.join(feature_dir, SIDECAR))
    if data:
        sc.update(data)
    return sc


def save_sidecar(feature_dir, data):
    return atomic_write_json(os.path.join(feature_dir, SIDECAR), data)


# -- plugin store: ${CLAUDE_PLUGIN_DATA}/store.json --------------------------------------------------

STORE = "store.json"


def store_path(data_dir=None):
    """${CLAUDE_PLUGIN_DATA}/store.json (or <data_dir>/store.json); None when neither is set."""
    base = data_dir or os.environ.get("CLAUDE_PLUGIN_DATA")
    return os.path.join(base, STORE) if base else None


def _default_store():
    return {"pending": [], "linked": {}, "dismissed_candidates": []}


def load_store(data_dir=None):
    st = _default_store()
    path = store_path(data_dir)
    data = _read_json(path) if path else None
    if data:
        for key, kind in (("pending", list), ("linked", dict), ("dismissed_candidates", list)):
            if isinstance(data.get(key), kind):
                st[key] = data[key]
    return st


def _save_store(st, data_dir=None):
    path = store_path(data_dir)
    return atomic_write_json(path, st) if path else False


def _key(feature_dir):
    return os.path.realpath(feature_dir)


def add_pending(feature_dir, data_dir=None):
    """Flag a feature dir (realpath) as needing board sync. False when the store can't be written."""
    if not store_path(data_dir):
        return False
    st = load_store(data_dir)
    key = _key(feature_dir)
    if key in st["pending"]:
        return True
    st["pending"].append(key)
    return _save_store(st, data_dir)


def remove_pending(feature_dir, data_dir=None):
    st = load_store(data_dir)
    key = _key(feature_dir)
    if key not in st["pending"]:
        return True
    st["pending"] = [p for p in st["pending"] if p != key]
    return _save_store(st, data_dir)


def list_pending(data_dir=None):
    """Pending feature dirs that still exist; entries for deleted dirs are dropped from the store."""
    st = load_store(data_dir)
    alive = [p for p in st["pending"] if os.path.isdir(p)]
    if alive != st["pending"]:
        st["pending"] = alive
        _save_store(st, data_dir)
    return alive


def set_linked(feature_dir, item_id, data_dir=None):
    """Link a feature to a board item; a falsy item_id removes the link."""
    st = load_store(data_dir)
    if item_id:
        st["linked"][_key(feature_dir)] = str(item_id)
    else:
        st["linked"].pop(_key(feature_dir), None)
    return _save_store(st, data_dir)


def dismiss(item_id, data_dir=None):
    st = load_store(data_dir)
    if str(item_id) not in st["dismissed_candidates"]:
        st["dismissed_candidates"].append(str(item_id))
    return _save_store(st, data_dir)


# -- discovering features outside the Edit/Write hook --------------------------------------------
# workflow-state.md is often changed through Bash (heredocs, `printf >>`, `python3 -`), which the
# PostToolUse Edit/Write matcher never sees. These helpers find features by slug or by drift.

SHARED_ROOT_ENV = "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"


def spec_dirs(data_dir=None):
    """Every known <...>/spec dir: <shared root>/sdd-memory/*/spec plus those of stored features."""
    found = []
    root = (os.environ.get(SHARED_ROOT_ENV) or "").strip()
    if root and os.path.isabs(root):
        base = os.path.join(root, "sdd-memory")
        try:
            names = sorted(os.listdir(base))
        except OSError:
            names = []
        found += [os.path.join(base, n, "spec") for n in names]
    st = load_store(data_dir)
    found += [os.path.dirname(p) for p in list(st["linked"]) + st["pending"]]
    seen, out = set(), []
    for d in found:
        real = os.path.realpath(d)
        if real not in seen and os.path.isdir(real):
            seen.add(real)
            out.append(real)
    return out


def feature_dirs_for_slug(slug, data_dir=None):
    return [os.path.join(s, slug) for s in spec_dirs(data_dir)
            if os.path.isfile(os.path.join(s, slug, "workflow-state.md"))]


def _hash_state(feature_dir):
    """Same 16-hex sha256 as planner.state_hash over workflow-state.md; None when unreadable."""
    import hashlib
    try:
        with open(os.path.join(feature_dir, "workflow-state.md"), "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def drifted_features(data_dir=None):
    """Linked features (sidecar has item_id, not unlinked) whose state changed since last sync."""
    out = []
    for spec in spec_dirs(data_dir):
        try:
            names = sorted(os.listdir(spec))
        except OSError:
            continue
        for name in names:
            d = os.path.join(spec, name)
            if not os.path.isfile(os.path.join(d, SIDECAR)):
                continue
            sc = load_sidecar(d)
            if not sc.get("item_id") or sc.get("unlinked"):
                continue
            current = _hash_state(d)
            if (current and current != sc.get("state_hash")) or _progress_newer(d, sc.get("synced_at")):
                out.append(d)
    return out


def _progress_newer(feature_dir, synced_at):
    """True when agent-isdd's impl-progress.json (one write per agent-TDD/code-reviewer report)
    changed after the last board sync."""
    import datetime
    try:
        mtime = os.path.getmtime(os.path.join(feature_dir, "impl-progress.json"))
    except OSError:
        return False
    if not synced_at:
        return True
    try:
        synced = datetime.datetime.fromisoformat(synced_at.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return True
    return mtime > synced
