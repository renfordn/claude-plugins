#!/usr/bin/env python3
"""SessionStart hook: announce this project's per-feature SDD spec-state directory
and surface any in-progress workflow so it can be resumed."""
import datetime
import glob
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import find_state_files, parse_state  # noqa: E402
from sdd_memory import (  # noqa: E402
    SHARED_ROOT, memory_dir, local_state_dir, ensure_shared_root, write_base_pointer,
    pending_nelly_summaries,
)
import followups  # noqa: E402


def _followups_cmd():
    """Shell command for followups.py with this hook's resolved env, so a later Bash call hits
    the same memory dir."""
    env = [f"CLAUDE_PLUGIN_DATA={shlex.quote(os.environ.get('CLAUDE_PLUGIN_DATA', ''))}"]
    if SHARED_ROOT:
        env.append(f"CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT={shlex.quote(SHARED_ROOT)}")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "followups.py")
    return " ".join(env + ["python3", shlex.quote(script)])


def _followup_lines(cwd):
    try:
        followups.ingest(cwd)
    except OSError:
        pass  # best-effort, like the rest of SessionStart
    lines = []
    cmd = _followups_cmd()
    open_ = followups.open_items(cwd)
    if open_:
        lines += ["", f"{len(open_)} open review follow-up{'' if len(open_) == 1 else 's'} from "
                  f"code-reviewer (refactor / consolidation / deferred defect), in "
                  f"{followups.followups_dir(cwd)}:"]
        for fid, _, fm, title in open_[:5]:
            files = fm.get("files", "").replace(";", ", ")
            lines.append(f"- [{fm.get('kind', '?')}] {title}" + (f" — {files}" if files else "") + f" (id: {fid})")
        if len(open_) > 5:
            lines.append(f"- …and {len(open_) - 5} more (`{cmd} list`)")
        lines.append(f"When the user starts new work or asks what's next, offer these as candidates. "
                     f"Starting one: `{cmd} set <id> picked`; finished or rejected: "
                     f"`{cmd} set <id> done` / `dismissed`.")
    pending = followups.pending_nelly(cwd)
    if pending:
        lines += ["", f"{len(pending)} review follow-up{'' if len(pending) == 1 else 's'} not yet in Agent "
                  f"Nelly memory. If agent-nelly:agent-nelly is available, pass them in one `new facts` "
                  f"batch as `file-relevance` entries (files from each item's `files:` line), each "
                  f"labelled `Source: code-reviewer follow-up <path>` and noting that the file's "
                  f"`status:` says whether it is still open; then run `{cmd} recorded <id>` for each:"]
        lines += [f"- {path}" for _, path, _, _ in pending]
    return lines


def _interruption_note(cwd):
    """Best-effort, display-only: note when a pre-compact snapshot exists that is
    newer than the last recorded normal Stop, suggesting this session is
    recovering from an interruption rather than resuming cleanly. Returns ""
    when there's nothing to say (matches this hook's additive-only convention).
    """
    d = local_state_dir(cwd)
    snapshots = glob.glob(os.path.join(d, "snapshots", "*"))
    if not snapshots:
        return ""
    newest_snapshot = max(snapshots, key=os.path.getmtime)
    snapshot_mtime = os.path.getmtime(newest_snapshot)

    last_stop_path = os.path.join(d, "last-stop.json")
    last_stop_mtime = None
    if os.path.isfile(last_stop_path):
        last_stop_mtime = os.path.getmtime(last_stop_path)

    if last_stop_mtime is None or snapshot_mtime > last_stop_mtime:
        ts = datetime.datetime.fromtimestamp(snapshot_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"Note: a pre-compact snapshot exists from {ts} with no matching "
            f"normal stop since — this session may be recovering from an "
            f"interrupted prior session rather than a clean resume."
        )
    return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    lines = []

    # Always tell the session where this project's per-feature spec state lives
    # (workflow-state.md, recap.md, requirements/design/tasks), so every
    # subagent uses the literal absolute path (no env needed). Note: reads/
    # writes under spec/** are auto-approved by hooks/memory_permission.py —
    # no permission-prompt friction. Cross-feature, goal-bearing, and
    # cross-project memory lives in agent-nelly, not here.
    mem = memory_dir(cwd)
    lines.append(f"SDD per-feature state for this project: {mem}")
    if SHARED_ROOT:
        lines.append(f"(shared memory root: {SHARED_ROOT})")
    try:
        ensure_shared_root()
        write_base_pointer()
    except OSError:
        pass  # best-effort; SessionStart must never fail over this

    pending = pending_nelly_summaries(cwd)
    if pending:
        lines.append("")
        lines.append(
            f"{len(pending)} completed-feature summar{'y' if len(pending) == 1 else 'ies'} "
            f"(condensed by the weekly SDD cleanup) not yet in Agent Nelly memory. If "
            f"agent-nelly:agent-nelly is available, pass them to it in one `new facts` batch, "
            f"each labelled `Source: agent-isdd completed-feature summary <path>`, then change "
            f"`nelly_recorded: no` to `nelly_recorded: yes` in each summary's frontmatter:"
        )
        lines.extend(f"- {p}" for p in pending)

    lines.extend(_followup_lines(cwd))

    note = _interruption_note(cwd)
    if note:
        lines.append("")
        lines.append(note)

    # Surface in-progress workflows, if any.
    files = find_state_files(cwd)
    if files:
        lines.append("")
        lines.append("Active spec-driven-development workflow(s) in this repo:")
        for path in files[:5]:
            f = parse_state(path)
            title = f.get("title", os.path.basename(os.path.dirname(path)))
            phase = f.get("current phase", "?")
            status = f.get("workflow status", "?")
            nxt = f.get("next action", "")
            entry = f"- {title}: phase '{phase}', status '{status}'."
            if nxt:
                entry += f" Next: {nxt}"
            json_path = os.path.join(os.path.dirname(path), "workflow-state.json")
            entry += " workflow-state.json: present." if os.path.isfile(json_path) else " workflow-state.json: absent."
            lines.append(entry)
        lines.append("Run /sdd-status for detail, or /sdd-continue to resume.")

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}))
    sys.exit(0)


if __name__ == "__main__":
    main()
