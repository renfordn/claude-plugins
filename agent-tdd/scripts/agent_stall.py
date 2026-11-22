#!/usr/bin/env python3
"""Check whether a background subagent has stalled.

    python3 agent_stall.py (--agent-id <id> | --transcript <path>) [--idle-minutes 20]

Reads the subagent's transcript (`<config>/projects/*/*/subagents/agent-<id>.jsonl`), takes the
last timestamp, and lists the background Bash commands it started that are still running
(matched against `ps`), flagging any self-matching `pgrep -f` / `pkill -f` wait loop.

Prints one JSON object and exits:
  0  active   (activity within --idle-minutes)
  3  stalled  (idle past the limit while waiting on background work or with live background
              commands): resume it with a status-check message, or tell the user
  4  idle     (idle past the limit with no sign of background work: probably finished; read its
              report, or the worktree / git log / test logs if the report never arrived)
  2  transcript not found or unreadable
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import wait_loop_guard  # noqa: E402

WAITING = re.compile(r"\b(waiting|wait for|background)\b", re.I)


def find_transcript(agent_id):
    root = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    aid = agent_id[len("agent-"):] if agent_id.startswith("agent-") else agent_id
    hits = glob.glob(os.path.join(root, "projects", "*", "*", "subagents", "agent-%s.jsonl" % aid))
    return max(hits, key=os.path.getmtime) if hits else None


def _ts(value):
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def read_transcript(path):
    """(last timestamp, last assistant text, background Bash commands) from a jsonl transcript."""
    last, text, background = None, "", []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            last = _ts(obj.get("timestamp")) or last
            msg = obj.get("message") or {}
            if obj.get("type") != "assistant" or not isinstance(msg.get("content"), list):
                continue
            for part in msg["content"]:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text", "").strip():
                    text = part["text"].strip()
                elif part.get("type") == "tool_use" and part.get("name") == "Bash":
                    inp = part.get("input") or {}
                    if inp.get("run_in_background") and isinstance(inp.get("command"), str):
                        background.append(inp["command"])
    return last, text, background


def live_processes():
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if pid.isdigit():
            rows.append((int(pid), cmd.strip()))
    return rows


def assess(path, idle_minutes, now=None, processes=None):
    last, text, background = read_transcript(path)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    procs = live_processes() if processes is None else processes
    me = os.getpid()
    commands = []
    for cmd in background:
        key = cmd.strip()[:80]
        pids = [p for p, c in procs if key and key in c and p != me]
        hit = wait_loop_guard.self_matching(cmd)
        commands.append({"command": cmd[:200], "live_pids": pids,
                         "self_matching_wait": "%s -f %s" % hit if hit else None})
    idle = round((now - last).total_seconds() / 60, 1) if last else None
    live = any(c["live_pids"] for c in commands)
    waiting = bool(WAITING.search(text[-400:]))
    if idle is not None and idle < idle_minutes:
        status, advice = "active", "Still working; check again later."
    elif live or waiting:
        status = "stalled"
        advice = ("Idle %s min while waiting on background work. Resume it with a status-check "
                  "message (SendMessage: 'Status check: report what you are waiting on; stop any "
                  "self-matching pgrep -f loop and rerun the command in the foreground'), or tell "
                  "the user. Kill dead-end wait loops listed under self_matching_wait." % idle)
    else:
        status = "idle"
        advice = ("No activity for %s min and no background work: it has probably finished. "
                  "If its report never arrived, read the worktree, git log and test logs." % idle)
    return {"status": status, "transcript": path,
            "last_activity": last.isoformat() if last else None, "idle_minutes": idle,
            "last_text": text[-300:], "background_commands": commands, "advice": advice}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--agent-id")
    src.add_argument("--transcript")
    ap.add_argument("--idle-minutes", type=float, default=20)
    args = ap.parse_args(argv)
    path = args.transcript or find_transcript(args.agent_id)
    if not path or not os.path.isfile(path):
        print(json.dumps({"status": "not_found", "agent_id": args.agent_id,
                          "transcript": args.transcript}))
        return 2
    result = assess(path, args.idle_minutes)
    print(json.dumps(result, indent=2))
    return {"active": 0, "stalled": 3, "idle": 4}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
