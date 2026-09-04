#!/usr/bin/env python3
"""PreToolUse gate: deny Write/Edit/MultiEdit whose target path resolves
under ~/.claude/agent-nelly-memory/<X>/ when X doesn't match the canonical
project_slug(cwd) or the literal "global" directory.

Rationale: nothing should hand-compute or approximate a project slug instead
of using nelly_memory.py's canonical resolver. This hook makes the correct
behavior structural instead of relying solely on instructions: any write to
a wrong-slug agent-nelly-memory path is denied outright, regardless of what
wrote it or why.

Separate from nelly_memory_permission.py on purpose: that file's entire
contract is "only ever allow or no-op" (auto-approve legitimate memory
paths). Bolting a deny path onto it would blur its one job. This hook has
exactly one job: reject wrong-slug agent-nelly-memory paths.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import BASE, project_slug  # noqa: E402

_SLUG_PATTERN = re.compile(
    r"^" + re.escape(os.path.normpath(BASE)) + re.escape(os.sep) + r"([^" + re.escape(os.sep) + r"]+)"
)


def allow(reason=None):
    out = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }}
    if reason:
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    print(json.dumps(out))
    sys.exit(0)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def no_decision():
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

    m = _SLUG_PATTERN.match(norm)
    if not m:
        no_decision()  # not under ~/.claude/agent-nelly-memory/ at all

    segment = m.group(1)
    if segment == "global":
        no_decision()  # global tier is exempt, let nelly_memory_permission.py allow it

    canonical = project_slug(cwd)
    if segment == canonical:
        no_decision()  # correct slug, let nelly_memory_permission.py allow it

    deny(
        f"Agent Nelly slug guard: '{norm}' targets agent-nelly-memory project "
        f"directory '{segment}', but the canonical directory for cwd '{cwd}' is "
        f"'{canonical}' (or 'global' for the cross-project tier). This looks like "
        f"a hand-computed or approximated slug rather than one resolved via "
        f"hooks/nelly_memory.py -- resolve the path via "
        f"'python3 hooks/nelly_memory.py --path' and use its output verbatim "
        f"instead."
    )


if __name__ == "__main__":
    main()
