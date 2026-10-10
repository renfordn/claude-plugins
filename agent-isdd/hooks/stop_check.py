#!/usr/bin/env python3
"""Stop hook: non-blocking reminder when the active workflow is paused or stalled.

Detects two conditions:
1. Explicit pause: workflow status contains "block", "await", or "confirm"
2. Mid-workflow stall: a phase marked Complete but next phase not yet entered

Blocks the stop only for the Plan Board gate (_plan_board_gate), once per changed record.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import active_state_file, parse_state  # noqa: E402
from sdd_memory import local_state_dir, memory_dir  # noqa: E402


PHASE_ORDER = ["Requirements", "Design", "Tasks"]  # Expected phase progression
PHASE_FILES = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
    "Tasks": "tasks/tasks.md",
}
# Phases that have a completion gate of their own (an artifact with a `- State:` field the
# orchestrator sets to Approved). Tasks has no such artifact-level gate here -- see
# workflow-manager's `continue` row: `Current Phase: Tasks` only ever arises as a rollback
# landing state, not a phase this hook watches for stalling out of.
PHASE_ARTIFACT_FILE = {
    "Requirements": "requirements/requirements.md",
    "Design": "design/design.md",
}


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


def _detect_stalled_phase(state_fields, feature_dir):
    """Check if the current phase's own artifact is Approved but the next phase hasn't
    been entered.

    `Workflow Status: Complete` is NOT the per-phase completion signal -- per
    workflow-manager's contract it is set only once, at the whole feature's final
    handoff/completion, never for an individual phase finishing mid-workflow. The real
    per-phase signal is the phase artifact's own `- State: Approved` field (set by
    requirements-agent/design-author immediately on approval), which is exactly what stays
    true while the orchestrator has provided guidance at a phase boundary and stalled before
    invoking the next phase in the same turn.

    Returns (is_stalled, phase_name, next_phase) or (False, None, None).
    """
    current = state_fields.get("current phase", "").strip()

    # Find current phase in order
    for i, phase in enumerate(PHASE_ORDER):
        if current.startswith(phase):
            artifact_file = PHASE_ARTIFACT_FILE.get(phase)
            if artifact_file and i + 1 < len(PHASE_ORDER):
                artifact_path = os.path.join(feature_dir, artifact_file)
                artifact_state = parse_state(artifact_path).get("state", "").strip().lower()
                if artifact_state == "approved":
                    next_phase = PHASE_ORDER[i + 1]
                    next_file = os.path.join(feature_dir, PHASE_FILES[next_phase])
                    if not os.path.exists(next_file):
                        # Phase's artifact approved but next phase not entered — stalled
                        return (True, phase, next_phase)
            break

    return (False, None, None)


RECENT_S = 24 * 3600
NUDGED_FILE = "plan-board-stop-nudged.json"


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
    nudged_path = os.path.join(local_state_dir(project_cwd), NUDGED_FILE)
    try:
        with open(nudged_path, "r", encoding="utf-8") as fh:
            nudged = json.load(fh)
        nudged = nudged if isinstance(nudged, dict) else {}
    except (OSError, ValueError):
        nudged = {}
    due = []
    for slug, path, doc in plan_board.stale_features(mem, project):
        recent = False
        for f in (path, os.path.join(os.path.dirname(path), "impl-progress.json")):
            try:
                recent = recent or now - os.path.getmtime(f) <= RECENT_S
            except OSError:
                pass
        h = plan_board.content_hash(doc)
        if recent and nudged.get(doc["id"]) != h:
            due.append((slug, path, doc))
            nudged[doc["id"]] = h
    if not due:
        return ""
    try:
        os.makedirs(os.path.dirname(nudged_path), exist_ok=True)
        with open(nudged_path, "w", encoding="utf-8") as fh:
            json.dump(nudged, fh)
    except OSError:
        pass
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


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    try:
        reason = _plan_board_gate(payload, cwd)
    except Exception:
        reason = ""                    # best-effort: never break Stop over the board
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)
    state = active_state_file(cwd)
    if not state:
        sys.exit(0)

    _write_last_stop_marker(cwd)

    f = parse_state(state)
    title = f.get("title", "the active feature")
    status = f.get("workflow status", "").lower()
    feature_dir = os.path.dirname(state)

    # Check for explicit pause (block/await/confirm)
    if "block" in status or "await" in status or "confirm" in status:
        pause_reason = f.get("pause reason", "").strip()
        next_action = f.get("next action", "").strip()
        if pause_reason and next_action:
            detail = f"{pause_reason}. Next: {next_action}"
        else:
            detail = pause_reason or next_action or "see workflow-state.md"
        print(json.dumps({
            "systemMessage": (
                f"SDD reminder: '{title}' is paused ({f.get('workflow status', '?')}) — "
                f"{detail}. Run /isdd-continue when ready."
            )
        }))
        sys.exit(0)

    # Check for stalled phase (completed but next not entered)
    is_stalled, phase_name, next_phase = _detect_stalled_phase(f, feature_dir)
    if is_stalled:
        print(json.dumps({
            "systemMessage": (
                f"⚠️  SDD workflow stalled: '{title}'\n\n"
                f"**Phase {phase_name} marked Complete** but **{next_phase} phase not yet entered**.\n\n"
                f"This likely means the orchestrator provided guidance/decisions and stopped its turn "
                f"before invoking the next phase. Run `/isdd-continue` to resume and advance to {next_phase}."
            )
        }))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
