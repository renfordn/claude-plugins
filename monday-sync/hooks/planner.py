"""monday-sync planner: pure functions from workflow-state + git + board item to a sync plan.

No I/O except where a function says so. Stdlib only.
"""
import datetime
import hashlib
import re

from fields import parse_fields  # noqa: F401  (re-exported)

PRE_IMPL = ("requirements", "design", "tasks")
POST_IMPL = ("implementation", "complete")

def git_known(git):
    """True when git probe output is usable (a dict whose on_origin/merged/ahead aren't unknown)."""
    if not isinstance(git, dict):
        return False
    return all(isinstance(git.get(k), t) for k, t in
               (("on_origin", bool), ("merged", bool), ("ahead", int)))


def _result(status, source, write=True, flag=None):
    return {"status": status, "source": source, "write": write, "flag": flag}


def synced_fields(fields):
    """The isdd fields a sync (or an accepted conflict answer) is pinned to."""
    return {"phase": fields.get("current phase"), "workflow_status": fields.get("workflow status")}


def git_pin(git):
    """The git state an accepted conflict answer is pinned to; None when git is unknown."""
    if not git_known(git):
        return None
    return {"head": git.get("head"), "on_origin": git["on_origin"], "merged": git["merged"]}


def _accept_holds(fields, git, sidecar):
    """An accepted board status holds while isdd phase/status and (known) git state are unchanged.

    Unknown git now, or no git pinned at accept time, doesn't lapse it."""
    acc = sidecar.get("accepted_fields") or {}
    if {"phase": acc.get("phase"), "workflow_status": acc.get("workflow_status")} != synced_fields(fields):
        return False
    pin = git_pin(git)
    return pin is None or acc.get("git") is None or acc.get("git") == pin


def desired_status(fields, git, sidecar=None):
    """Board Status for a feature per design.md's mapping table (first match wins).

    Returns {status, source ("phase"|"git"|"user"), write (False = keep, don't push), flag}.
    A board status the user accepted in a conflict (source "user") is authoritative until the
    isdd phase/status or the git state moves from what it was at accept time, and never over a
    merge-derived Done; a user-confirmed Done
    holds through Implementation/Complete (no branch_gone question) but not through a rewind.
    """
    sidecar = sidecar or {}
    last = sidecar.get("last_pushed") or {}
    phase = (fields.get("current phase") or "").strip().lower()
    wstatus = (fields.get("workflow status") or "").strip().lower()
    merged_done = (phase in POST_IMPL and git_known(git) and git["merged"]
                   and bool(sidecar.get("pushed_head") or git.get("merge_subject")))
    if last.get("source") == "user" and last.get("status") and not merged_done \
            and _accept_holds(fields, git, sidecar):
        return _result(last["status"], "user", write=False)
    if wstatus == "blocked":
        return _result("Stuck", "phase")
    if phase in PRE_IMPL:
        # Planning done (tasks drafted, or isdd awaiting the implementation request) vs still specing.
        if phase == "tasks" or wstatus == "awaiting implementation request":
            return _result("Implementation Ready", "phase")
        return _result("Gather Requirements", "phase")
    if phase not in POST_IMPL:
        # Unknown/empty phase: don't guess; keep what was last pushed.
        return _result(last.get("status"), "phase", write=False)
    if sidecar.get("confirmed_done"):
        return _result("Done", "user")
    if git_known(git):
        if git["merged"] and (sidecar.get("pushed_head") or git.get("merge_subject")):
            return _result("Done", "git")
        if git["on_origin"] and git["ahead"] > 0:
            return _result("Review", "git")
        if not git["on_origin"] and sidecar.get("pushed_head"):
            return _result("Review", "git", flag="branch_gone")
    else:
        if last.get("source") == "git" and last.get("status"):
            return _result(last["status"], "git", write=False)
    return _result("In progress", "phase")


def notes_text(fields, slug):
    """Notes column: `Phase: X · Next: Y · Spec: <slug>` (slug field wins over the dir slug)."""
    nxt = (fields.get("next action") or "").strip() or "None"
    spec = (fields.get("slug") or "").strip() or slug
    return f"Phase: {fields.get('current phase') or '?'} · Next: {nxt} · Spec: {spec}"


_GITHUB = re.compile(r"(?:^|[@/])github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_PR = re.compile(r"Merge pull request #(\d+)")


def github_repo(url):
    """`owner/repo` from a GitHub remote URL (ssh, scp-like or https); None otherwise."""
    m = _GITHUB.search(url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def code_link(git, branch):
    """PR URL when the merge subject names a PR, else the branch tree URL; None if unknowable."""
    if not isinstance(git, dict):
        return None
    repo = github_repo(git.get("origin_url"))
    if not repo:
        return None
    m = _PR.search(git.get("merge_subject") or "") if git.get("merged") is True else None
    if m:
        return f"https://github.com/{repo}/pull/{m.group(1)}"
    return f"https://github.com/{repo}/tree/{branch}" if branch else None


def state_hash(text):
    """16-hex sha256 of workflow-state.md content (content_hash style, plan_board.py:152)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]



# -- board columns (Software Engineering board, see skills/monday-sync/references/board.md) ------

STATUS_COL = "color_mm7na652"
TYPE_COL = "color_mm7n3b93"
PROJECT_COL = "dropdown_mm7na5br"
LINK_COL = "text_mm7nz61n"
NOTES_COL = "long_text_mm7nzhmb"


# -- plan() helpers ----------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")
NOTE_MAX = 240
UNSET_STATUSES = (None, "", "To do")


def _clean(text):
    text = re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()
    return text if len(text) <= NOTE_MAX else text[: NOTE_MAX - 1].rstrip() + "…"


def _update_key(u):
    return (u.get("created_at") or "", str(u.get("id") or ""))


def _latest_update(item):
    updates = (item or {}).get("updates") or []
    return max(updates, key=_update_key) if updates else None


def _notes_user_edited(item, last_pushed):
    """True when the board Notes aren't what we last pushed (hook ownership lost).

    With no pushed baseline (freshly linked ticket), any non-empty Notes count as the user's."""
    notes = (item or {}).get("notes") or ""
    pushed_hash = (last_pushed or {}).get("notes_hash")
    if pushed_hash is None:
        return bool(notes.strip())
    return state_hash(notes) != pushed_hash


def _latest_note(item, last_pushed):
    """Newest update body, else the Notes column if the user edited it, else a stock line."""
    latest = _latest_update(item)
    if latest and _clean(latest.get("body")):
        return _clean(latest.get("body"))
    if _notes_user_edited(item, last_pushed) and _clean(item.get("notes")):
        return _clean(item.get("notes"))
    return "Set to Stuck on the monday board"


def _board_rules(fields, desired, item, last_pushed):
    """Decision table for board->isdd. Returns (push_status, user_stuck, isdd_updates, conflicts).

    user_stuck: the board's Stuck is the user's (set on the board, or mirrored from it and isdd is
    still blocked) -- neither Status nor Notes is written over it."""
    if item is None:
        return True, False, {}, []
    board_status = item.get("status")
    lp = last_pushed or {}
    if board_status == "Stuck" and lp.get("status") != "Stuck":
        updates = {}
        if (fields.get("workflow status") or "").strip().lower() != "blocked":
            target = {"Workflow Status": "Blocked", "Pause Reason": "blocker",
                      "Hook Notes": _latest_note(item, last_pushed)}
            updates = {k: v for k, v in target.items() if (fields.get(k.lower()) or "") != v}
        return False, True, updates, []
    if board_status == "Stuck" and lp.get("source") == "board" and desired["status"] == "Stuck":
        return False, True, {}, []
    if (desired["status"] is not None and board_status != desired["status"]
            and board_status != lp.get("status")
            and not (last_pushed is None and board_status in UNSET_STATUSES)):
        return False, False, {}, [{"kind": "status", "board": board_status,
                                   "desired": desired["status"], "last_pushed": lp.get("status")}]
    return desired["write"], False, {}, []


def _notes_write(item, desired_notes, last_pushed, user_stuck):
    """(write?, notes_hash to record). Notes are hook-owned only while the user hasn't edited them."""
    if item is None:
        return True, state_hash(desired_notes)
    if (item.get("notes") or "") == desired_notes:
        return False, state_hash(desired_notes)
    if user_stuck or _notes_user_edited(item, last_pushed):
        return False, (last_pushed or {}).get("notes_hash")
    return True, state_hash(desired_notes)


def _board_changes(item, sidecar):
    """What the user changed on the board since the last sync: status vs the post-write last_seen
    status, user-edited Notes (reported once, via last_seen notes_hash), and updates after
    last_update_id (or, if that id is gone, newer than update_created_at). Never compares item
    timestamps, so our own writes aren't reported. Empty on the first sync (no baseline)."""
    last_seen = sidecar.get("last_seen_board")
    if item is None or not last_seen:
        return []
    changes = []
    if item.get("status") != last_seen.get("status"):
        changes.append({"kind": "status", "from": last_seen.get("status"), "to": item.get("status")})
    notes = item.get("notes") or ""
    if (_notes_user_edited(item, sidecar.get("last_pushed"))
            and state_hash(notes) != last_seen.get("notes_hash")):
        changes.append({"kind": "notes", "text": _clean(notes)})
    updates = sorted(item.get("updates") or [], key=_update_key)
    ids = [u.get("id") for u in updates]
    seen, seen_at = last_seen.get("last_update_id"), last_seen.get("update_created_at")
    if seen in ids:
        new = updates[ids.index(seen) + 1:]
    elif seen is None:
        new = updates
    elif seen_at:
        new = [u for u in updates if (u.get("created_at") or "") > seen_at]
    else:
        new = []
    for u in new:
        changes.append({"kind": "update", "id": u.get("id"), "text": _clean(u.get("body"))})
    return changes


def _recap_line(changes, now):
    if not changes:
        return None
    parts = []
    for c in changes:
        if c["kind"] == "status":
            parts.append(f"status {c['from']} -> {c['to']}")
        else:
            parts.append(f"{c['kind']}: {c['text']}")
    return f"- {now or ''} Board changes: " + "; ".join(parts)


def _desired(fields, git, sidecar, slug):
    ds = desired_status(fields, git, sidecar)
    return dict(ds, notes=notes_text(fields, slug), code_link=code_link(git, sidecar.get("branch")))


def _plan_result(state_text, desired=None, **kw):
    """The plan() result dict with every key present (defaults = nothing to do, save nothing)."""
    result = {"desired": desired, "writes": {}, "isdd_updates": {}, "conflicts": [], "changes": [],
              "recreate": None, "create": False, "snapshot": None,
              "state_hash": state_hash(state_text), "recap_line": None, "skipped": None}
    result.update(kw)
    return result


def _ask_missing(fields, git, sidecar, slug, state_text):
    """Linked item gone again after one recreate: never auto-recreate twice; ask (recreate/unlink)."""
    conflict = {"kind": "item_missing", "item_id": sidecar.get("item_id"),
                "recreated_from": sidecar.get("recreated_from"),
                "question": "Board item was deleted again - recreate it or unlink the feature?"}
    return _plan_result(state_text, _desired(fields, git, sidecar, slug), conflicts=[conflict],
                        recreate="ask")


def plan(state_text, sidecar, git, item, slug, now=None):
    """Sync plan for one feature. Pure: the caller loads workflow-state.md text and the sidecar.

    item is the normalized board item ({id, status, notes, code_link, updated_at, updates}) or None
    when the feature has no board item. Returns {desired, writes, isdd_updates, conflicts, changes,
    recreate, create, snapshot, state_hash, recap_line}; `snapshot` is what to merge into the
    sidecar once the writes succeed (None: save nothing).
    """
    fields = parse_fields(state_text)
    if sidecar.get("unlinked"):
        return _plan_result(state_text, skipped="unlinked")
    recreate = None
    if item is None and sidecar.get("item_id"):
        if sidecar.get("recreated_from"):
            return _ask_missing(fields, git, sidecar, slug, state_text)
        recreate = "recreate"
        sidecar = dict(sidecar, last_pushed=None, last_seen_board=None)
    desired = _desired(fields, git, sidecar, slug)
    create = item is None
    board = item or {}
    last_pushed = sidecar.get("last_pushed")
    push_status, user_stuck, isdd_updates, conflicts = _board_rules(fields, desired, item, last_pushed)
    if desired["flag"] == "branch_gone":
        conflicts.append({"kind": "branch_gone", "branch": sidecar.get("branch"),
                          "question": "Branch gone from origin, not merged - confirm Done?"})

    writes = {}
    if push_status and desired["status"] is not None and board.get("status") != desired["status"]:
        writes[STATUS_COL] = desired["status"]
    write_notes, notes_hash = _notes_write(item, desired["notes"], last_pushed, user_stuck)
    if write_notes:
        writes[NOTES_COL] = desired["notes"]
    if desired["code_link"] and board.get("code_link") != desired["code_link"]:
        writes[LINK_COL] = desired["code_link"]
    if create:
        writes[TYPE_COL] = "Feature"
        if sidecar.get("project"):
            writes[PROJECT_COL] = sidecar["project"]

    if user_stuck:
        pushed = {"status": "Stuck", "source": "board"}
    elif push_status:
        pushed = {"status": desired["status"], "source": desired["source"]}
    else:
        pushed = {k: (last_pushed or {}).get(k) for k in ("status", "source")}
    pushed.update(notes_hash=notes_hash, code_link=desired["code_link"])

    pushed_head = sidecar.get("pushed_head")
    if git_known(git) and git["on_origin"] and git["ahead"] > 0 and git.get("head"):
        pushed_head = git["head"]

    changes = _board_changes(item, sidecar)
    latest = _latest_update(item) or {}
    snapshot = {
        "last_pushed": pushed,
        "last_seen_board": {"status": writes.get(STATUS_COL, board.get("status")),
                            "notes_hash": state_hash(writes.get(NOTES_COL, board.get("notes") or "")),
                            "updated_at": board.get("updated_at"),
                            "last_update_id": latest.get("id"),
                            "update_created_at": latest.get("created_at")},
        "synced_fields": synced_fields(fields),
        "pushed_head": pushed_head,
        "state_hash": state_hash(state_text),
        "synced_at": now,
    }
    if recreate:
        snapshot.update(recreated_from=sidecar["item_id"], item_id=None)
    elif sidecar.get("recreated_from"):
        snapshot["recreated_from"] = sidecar["recreated_from"]   # keep the recreate-once guard
    if (fields.get("current phase") or "").strip().lower() in PRE_IMPL:
        snapshot["confirmed_done"] = False          # a rewind ends a user-confirmed Done
    return _plan_result(state_text, desired, writes=writes, isdd_updates=isdd_updates,
                        conflicts=conflicts, changes=changes, recreate=recreate, create=create,
                        snapshot=snapshot, recap_line=_recap_line(changes, now))


def normalize_item(raw):
    """A board item as {id, name, group, status, notes, code_link, updated_at, created_at, project,
    updates} (project = the Project dropdown text).

    Accepts the live get_board_items_page shape (column_values {column_id: text}, group {title})
    with an optional `updates` list the skill attaches from get_updates (body or text_body), the
    older column_values [{id, text}] list form, or an already-normalized dict.
    """
    raw = raw or {}
    cv = raw.get("column_values")
    if isinstance(cv, dict):
        cols = dict(cv)
    else:
        cols = {c.get("id"): c.get("text") for c in cv or [] if isinstance(c, dict)}
    group = raw.get("group")
    if isinstance(group, dict):
        group = group.get("title")
    updates = [{"id": str(u.get("id")), "body": u.get("text_body") or u.get("body") or "",
                "created_at": u.get("created_at")} for u in raw.get("updates") or [] if isinstance(u, dict)]
    return {
        "id": None if raw.get("id") is None else str(raw["id"]),
        "name": raw.get("name"),
        "group": group,
        "status": cols.get(STATUS_COL, raw.get("status")),
        "notes": cols.get(NOTES_COL, raw.get("notes")),
        "code_link": cols.get(LINK_COL, raw.get("code_link")),
        "updated_at": raw.get("updated_at"),
        "created_at": raw.get("created_at"),
        "project": cols.get(PROJECT_COL, raw.get("project")),
        "updates": updates,
    }


def candidates(items, linked_ids, dismissed=()):
    """Backlog items in To do with no linked feature and not dismissed: [{id, name}]."""
    skip = {str(i) for i in linked_ids} | {str(i) for i in dismissed}
    out = []
    for raw in items or []:
        it = normalize_item(raw)
        if it["group"] == "Backlog" and it["status"] == "To do" and it["id"] not in skip:
            out.append({"id": it["id"], "name": it["name"]})
    return out



# -- kickoff (scheduled 'Gather Requirements' poll; see skills/monday-kickoff/SKILL.md) ------------

KICKOFF_STATUS = "Gather Requirements"
KICKOFF_MARKER = re.compile(r"^🤖 isdd kickoff (started|done|needs-project)\b")
KICKOFF_RETRY = re.compile(r"^isdd kickoff retry\b", re.I)


def _time_key(ts):
    """Sort key for an ISO timestamp: parsed times in time order, unparsable/missing ones first."""
    try:
        return (1, parse_iso(ts).timestamp(), "")
    except ValueError:
        return (0, 0.0, ts if isinstance(ts, str) else "")


def _kickoff_markers(it):
    """[(kind, created_at)] for updates whose (tag-stripped) body starts with a kickoff marker,
    ignoring markers posted before the latest user `isdd kickoff retry` update (restart path)."""
    bodies = [(_clean(u.get("body")), u.get("created_at")) for u in it.get("updates") or []]
    retries = [_time_key(ts) for body, ts in bodies if KICKOFF_RETRY.match(body)]
    cutoff = max(retries) if retries else None
    out = []
    for body, ts in bodies:
        m = KICKOFF_MARKER.match(body)
        if m and (cutoff is None or _time_key(ts) > cutoff):
            out.append((m.group(1), ts))
    return out


def _kickoff_eligible(it):
    """In Gather Requirements and not linked to an isdd feature (no `Spec:` in Notes, no Code link)."""
    return (it["status"] == KICKOFF_STATUS and "Spec:" not in (it["notes"] or "")
            and not (it["code_link"] or "").strip())


KICKOFF_RETRY_AFTER = datetime.timedelta(hours=3)
_NAME_PREFIX = re.compile(r"^\s*\[([^\]]*)\]")


def ticket_name_key(name):
    """Comparison key for `[<project>] <Title>` ticket names: whitespace collapsed, case folded."""
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def _linked_by_spec(it, spec_index):
    """True when a repo spec folder already claims the ticket: its `- Monday Item:` is the ticket id,
    or its `- Title:` makes the ticket name `[<project>] <Title>` (project = the Project label, else
    the ticket name's own bracket prefix)."""
    if not spec_index:
        return False
    if it["id"] in {str(e["item_id"]) for e in spec_index if e.get("item_id") not in (None, "")}:
        return True
    project = (it["project"] or "").strip()
    if not project:
        m = _NAME_PREFIX.match(it["name"] or "")
        project = m.group(1).strip() if m else ""
    name = ticket_name_key(it["name"])
    return any(e.get("title") and name == ticket_name_key(f"[{project}] {e['title']}")
               for e in spec_index)


def parse_iso(ts):
    """Aware datetime from an ISO timestamp (`Z` ok, naive = UTC). Raises ValueError if unparsable."""
    if not isinstance(ts, str) or not ts.strip():
        raise ValueError(f"not an ISO timestamp: {ts!r}")
    dt = datetime.datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def _stale(ts, now):
    """True when a marker is more than 3h old; a missing/unparsable time counts as stale, so a
    malformed marker can't block the ticket forever."""
    try:
        return now - parse_iso(ts) > KICKOFF_RETRY_AFTER
    except ValueError:
        return True


def _oldest_key(it):
    """Oldest first by created_at (else updated_at) in time order; unparsable times after parsed
    ones (string order), missing last; then numeric-ish id order."""
    ts = it.get("created_at") or it.get("updated_at")
    parsed, stamp, raw = _time_key(ts)
    id_ = it["id"] or ""
    return (ts is None, -parsed, stamp, raw, len(id_), id_)


def kickoff_candidates(items, now, project_map, spec_index=None):
    """Pick at most one Gather Requirements ticket to kick off, oldest first.

    Returns {"pick": {id, name, project, repo_path, attempt} | None, "needs_project": [id],
    "stuck": [id]}. Pure: `now` is an ISO timestamp (ValueError if not), project_map maps
    Project label -> repo path, spec_index lists the repos' spec folders [{title, item_id, dir}];
    a ticket a spec folder already claims (see _linked_by_spec) is never a candidate. Rules (design.md touchpoint 4): a `done` marker skips the ticket;
    a missing/unmapped Project is reported in needs_project unless a needs-project marker already
    asked; a `started` marker 3h old or less means a run is in flight (no/bad time = stale);
    markers before the latest user update starting `isdd kickoff retry` are ignored; one stale start retries
    (attempt 2); two or more with the latest stale are stuck.
    """
    now = parse_iso(now)
    project_map = project_map or {}
    ready, needs_project, stuck = [], [], []
    for raw in items or []:
        it = normalize_item(raw)
        if not _kickoff_eligible(it) or _linked_by_spec(it, spec_index):
            continue
        markers = _kickoff_markers(it)
        kinds = [k for k, _ in markers]
        if "done" in kinds:
            continue
        project = (it["project"] or "").strip()
        if project not in project_map:
            if "needs-project" not in kinds:     # asked once already: wait for the label to change
                needs_project.append(it["id"])
            continue
        started = sorted((ts for k, ts in markers if k == "started"), key=_time_key)
        if started and not _stale(started[-1], now):
            continue                             # a run is (probably) still going
        if len(started) >= 2:
            stuck.append(it["id"])               # retried once already and died again
            continue
        ready.append((it, project, len(started) + 1))
    pick = None
    if ready:
        it, project, attempt = min(ready, key=lambda r: _oldest_key(r[0]))
        pick = {"id": it["id"], "name": it["name"], "project": project,
                "repo_path": project_map[project], "attempt": attempt}
    return {"pick": pick, "needs_project": needs_project, "stuck": stuck}
