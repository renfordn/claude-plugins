#!/usr/bin/env python3
"""Plan Board helpers: turn a feature's workflow-state.md into one record for a living Artifact page.

The Plan Board is one Artifact page (skills/workflow-manager/assets/plan-board.html) that reads a
`plans` collection from its own `db`. Each SDD feature is one small JSON document. This module
builds that document from workflow-state.md so the model never hand-writes it, and tracks which
documents have been written so a stale board can be noticed.

Commands:
    plan_board.py doc <workflow-state.md> [--project NAME] [--out FILE]   # print the record as JSON, or write it to FILE and print its id
    plan_board.py page <out.html>                            # write the board page (publish once)
    plan_board.py stale [--cwd DIR]                          # features whose record is out of date
    plan_board.py mark-synced <workflow-state.md> [--project NAME]   # after writing the record

Stdlib only. Importing this module needs no CLAUDE_PLUGIN_DATA; only the functions that read the
project's memory directory do.
"""
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feature_paths  # noqa: E402
import plan_brief  # noqa: E402

SCHEMA = 2
PHASES = ("Requirements", "Design", "Tasks", "Implementation")
GOAL_MAX = 300
NEXT_MAX = 300
PAUSE_MAX = 240
TITLE_MAX = 120
BOARD_FILE = "PLAN-BOARD.md"
SYNC_FILE = "plan-board-sync.json"
COLLECTION = "plans"
PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "skills", "workflow-manager", "assets", "plan-board.html")

_FIELD = re.compile(r"^\s*[-*]\s*([A-Za-z][A-Za-z /]+?):\s*(.*\S)?\s*$")
_CONTINUATION = re.compile(r"^\s{2,}(\S.*)$")
_PATH_UNSAFE = re.compile(r"[^A-Za-z0-9_.~:@+-]+")


def parse_fields(text):
    """`- Field: value` lines of a workflow-state.md as {lowercased field: value}.

    A value can continue on following indented lines (workflow-state.md wraps long Goal and Next
    Action text); those are joined with single spaces. The first occurrence of a field wins.
    """
    fields = {}
    current = None
    for line in text.splitlines():
        m = _FIELD.match(line)
        if m:
            key = m.group(1).strip().lower()
            current = key if key not in fields else None
            if current:
                fields[current] = (m.group(2) or "").strip()
            continue
        cont = _CONTINUATION.match(line)
        if cont and current:
            fields[current] = (fields[current] + " " + cont.group(1).strip()).strip()
        else:
            current = None
    return fields


def _clip(value, limit):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _safe(part):
    return _PATH_UNSAFE.sub("-", part or "").strip("-") or "x"


def doc_id(project, slug):
    """A document id the db path grammar accepts: letters, digits and `_ - . ~ : @ +` only."""
    return f"{_safe(project)}--{_safe(slug)}"[:200]


def _phase_states(phase, status, track):
    status_l = (status or "").strip().lower()
    if phase == "Complete":
        states = ["done"] * len(PHASES)
    elif phase in PHASES:
        idx = PHASES.index(phase)
        states = []
        for i in range(len(PHASES)):
            if i < idx:
                states.append("done")
            elif i == idx:
                if status_l == "complete":
                    states.append("done")
                elif status_l in ("paused", "blocked") or status_l.startswith("awaiting"):
                    states.append("paused")  # Awaiting Confirmation / Awaiting Implementation Request
                else:
                    states.append("active")
            else:
                states.append("pending")
    else:
        states = ["pending"] * len(PHASES)
    if (track or "").strip().lower() == "fast":
        states[PHASES.index("Tasks")] = "skipped"
    return [{"name": n, "state": s} for n, s in zip(PHASES, states)]


def repo_label(cwd):
    """The project label: basename of the realpath of cwd's nearest ancestor holding a `.git`
    (the git top-level folder), else of cwd itself. No subprocess; realpath so a symlinked path
    and its target give the same label (and so the same record ids)."""
    start = os.path.realpath(cwd or os.getcwd())
    cur = start
    while not os.path.exists(os.path.join(cur, ".git")):
        parent = os.path.dirname(cur)
        if parent == cur:
            cur = start
            break
        cur = parent
    return os.path.basename(cur) or "project"


def build_doc(path, project=None):
    """The Plan Board record for one workflow-state.md, or None when the file can't be read."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    f = parse_fields(text)
    project = project or repo_label(os.getcwd())
    slug = f.get("slug") or os.path.basename(os.path.dirname(os.path.abspath(path)))
    phase = f.get("current phase") or "Unknown"
    status = f.get("workflow status") or "Unknown"
    track = f.get("track") or "Standard"
    impl = f.get("implementation requested")
    updated = f.get("date") or ""
    has_date = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated))
    if not has_date:
        updated = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).strftime("%Y-%m-%d")
    closed = "complete" in (status.strip().lower(), phase.strip().lower())
    doc = {
        "schema": SCHEMA,
        "id": doc_id(project, slug),
        "project": project,
        "slug": slug,
        "title": _clip(f.get("title") or slug, TITLE_MAX),
        "goal": _clip(f.get("goal"), GOAL_MAX),
        "track": track,
        "phase": phase,
        "status": status,
        "pauseReason": _clip(f.get("pause reason") if (f.get("pause reason") or "").lower() != "none" else "", PAUSE_MAX),
        "nextAction": _clip(f.get("next action") if (f.get("next action") or "").lower() != "none" else "", NEXT_MAX),
        "phases": _phase_states(phase, status, track),
        "implementationRequested": None if impl is None else impl.strip().lower() in ("yes", "true"),
        "updatedAt": updated,
        "closedAt": updated if closed and has_date else "",  # an mtime fallback would churn the hash
        "brief": plan_brief.parse_brief(os.path.dirname(os.path.abspath(path)), f),
    }
    import impl_progress
    prog = impl_progress.summary(os.path.dirname(os.path.abspath(path)))
    if prog and prog["last"]:
        doc["lastImplEvent"] = prog["last"]
    found = feature_paths.feature_dir_from_path(os.path.abspath(path))
    url = found and brief_board_url(found[0])
    if url:
        doc["briefBoardUrl"] = url
    doc["contentHash"] = content_hash(doc)
    return doc


def content_hash(doc):
    """Hash of the record's content, ignoring updatedAt (a touch of the file isn't a change) and
    contentHash itself (no self-reference)."""
    body = {k: v for k, v in doc.items() if k not in ("updatedAt", "contentHash")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:16]


# -- project memory: which features are synced ------------------------------------------------

def _memory_dir():
    import sdd_memory
    return sdd_memory.memory_dir(os.getcwd())


def memory_dir_for_state(path):
    """The project memory dir a workflow-state.md belongs to, from its own location.

    A state file lives at <memory dir>/spec/<feature>/workflow-state.md, so its project is known
    without asking which folder the command was run from. Falls back to the current project's
    memory dir for a file that isn't in that layout.
    """
    found = feature_paths.feature_dir_from_path(os.path.abspath(path))
    if found:
        return found[0]
    return _memory_dir()


def _board_fields(memory_dir):
    """The project's PLAN-BOARD.md fields, else the shared one at the sdd-memory root (one board
    for every project, filtered by project on the page), else None."""
    for d in (memory_dir, os.path.dirname(os.path.normpath(memory_dir))):
        try:
            with open(os.path.join(d, BOARD_FILE), "r", encoding="utf-8") as fh:
                return parse_fields(fh.read())
        except OSError:
            continue
    return None


def board_url(memory_dir):
    """The Plan Board page URL recorded in <memory dir>/PLAN-BOARD.md, or None when unset."""
    url = (_board_fields(memory_dir) or {}).get("url", "")
    return url if url.startswith("https://") else None


def brief_board_url(memory_dir):
    """The optional `- Brief Board:` https URL in PLAN-BOARD.md (the ad-hoc brief board), or None."""
    url = (_board_fields(memory_dir) or {}).get("brief board", "")
    return url if url.startswith("https://") else None


def sync_enabled(memory_dir):
    """True when the project has a PLAN-BOARD.md that doesn't say `- Sync: off` (no file = off)."""
    fields = _board_fields(memory_dir)
    return fields is not None and fields.get("sync", "on").strip().lower() != "off"


def _sync_path(memory_dir):
    return os.path.join(memory_dir, SYNC_FILE)


def _read_sync(memory_dir):
    try:
        with open(_sync_path(memory_dir), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def mark_synced(memory_dir, doc):
    """Record that `doc` was written to the board. Atomic; returns False if it couldn't save."""
    data = _read_sync(memory_dir)
    data[doc["id"]] = content_hash(doc)
    tmp = _sync_path(memory_dir) + ".tmp"
    try:
        os.makedirs(memory_dir, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.replace(tmp, _sync_path(memory_dir))
        return True
    except OSError:
        return False


def stale_features(memory_dir, project):
    """[(slug, state path, doc)] for features whose board record is missing or out of date.

    Empty when no Plan Board URL is recorded for the project: the feature is opt-in.
    """
    if not board_url(memory_dir) or not sync_enabled(memory_dir):
        return []
    synced = _read_sync(memory_dir)
    out = []
    spec = os.path.join(memory_dir, "spec")
    try:
        names = sorted(os.listdir(spec))
    except OSError:
        return []
    for name in names:
        path = os.path.join(spec, name, "workflow-state.md")
        if not os.path.isfile(path):
            continue
        doc = build_doc(path, project=project)
        if doc and synced.get(doc["id"]) != content_hash(doc):
            out.append((name, path, doc))
    return out


def _arg(argv, flag, default=None):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "doc" and len(argv) >= 2:
        doc = build_doc(argv[1], project=_arg(argv, "--project"))
        if doc is None:
            print(f"plan_board: cannot read {argv[1]}", file=sys.stderr)
            return 1
        out = _arg(argv, "--out")
        if out:
            try:
                with open(out, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, indent=1)
            except OSError as exc:
                print(f"plan_board: cannot write {out}: {exc}", file=sys.stderr)
                return 1
            print(doc["id"])  # the doc_id to write it under
        else:
            print(json.dumps(doc, indent=1))
        return 0
    if cmd == "page" and len(argv) == 2:
        try:
            with open(PAGE, "r", encoding="utf-8") as src, open(argv[1], "w", encoding="utf-8") as out:
                out.write(src.read())
        except OSError as exc:
            print(f"plan_board: {exc}", file=sys.stderr)
            return 1
        return 0
    if cmd == "stale":
        cwd = _arg(argv, "--cwd", os.getcwd())
        os.chdir(cwd)
        project = repo_label(cwd)
        for slug, path, _doc in stale_features(_memory_dir(), project):
            print(f"{slug}\t{path}")
        return 0
    if cmd == "mark-synced" and len(argv) >= 2:
        doc = build_doc(argv[1], project=_arg(argv, "--project"))
        if doc is None:
            print(f"plan_board: cannot read {argv[1]}", file=sys.stderr)
            return 1
        if not mark_synced(memory_dir_for_state(argv[1]), doc):
            print("plan_board: could not save the sync mark", file=sys.stderr)
            return 1
        print(doc["id"])
        return 0
    print("usage: plan_board.py doc <state.md> [--project NAME] [--out FILE] | page <out.html> | "
          "stale [--cwd DIR] | mark-synced <state.md> [--project NAME]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
