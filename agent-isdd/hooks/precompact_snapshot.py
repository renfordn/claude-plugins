#!/usr/bin/env python3
"""PreCompact hook: snapshot in-progress workflow-state + recap before context
compaction, so long SDD workflows survive it. Writes to the central memory store.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_state import find_state_files  # noqa: E402
from sdd_memory import memory_dir  # noqa: E402


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    states = find_state_files(cwd)
    if not states:
        sys.exit(0)  # nothing worth snapshotting

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snap_dir = os.path.join(memory_dir(cwd), "snapshots")
    out = [f"# SDD pre-compact snapshot — {ts}",
           f"Project: {os.path.abspath(cwd)}",
           f"Trigger: {payload.get('trigger', 'unknown')}", ""]

    hook_notes = []
    for s in states[:5]:
        out.append(f"## {os.path.relpath(s, cwd)}\n\n```\n{read(s)}\n```\n")
        recap = os.path.join(os.path.dirname(s), "recap", "recap.md")
        if os.path.isfile(recap):
            out.append(f"### recap\n\n{read(recap)}\n")

    if hook_notes:
        out.append("## Hook notes\n\n" + "\n".join(f"- {n}" for n in hook_notes) + "\n")

    path = os.path.join(snap_dir, f"precompact-{ts}.md")
    try:
        os.makedirs(snap_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    except OSError:
        sys.exit(0)

    msg = f"SDD: snapshotted workflow state to {path} before compaction."
    if hook_notes:
        msg += " Hook notes: " + "; ".join(hook_notes)
    print(json.dumps({"systemMessage": msg}))
    sys.exit(0)


if __name__ == "__main__":
    main()
