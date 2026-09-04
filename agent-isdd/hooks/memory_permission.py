#!/usr/bin/env python3
"""PreToolUse hook: auto-approve Read/Write/Edit/MultiEdit whose target path
resolves strictly under this project's per-feature spec state
(~/.claude/sdd-memory/<project-slug>/spec/**).

Rationale: this plugin owns and generates that per-feature scaffolding
(workflow-state.md, recap.md, requirements/design/tasks — see spec_dir() in
sdd_memory.py) itself, so it should never stall on a permission prompt for a
path it created and scoped. Central, cross-feature memory files
(PROJECT-MEMORY.md, TDD-MEMORY.md, scholar-memory.md, GLOBAL-MEMORY.md, and
the global/ tier generally) are not this plugin's domain — that
responsibility belongs to the agent-nelly plugin — so this hook does not
auto-approve them. Nothing outside spec/** is affected by this hook — every
other path falls through to the harness's normal permission prompting
untouched.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_memory import spec_dir  # noqa: E402


def allow(reason=None):
    out = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }}
    if reason:
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    print(json.dumps(out))
    sys.exit(0)


def no_decision():
    # No output at all -> defer to normal permission handling.
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        no_decision()

    cwd = payload.get("cwd") or os.getcwd()
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    norm = os.path.normpath(abspath)

    spec_root = os.path.normpath(spec_dir(cwd))
    if norm == spec_root or norm.startswith(spec_root + os.sep):
        allow(f"SDD memory permission: {norm} is under the project's per-feature "
              f"spec state, generated and owned by this plugin.")

    no_decision()


if __name__ == "__main__":
    main()
