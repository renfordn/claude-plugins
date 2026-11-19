#!/usr/bin/env python3
"""Stop hook: end-of-turn gate and reminder for the active SDD workflow.

Reminds (non-blocking) when the workflow is paused (status contains "block", "await" or
"confirm"). Blocks the stop (one `decision: block` per invocation, reasons merged, never when
`stop_hook_active`) for the Plan Board gate, a stalled phase (artifact Approved, next phase not
entered) and the R3 backstop (Complete while a high-risk slice lacks review evidence). Each block
fires once per change (see _once_per_change); a changed state re-arms it.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_tracking  # noqa: E402
from sdd_state import active_state_file, parse_state, detect_stall, is_complete_state  # noqa: E402
from sdd_memory import local_state_dir, memory_dir  # noqa: E402




def _write_last_stop_marker(cwd):
    """Record 'the last time a session ended normally' so SessionStart can tell
    a clean resume apart from recovering after an interrupted session. Additive
    and best-effort — never affects Stop's control flow."""
    try:
        d = local_state_dir(cwd)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last-stop.json"), "w", encoding="utf-8") as fh:
            json.dump({"timestamp": datetime.datetime.now().isoformat()}, fh)
    except OSError:
        pass


RECENT_S = 24 * 3600
NUDGED_FILE = "plan-board-stop-nudged.json"


def _once_per_change(project_cwd, key, digest):
    """True (and record it) when `digest` differs from the last one recorded for `key`;
    False when this exact change was already nudged. Persists in local_state_dir JSON."""
    path = os.path.join(local_state_dir(project_cwd), NUDGED_FILE)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            nudged = json.load(fh)
        nudged = nudged if isinstance(nudged, dict) else {}
    except (OSError, ValueError):
        nudged = {}
    if nudged.get(key) == digest:
        return False
    nudged[key] = digest
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(nudged, fh)
    except OSError:
        pass
    return True


def _main_repo(cwd):
    """The main checkout for a git worktree (parent of the shared .git dir), else None."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    common = out.stdout.strip()
    if out.returncode or not common:
        return None
    main = os.path.dirname(common)
    real_main, real_cwd = os.path.realpath(main), os.path.realpath(cwd)
    if real_main == real_cwd:
        return None
    # Keep cwd's own spelling (e.g. /var vs /private/var) when the worktree sits inside the main
    # checkout (.claude/worktrees/<name>), so the project slug matches the main session's.
    rel = os.path.relpath(real_cwd, real_main)
    if not rel.startswith("..") and cwd.rstrip("/").endswith(rel):
        return cwd.rstrip("/")[: -len(rel)].rstrip("/") or main
    return main


def _board_memory(cwd):
    """(memory dir, project cwd) holding this project's Plan Board; a worktree uses its main repo's."""
    import plan_board
    mem = memory_dir(cwd)
    if plan_board.board_url(mem):
        return mem, cwd
    main = _main_repo(cwd)
    if main and plan_board.board_url(memory_dir(main)):
        return memory_dir(main), main
    return None, None


def _plan_board_gate(payload, cwd):
    """Block the stop once per changed record when a feature changed in the last 24h is stale
    on the Plan Board. Reminders alone were ignored; this makes the sync part of the turn.
    Returns the reason text, or "" to let the stop through."""
    if payload.get("stop_hook_active"):
        return ""                      # the stop is already a hook continuation: never loop
    import plan_board
    mem, project_cwd = _board_memory(cwd)
    if not mem:
        return ""
    project = plan_board.repo_label(project_cwd)
    now = datetime.datetime.now().timestamp()
    due = []
    for slug, path, doc in plan_board.stale_features(mem, project):
        recent = False
        for f in (path, os.path.join(os.path.dirname(path), "impl-progress.json")):
            try:
                recent = recent or now - os.path.getmtime(f) <= RECENT_S
            except OSError:
                pass
        h = plan_board.content_hash(doc)
        if recent and _once_per_change(project_cwd, doc["id"], h):
            due.append((slug, path, doc))
    if not due:
        return ""
    import shlex
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan_board.py")
    url = plan_board.board_url(mem)
    lines = [f"Plan Board ({url}) is out of date for {len(due)} feature(s) changed this session. "
             f"Before ending the turn, for each: run `python3 {shlex.quote(script)} doc <state> "
             f"--project {shlex.quote(project)} --out <temp file>`, `ArtifactData get` its `id` in "
             f"collection `plans`, `ArtifactData set` with `file_path` = the temp file (add "
             f"`if_version` when the record exists), then `python3 {shlex.quote(script)} "
             f"mark-synced <state> --project {shlex.quote(project)}`. If a step fails, say so in "
             f"one line and stop; this check will not block again for the same change."]
    lines += [f"- {slug} ({path})" for slug, path, _doc in due]
    return "\n".join(lines)


def _recent_complete_states(cwd):
    """Every workflow-state.md changed in the last 24h whose status is Complete (they drop out of
    active_state_file, so the R3 backstop looks for them here), newest first."""
    import glob
    now = datetime.datetime.now().timestamp()
    found = []
    for p in glob.glob(os.path.join(memory_dir(cwd), "spec", "*", "workflow-state.md")):
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if now - m <= RECENT_S and is_complete_state(p):
            found.append((m, p))
    return [p for _m, p in sorted(found, reverse=True)]


def _stall_reason(title, phase, next_phase):
    return (f"SDD workflow stalled: '{title}'. Phase {phase} is approved but {next_phase} has not "
            f"been entered; the orchestrator likely gave guidance and ended its turn. Invoke the "
            f"{next_phase} phase now (or run /isdd-continue) before ending the turn.")


def _backstop_reason(items):
    lines = ["SDD completion backstop: feature(s) marked Complete have high-risk slice(s) with no "
             "independent code-reviewer evidence. Run the review, or record `Accepted via "
             "AskUserQuestion: <slice ids | all>: <reason>` as the Review Fallback, or set "
             "Workflow Status back from Complete."]
    lines += [f"- '{title}': slice(s) {', '.join(ids)}" for title, ids in items]
    return "\n".join(lines)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    active = bool(payload.get("stop_hook_active"))
    reasons = []
    try:
        board = _plan_board_gate(payload, cwd)
    except Exception:
        board = ""                     # best-effort: never break Stop over the board
    if board:
        reasons.append(board)

    reminder = None
    state = active_state_file(cwd)
    if state:
        _write_last_stop_marker(cwd)
        f = parse_state(state)
        title = f.get("title", "the active feature")
        status = f.get("workflow status", "").lower()
        feature_dir = os.path.dirname(state)
        if "block" in status or "await" in status or "confirm" in status:
            pause_reason = f.get("pause reason", "").strip()
            next_action = f.get("next action", "").strip()
            if pause_reason and next_action:
                detail = f"{pause_reason}. Next: {next_action}"
            else:
                detail = pause_reason or next_action or "see workflow-state.md"
            reminder = (f"SDD reminder: '{title}' is paused ({f.get('workflow status', '?')}) — "
                        f"{detail}. Run /isdd-continue when ready.")
        elif not active:
            try:
                stall = detect_stall(f, feature_dir)
                if stall:
                    req = parse_state(os.path.join(feature_dir, "requirements", "requirements.md"))
                    digest = f"{stall[0]}|{req.get('state', '')}|{status}"
                    if _once_per_change(cwd, "stall:" + state, digest):
                        reasons.append(_stall_reason(title, stall[0], stall[1]))
            except Exception:
                pass                   # best-effort: fail open

    if not active:
        try:
            items = []
            for done in _recent_complete_states(cwd):
                ids = review_tracking.unreviewed_high_risk(os.path.dirname(done))
                if ids and _once_per_change(cwd, "backstop:" + done, ",".join(sorted(ids))):
                    items.append((parse_state(done).get("title", os.path.basename(os.path.dirname(done))), ids))
            if items:
                reasons.append(_backstop_reason(items))
        except Exception:
            pass

    if reasons and not active:
        print(json.dumps({"decision": "block", "reason": "\n\n".join(reasons)}))
    elif reminder:
        print(json.dumps({"systemMessage": reminder}))
    sys.exit(0)


if __name__ == "__main__":
    main()
