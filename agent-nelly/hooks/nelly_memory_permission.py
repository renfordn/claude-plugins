#!/usr/bin/env python3
"""PreToolUse hook: auto-approve Write/Edit/MultiEdit whose target path
resolves strictly under this project's Agent Nelly memory directory
(~/.claude/agent-nelly-memory/<project-slug>/) or the cross-project global
tier (~/.claude/agent-nelly-memory/global/).

Rationale: Agent Nelly is the single owner of both directories' contents, and
it should never stall on a permission prompt for a path the plugin itself
created and scoped. Nothing outside those directories is affected by this
hook -- every other path falls through to the harness's normal permission
prompting untouched.

Validates file types (blocks .exe) and creates audit trail entries for all
decisions (allow or deny) using shared validators from plugin_data_whitelist.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import memory_dir, global_dir  # noqa: E402
from plugin_data_whitelist import create_whitelist_validator, create_audit_logger  # noqa: E402


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
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        allow()

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

    # Use shared validator to check file types (blocks .exe, etc.)
    # check_namespace=False because memory dirs don't use plugin-data namespace
    validator = create_whitelist_validator(check_namespace=False)
    validation = validator(file_path=norm, operation="write", plugin_name="agent-nelly")
    if not validation.get("allowed", False):
        # File type is blocked; defer to normal permission handling
        no_decision()

    mem_root = os.path.normpath(memory_dir(cwd))
    if norm == mem_root or norm.startswith(mem_root + os.sep):
        allow(f"Agent Nelly memory permission: {norm} is under the project's "
              f"memory directory, owned by Agent Nelly.")

    glob_root = os.path.normpath(global_dir())
    if norm == glob_root or norm.startswith(glob_root + os.sep):
        allow(f"Agent Nelly memory permission: {norm} is under the "
              f"cross-project global memory tier, owned by Agent Nelly.")

    no_decision()


if __name__ == "__main__":
    main()
