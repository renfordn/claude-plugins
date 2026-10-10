#!/usr/bin/env python3
"""monday-sync CLI: thin JSON wrapper over planner.py (pure) and store.py (I/O).

    cli.py plan <feature_dir> [--git FILE] [--item FILE | --item-missing] [--now ISO]
    cli.py sync-begin <feature_dir>
    cli.py record <feature_dir> [--item-id ID] [--branch B] [--project P] [--repo-path R]
                                [--snapshot FILE] [--accept-board-status LABEL [--git FILE]]
                                [--unlink | --forget-item]
    cli.py pending list
    cli.py pending clear <feature_dir> [--expect-hash H]
    cli.py candidates --items FILE | --dismiss ID
    cli.py kickoff-candidates --items FILE --now ISO [--project-map FILE] [--spec-index FILE]

Every command prints one JSON value. Store commands need CLAUDE_PLUGIN_DATA (exit 2 + {"error"});
kickoff-candidates doesn't (scheduled kickoff runs keep no state between sessions).
FILE may be "-" for stdin.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fields  # noqa: E402
import planner  # noqa: E402
import store  # noqa: E402

STATE_FILE = fields.STATE_FILE
PROJECT_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "skills", "monday-kickoff", "references", "projects.json")
STATUS_LABELS = ("To do", "Gather Requirements", "Implementation Ready", "In progress", "Review",
                 "Done", "Stuck")


class CliError(Exception):
    pass


def _out(value):
    print(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False))


def _load_json(path):
    if path is None:
        return None
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise CliError(f"cannot read JSON from {path}: {exc}")


def _state_text(feature_dir):
    try:
        with open(os.path.join(feature_dir, STATE_FILE), "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise CliError(f"cannot read {STATE_FILE} in {feature_dir}: {exc}")


def _need_store():
    if not store.store_path():
        raise CliError("CLAUDE_PLUGIN_DATA not set; pass it explicitly to this command")


def _items(raw):
    """A list of raw items from a list, an {"items": [...]} wrapper, or one item dict."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw["items"] if isinstance(raw.get("items"), list) else [raw]
    raise CliError("items JSON must be a list, {\"items\": [...]} or one item object")


def cmd_plan(a):
    text = _state_text(a.feature_dir)
    sidecar = store.load_sidecar(a.feature_dir)
    if a.item and a.item_missing:
        raise CliError("pass either --item or --item-missing, not both")
    if a.item:
        items = _items(_load_json(a.item))
        if len(items) != 1:
            raise CliError(f"--item must hold exactly one board item, got {len(items)}")
        item = planner.normalize_item(items[0])
    elif sidecar.get("item_id") and not a.item_missing:
        raise CliError(f"feature is linked to item {sidecar['item_id']}: pass --item <file> with "
                       "the board item, or --item-missing if it no longer exists on the board")
    else:
        item = None
    slug = os.path.basename(os.path.normpath(a.feature_dir))
    _out(planner.plan(text, sidecar, _load_json(a.git), item, slug, now=a.now,
                     slices=fields.slice_progress(a.feature_dir)))


def cmd_sync_begin(a):
    """Mark a sync as running, so flag_sync doesn't nudge for the skill's own isdd_updates edits."""
    sc = store.load_sidecar(a.feature_dir)
    sc["syncing_since"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not store.save_sidecar(a.feature_dir, sc):
        raise CliError(f"cannot write {store.SIDECAR} in {a.feature_dir}")
    _out({"ok": True, "syncing_since": sc["syncing_since"]})


def cmd_record(a):
    if a.unlink and (a.item_id or a.forget_item):
        raise CliError("--unlink can't be combined with --item-id or --forget-item")
    if a.accept_board_status and a.accept_board_status not in STATUS_LABELS:
        raise CliError(f"--accept-board-status must be one of {', '.join(STATUS_LABELS)}")
    sc = store.load_sidecar(a.feature_dir)
    snap = _load_json(a.snapshot)
    if isinstance(snap, dict):
        # Accept a whole `plan` output (use its snapshot; None = save nothing) or a bare snapshot.
        sc.update((snap.get("snapshot") or {}) if "snapshot" in snap else snap)
        sc["syncing_since"] = None                      # the sync this snapshot ends is over
    for key in ("item_id", "branch", "project", "repo_path"):
        value = getattr(a, key)
        if value is not None:
            sc[key] = value
    if a.item_id:
        sc["unlinked"] = False                          # relink opts back in
    if a.forget_item:
        sc["item_id"] = None                            # next plan is a plain create
    if a.accept_board_status:
        # A conflict answered "keep the board": authoritative until isdd phase/status moves.
        sc["last_pushed"] = dict(sc.get("last_pushed") or {}, status=a.accept_board_status,
                                 source="user")
        sc["accepted_fields"] = dict(planner.synced_fields(fields.read_fields(a.feature_dir)),
                                     git=planner.git_pin(_load_json(a.git)))
        if a.accept_board_status == "Done":
            sc["confirmed_done"] = True
    if a.unlink:
        sc.update(item_id=None, unlinked=True, syncing_since=None)
    if not store.save_sidecar(a.feature_dir, sc):
        raise CliError(f"cannot write {store.SIDECAR} in {a.feature_dir}")
    linked = False
    if store.store_path():
        linked = store.set_linked(a.feature_dir, sc.get("item_id")) and bool(sc.get("item_id"))
        if a.unlink:
            store.remove_pending(a.feature_dir)
    _out({"ok": True, "linked": bool(linked), "sidecar": sc})


def cmd_pending(a):
    _need_store()
    if a.action == "list":
        out = []
        for d in store.list_pending():
            out.append({"dir": d, "title": fields.feature_title(d), "slug": os.path.basename(d)})
        _out(out)
        return
    if not a.feature_dir:
        raise CliError("pending clear needs <feature_dir>")
    if a.expect_hash:
        try:
            current = planner.state_hash(_state_text(a.feature_dir))
        except CliError:
            current = None
        if current is not None and current != a.expect_hash:
            _out({"cleared": False, "reason": "workflow-state.md changed since plan; re-run plan"})
            return
    _out({"cleared": bool(store.remove_pending(a.feature_dir))})


def cmd_candidates(a):
    _need_store()
    if a.dismiss:
        _out({"dismissed": bool(store.dismiss(a.dismiss))})
        return
    items = _items(_load_json(a.items))
    st = store.load_store()
    _out(planner.candidates(items, st["linked"].values(), st["dismissed_candidates"]))


def cmd_kickoff_candidates(a):
    """At most one Gather Requirements ticket to kick off; pure (no store)."""
    project_map = _load_json(a.project_map or PROJECT_MAP)
    if not isinstance(project_map, dict):
        raise CliError("project map JSON must be an object {project label: repo path}")
    try:
        planner.parse_iso(a.now)
    except ValueError:
        raise CliError(f"--now must be an ISO timestamp, got {a.now!r}")
    spec_index = _load_json(a.spec_index) if a.spec_index else []
    if not (isinstance(spec_index, list) and all(isinstance(e, dict) for e in spec_index)):
        raise CliError("--spec-index JSON must be a list of {title, item_id, dir} objects")
    _out(planner.kickoff_candidates(_items(_load_json(a.items)), a.now, project_map, spec_index))


def build_parser():
    p = argparse.ArgumentParser(prog="cli.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("feature_dir")
    pl.add_argument("--git")
    pl.add_argument("--item")
    pl.add_argument("--item-missing", dest="item_missing", action="store_true")
    pl.add_argument("--now")
    pl.set_defaults(func=cmd_plan)
    rc = sub.add_parser("record")
    rc.add_argument("feature_dir")
    rc.add_argument("--item-id", dest="item_id")
    rc.add_argument("--branch")
    rc.add_argument("--project")
    rc.add_argument("--repo-path", dest="repo_path")
    rc.add_argument("--snapshot")
    rc.add_argument("--accept-board-status", dest="accept_board_status")
    rc.add_argument("--git", help="git probe JSON to pin an accepted status to")
    rc.add_argument("--unlink", action="store_true")
    rc.add_argument("--forget-item", dest="forget_item", action="store_true")
    rc.set_defaults(func=cmd_record)
    sb = sub.add_parser("sync-begin")
    sb.add_argument("feature_dir")
    sb.set_defaults(func=cmd_sync_begin)
    pe = sub.add_parser("pending")
    pe.add_argument("action", choices=("list", "clear"))
    pe.add_argument("feature_dir", nargs="?")
    pe.add_argument("--expect-hash", dest="expect_hash")
    pe.set_defaults(func=cmd_pending)
    ca = sub.add_parser("candidates")
    ca.add_argument("--items")
    ca.add_argument("--dismiss")
    ca.set_defaults(func=cmd_candidates)
    kc = sub.add_parser("kickoff-candidates")
    kc.add_argument("--items", required=True)
    kc.add_argument("--now", required=True)
    kc.add_argument("--project-map", dest="project_map")
    kc.add_argument("--spec-index", dest="spec_index")
    kc.set_defaults(func=cmd_kickoff_candidates)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except CliError as exc:
        _out({"error": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
