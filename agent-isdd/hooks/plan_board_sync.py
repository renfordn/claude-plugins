#!/usr/bin/env python3
"""Plan Board drift hardening: verify the board against local state, resync it in one batch, and
prune orphaned sync entries after user confirmation.

Pure helpers first; the CLI at the bottom wires them to a project's memory dir. Stdlib only.
Hooks and this script never call MCP tools: they print what the model should write.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_board  # noqa: E402


def local_docs(memory_dir, project):
    """{id: doc} for every feature with a workflow-state.md under <memory_dir>/spec."""
    spec = os.path.join(memory_dir, "spec")
    docs = {}
    try:
        names = sorted(os.listdir(spec))
    except OSError:
        return docs
    for name in names:
        path = os.path.join(spec, name, "workflow-state.md")
        doc = plan_board.build_doc(path, project=project) if os.path.isfile(path) else None
        if doc:
            docs[doc["id"]] = doc
    return docs


def build_batch(memory_dir, project, board_hashes, versions=None):
    """One `ArtifactData batch` payload (`writes` is passed to the tool as-is): a `set` write for every
    record the board lacks or holds with a different hash. `board_hashes` is the board's id->contentHash
    map (None = judge by the sync file); `versions` is its id->version map, which the tool requires as
    `if_version` on any write to an existing record. Empty when the project has no board or sync is off."""
    versions = versions or {}
    batch = {"writes": [], "ids": []}
    if not (plan_board.board_url(memory_dir) and plan_board.sync_enabled(memory_dir)):
        return batch
    synced = plan_board._read_sync(memory_dir)
    for doc_id, doc in local_docs(memory_dir, project).items():
        have = synced.get(doc_id) if board_hashes is None else board_hashes.get(doc_id)
        if have != doc["contentHash"]:
            write = {"op": "set", "collection": plan_board.COLLECTION, "doc_id": doc_id, "data": doc}
            if versions.get(doc_id):
                write["if_version"] = versions[doc_id]
            batch["writes"].append(write)
            batch["ids"].append(doc_id)
    return batch


def mark_success(memory_dir, project, ids):
    """Record the current hash for each successfully written id; failed ones stay stale."""
    docs = local_docs(memory_dir, project)
    return [i for i in ids if i in docs and plan_board.mark_synced(memory_dir, docs[i])]


def diff_records(local, board):
    """Compare id->hash maps. Returns sorted id lists: records missing from the board, records whose
    hash differs from local state, and board records with no local feature (orphans)."""
    return {
        "missing": sorted(i for i in local if i not in board),
        "mismatched": sorted(i for i in local if i in board and board[i] != local[i]),
        "orphaned": sorted(i for i in board if i not in local),
    }


def plan_prune(orphans):
    """What pruning would remove, plus the question to put to the user. Deletes nothing."""
    ids = sorted(set(orphans))
    listing = "\n".join(f"- {i}" for i in ids)
    return {"candidates": ids,
            "confirmation": f"These Plan Board records have no matching feature and would be removed:\n{listing}\n"
                            f"Remove them? Nothing is deleted until you say yes."}


def _live(memory_dir, doc_id):
    try:
        names = os.listdir(os.path.join(memory_dir, "spec"))
    except OSError:
        return False
    return any(doc_id.endswith("--" + plan_board._safe(n)) for n in names)


def apply_prune(sync_path, ids, confirmed, versions=None):
    """Remove orphan entries from the sync file, only when `confirmed is True`.

    Ids that still have a feature dir are skipped. A missing or corrupt sync file is left as it is.
    Board-side deletes are returned as instructions for the caller, never performed here.
    """
    result = {"removed": [], "board_instructions": []}
    if confirmed is not True:
        return result
    try:
        with open(sync_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return result
    if not isinstance(data, dict):
        return result
    memory_dir = os.path.dirname(os.path.abspath(sync_path))
    for doc_id in ids:
        if doc_id in data and not _live(memory_dir, doc_id):
            del data[doc_id]
            result["removed"].append(doc_id)
            write = {"op": "delete", "collection": plan_board.COLLECTION, "doc_id": doc_id}
            if (versions or {}).get(doc_id):
                write["if_version"] = versions[doc_id]
            result["board_instructions"].append(write)
    if result["removed"]:
        tmp = sync_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1, sort_keys=True)
            os.replace(tmp, sync_path)
        except OSError:
            return {"removed": [], "board_instructions": []}
    return result


# -- lastVerified (kept in plan-board-sync.json beside the id->hash entries) --------------------

def last_verified(memory_dir):
    """When the board was last verified (aware UTC datetime), or None."""
    raw = plan_board._read_sync(memory_dir).get("lastVerified")
    try:
        when = datetime.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def stamp_verified(memory_dir, now=None):
    data = plan_board._read_sync(memory_dir)
    data["lastVerified"] = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds")
    path = plan_board._sync_path(memory_dir)
    try:
        os.makedirs(memory_dir, exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.replace(path + ".tmp", path)
        return True
    except OSError:
        return False


# -- CLI ---------------------------------------------------------------------------------------

def _board_hashes(path, project):
    """id->contentHash for this project's records from a JSON dump of the board's `plans` list."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = [{"id": k, "contentHash": v} for k, v in data.items()]
    prefix = plan_board._safe(project) + "--"
    return {d["id"]: d.get("contentHash", "") for d in data
            if isinstance(d, dict) and str(d.get("id", "")).startswith(prefix)}


def _board_versions(path):
    """id->version from a board dump whose entries carry `version` (as `ArtifactData list` shows it)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        return {}
    return {d["id"]: d["version"] for d in data if isinstance(d, dict) and d.get("id") and d.get("version")}


def _arg(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


def _ids(argv):
    """Positional args after the command (skipping `--flag value` pairs)."""
    out, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a in ("--memory-dir", "--project", "--cwd", "--board-json", "--base"):
            skip = True
        elif not a.startswith("--"):
            out.append(a)
    return out


# -- central run: every project under sdd-memory/ on the shared board --------------------------

def _label(memory_dir):
    """The project label used in this project's record ids, from its sync file (most common id
    prefix), or None when it has never synced (run once from that project to label it)."""
    counts = {}
    for key in plan_board._read_sync(memory_dir):
        if "--" in key:
            prefix = key.split("--", 1)[0]
            counts[prefix] = counts.get(prefix, 0) + 1
    return max(counts, key=counts.get) if counts else None


def central_projects(base):
    """([(label, memory_dir)], [skipped dir names]) for every project dir under `base` with a spec/
    folder whose effective board is the shared one (base/PLAN-BOARD.md) and sync is on."""
    shared = plan_board.board_url(os.path.join(base, "_"))
    found, skipped = [], []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return found, skipped
    for name in names:
        mem = os.path.join(base, name)
        if not os.path.isdir(os.path.join(mem, "spec")):
            continue
        if not shared or plan_board.board_url(mem) != shared or not plan_board.sync_enabled(mem):
            continue
        label = _label(mem)
        (found.append((label, mem)) if label else skipped.append(name))
    return found, skipped


def _dump(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = [{"id": k, "contentHash": v} for k, v in data.items()]
    return [d for d in data if isinstance(d, dict) and d.get("id")]


def main_all(argv):
    """`all <verify|resync|prune|mark> [--board-json FILE] [--confirm] [ids] [--base DIR]`."""
    cmd = argv[0] if argv else ""
    if cmd not in ("verify", "resync", "prune", "mark"):
        print("usage: plan_board_sync.py all verify|resync|prune|mark [--board-json FILE] "
              "[--confirm] [ids...] [--base DIR]", file=sys.stderr)
        return 2
    base = _arg(argv, "--base")
    if not base:
        import sdd_memory
        base = sdd_memory.BASE
    projects, skipped = central_projects(base)
    board = []
    if _arg(argv, "--board-json"):
        try:
            board = _dump(_arg(argv, "--board-json"))
        except (OSError, ValueError) as exc:
            print(f"plan_board_sync: cannot read board dump: {exc}", file=sys.stderr)
            return 2
    elif cmd != "mark":
        print("plan_board_sync: all needs --board-json FILE (the board's `plans` list)", file=sys.stderr)
        return 2
    hashes = {d["id"]: d.get("contentHash", "") for d in board}
    versions = {d["id"]: d["version"] for d in board if d.get("version")}
    local_ids = set()
    per = {}
    for label, mem in projects:
        prefix = plan_board._safe(label) + "--"
        local = {i: d["contentHash"] for i, d in local_docs(mem, label).items()}
        local_ids |= set(local)
        mine = {i: h for i, h in hashes.items() if i.startswith(prefix)}
        per[label] = (mem, local, mine)
    # A card is an orphan only when no feature folder anywhere under base has its slug, so cards of
    # skipped (never-synced) or sync-off projects are never offered for deletion.
    all_slugs = set()
    try:
        for name in os.listdir(base):
            try:
                all_slugs |= {plan_board._safe(f) for f in os.listdir(os.path.join(base, name, "spec"))}
            except OSError:
                pass
    except OSError:
        pass
    orphans = sorted(i for i in hashes if i not in local_ids
                     and (i.split("--", 1)[1] if "--" in i else i) not in all_slugs)
    if cmd == "verify":
        out = {"projects": {}, "orphaned": orphans, "skipped": skipped}
        for label, (mem, local, mine) in per.items():
            d = diff_records(local, mine)
            out["projects"][label] = {"missing": d["missing"], "mismatched": d["mismatched"]}
            stamp_verified(mem)
        print(json.dumps(out, indent=1))
    elif cmd == "resync":
        batch = {"writes": [], "ids": [], "skipped": skipped}
        for label, (mem, _local, mine) in per.items():
            b = build_batch(mem, label, mine, versions)
            batch["writes"] += b["writes"]
            batch["ids"] += b["ids"]
        print(json.dumps(batch, indent=1))
    elif cmd == "mark":
        done = []
        for i in _ids(argv):
            for label, (mem, _l, _m) in per.items():
                if i.startswith(plan_board._safe(label) + "--"):
                    done += mark_success(mem, label, [i])
        print("\n".join(done))
    elif "--confirm" in argv:
        out = {"removed": [], "board_instructions": []}
        for mem, _l, _m in per.values():
            r = apply_prune(plan_board._sync_path(mem), orphans, True, versions)
            out["removed"] += r["removed"]
        out["board_instructions"] = [dict({"op": "delete", "collection": plan_board.COLLECTION, "doc_id": i},
                                          **({"if_version": versions[i]} if versions.get(i) else {}))
                                     for i in orphans]
        print(json.dumps(out, indent=1))
    elif orphans:
        print(plan_prune(orphans)["confirmation"])
    return 0


def main(argv):
    if argv and argv[0] == "all":
        return main_all(argv[1:])
    cmd = argv[0] if argv else ""
    if cmd not in ("verify", "resync", "prune", "mark"):
        print("usage: plan_board_sync.py verify --board-json FILE | resync [--board-json FILE] | "
              "prune [--board-json FILE] [--confirm] | mark <id>...  "
              "[--memory-dir DIR] [--project NAME] [--cwd DIR]", file=sys.stderr)
        return 2
    cwd = _arg(argv, "--cwd") or os.getcwd()
    memory_dir = _arg(argv, "--memory-dir")
    if not memory_dir:
        os.chdir(cwd)
        memory_dir = plan_board._memory_dir()
    project = _arg(argv, "--project") or plan_board.repo_label(cwd)
    if not (plan_board.board_url(memory_dir) and plan_board.sync_enabled(memory_dir)):
        return 0  # no board, or sync off: nothing to do, nothing to say
    board, versions = None, {}
    if _arg(argv, "--board-json"):
        try:
            board = _board_hashes(_arg(argv, "--board-json"), project)
            versions = _board_versions(_arg(argv, "--board-json"))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"plan_board_sync: cannot read board dump: {exc}", file=sys.stderr)
            return 2
    elif cmd == "verify":
        print("plan_board_sync: verify needs --board-json FILE (the board's `plans` list)", file=sys.stderr)
        return 2
    local = {i: d["contentHash"] for i, d in local_docs(memory_dir, project).items()}
    if cmd == "verify":
        print(json.dumps(diff_records(local, board), indent=1))
        stamp_verified(memory_dir)
    elif cmd == "resync":
        print(json.dumps(build_batch(memory_dir, project, board, versions), indent=1))
    elif cmd == "mark":
        print("\n".join(mark_success(memory_dir, project, _ids(argv))))
    else:
        known = {i for i in plan_board._read_sync(memory_dir) if "--" in i}
        orphans = sorted({i for i in known if i not in local} | set(diff_records(local, board or {})["orphaned"]))
        plan = plan_prune(orphans)
        if "--confirm" in argv:
            print(json.dumps(apply_prune(plan_board._sync_path(memory_dir), orphans, True, versions), indent=1))
        elif orphans:
            print(plan["confirmation"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
