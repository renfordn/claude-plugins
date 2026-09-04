#!/usr/bin/env python3
"""PreToolUse gate: deny Write/Edit/MultiEdit whose target path resolves under
~/.claude/sdd-memory/<X>/ when X doesn't match the canonical project_slug(cwd)
or the literal "global" directory.

Rationale: a subagent (memory-orchestrator) has twice hand-computed or
otherwise arrived at a wrong project slug instead of using sdd_memory.py's
canonical resolver, producing a divergent directory each time -- once
requiring manual repair, once reproduced live one session later despite a
doc-only instruction fix. This hook makes the correct behavior structural
instead of relying solely on instructions: any write to a wrong-slug
sdd-memory path is denied outright, regardless of what wrote it or why.

Separate from memory_permission.py on purpose: that file's entire contract is
"only ever allow or no-op" (auto-approve legitimate memory paths). Bolting a
deny path onto it would blur its one job. This hook has exactly one job:
reject wrong-slug sdd-memory paths.

Set env SDD_GATE=off to disable entirely (same convention as commit_audit_gate.py).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_memory import BASE, project_slug  # noqa: E402

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
    if os.environ.get("SDD_GATE", "").lower() in ("off", "0", "false", "disabled"):
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
        no_decision()  # not under ~/.claude/sdd-memory/ at all

    segment = m.group(1)
    if segment == "global":
        no_decision()  # global tier is exempt, let memory_permission.py allow it

    canonical = project_slug(cwd)
    if segment == canonical:
        no_decision()  # correct slug, let memory_permission.py allow it

    deny(
        f"SDD memory slug guard: '{norm}' targets sdd-memory project directory "
        f"'{segment}', but the canonical directory for cwd '{cwd}' is "
        f"'{canonical}' (or 'global' for the cross-project tier). This looks like "
        f"a hand-computed or approximated slug rather than one resolved via "
        f"hooks/sdd_memory.py -- resolve the path via "
        f"'python3 hooks/sdd_memory.py --path' (or --global-path) and use its "
        f"output verbatim instead."
    )


if __name__ == "__main__":
    main()
