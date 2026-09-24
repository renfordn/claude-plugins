#!/usr/bin/env python3
"""PreToolUse gate: deny Write/Edit/MultiEdit whose target path resolves under
sdd_memory.py's BASE (`<memory root>/sdd-memory/<X>/` -- the shared_memory_root
plugin option when set, else `${CLAUDE_PLUGIN_DATA}`; not the legacy bare
`~/.claude/sdd-memory/`) when X doesn't match the canonical project_slug(cwd) or
the literal "global" directory. With a shared root configured, any write under
the (now stale) `${CLAUDE_PLUGIN_DATA}/sdd-memory/` copy is denied as well.

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
from sdd_memory import BASE, LOCAL_BASE, project_slug  # noqa: E402


def _slug_pattern(base):
    return re.compile(
        r"^" + re.escape(os.path.normpath(base)) + re.escape(os.sep) + r"([^" + re.escape(os.sep) + r"]+)"
    )


_SLUG_PATTERN = _slug_pattern(BASE)
# Only set when a shared memory root is configured (BASE then differs from LOCAL_BASE): the
# ${CLAUDE_PLUGIN_DATA} copy of sdd-memory is stale from then on, so writes there are denied.
_LOCAL_PATTERN = (
    _slug_pattern(LOCAL_BASE) if os.path.normpath(LOCAL_BASE) != os.path.normpath(BASE) else None
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

    if _LOCAL_PATTERN is not None and _LOCAL_PATTERN.match(norm):
        deny(
            f"SDD memory slug guard: '{norm}' is under the local ${{CLAUDE_PLUGIN_DATA}} "
            f"sdd-memory ({LOCAL_BASE}), but a shared memory root is configured, so the live "
            f"store is {BASE}. Resolve the path via 'hooks/sdd_memory.py --spec-path' (passing "
            f"CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT) and use its output verbatim. To bring "
            f"old local state across, run scripts/merge_plugin_data.py."
        )

    m = _SLUG_PATTERN.match(norm)
    if not m:
        no_decision()  # not under <memory root>/sdd-memory/ at all

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
