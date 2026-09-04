#!/usr/bin/env python3
"""SDD statusline: shows the active feature's phase and status in the status bar.

Self-contained (no plugin imports) so it works wherever settings.json points it.
Wire it in ~/.claude/settings.json:

  "statusLine": {
    "type": "command",
    "command": "python3 /ABSOLUTE/PATH/TO/spec-driven-development/statusline/sdd_statusline.py"
  }

Prints e.g.  SDD ▸ Design ▸ Awaiting Confirmation   (nothing when no workflow).
This is the terse always-on macro breadcrumb; the fuller per-phase/slice tick
list lives in the harness's own task tracker (see INTEROP.md's "-> agent-ux
(UX rendering)" section), not here.
"""
import glob
import json
import os
import re
import sys


def newest_state(cwd):
    files = glob.glob(os.path.join(cwd, "spec", "*", "workflow-state.md"))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0] if files else None


def field(text, name):
    m = re.search(rf"^\s*[-*]\s*{re.escape(name)}:\s*(.+?)\s*$", text, re.M | re.I)
    return m.group(1).strip() if m else ""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    ws = data.get("workspace") or {}
    cwd = ws.get("current_dir") or data.get("cwd") or os.getcwd()

    state = newest_state(cwd)
    if not state:
        sys.exit(0)  # no workflow -> empty statusline segment
    try:
        with open(state, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        sys.exit(0)

    phase = field(text, "Current Phase") or "?"
    status = field(text, "Workflow Status") or "?"
    line = f"SDD ▸ {phase} ▸ {status}"
    if phase == "Implementation":
        stage = field(text, "Implementation Stage")
        if stage:
            line += f" ▸ Stage: {stage}"
    print(line)


if __name__ == "__main__":
    main()
