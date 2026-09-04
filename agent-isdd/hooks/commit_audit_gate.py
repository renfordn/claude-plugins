#!/usr/bin/env python3
"""PreToolUse gate: deny `git commit` in this plugin's own repo unless the
doc-consistency-auditor has already run clean against the currently staged
diff.

Enforces the "audit before commit" rule structurally: the hook only decides
allow/deny, it never judges content itself (that's doc-consistency-auditor's
job, an LLM-driven skill -- hooks can't reason semantically). Uses the same
SDD_GATE=off escape-hatch convention as the (now-external) sdd plugin's own
gate hooks used.

Scoped to this plugin specifically: no-ops immediately for any repo that
doesn't have skills/, agents/, commands/, and hooks/ at its root, so this
hook never affects commits in unrelated repositories even though it's
registered globally via this plugin's hooks.json.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_memory import memory_dir  # noqa: E402
from diff_fingerprint import compute as compute_fingerprint  # noqa: E402

_COMMIT_RE = re.compile(r"(?:^|[;&|]\s*)git\s+commit\b")
_TRACKED_DIRS = ("skills", "agents", "commands", "hooks")


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


def _looks_like_this_plugin(repo_root):
    return all(os.path.isdir(os.path.join(repo_root, d)) for d in _TRACKED_DIRS)


def _parse_state(path):
    """Parse DOC-AUDIT-STATE.md's `- Field: value` lines into a dict.

    Same lightweight convention as sdd_state.parse_state, values may be
    backtick-wrapped in this file's template so strip those too.
    """
    fields = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return fields
    for line in text.splitlines():
        m = re.match(r"\s*-\s*([A-Za-z][A-Za-z ]+?):\s*`?([^`]*)`?\s*$", line)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if key not in fields:
                fields[key] = val
    return fields


def main():
    if os.environ.get("SDD_GATE", "").lower() in ("off", "0", "false", "disabled"):
        allow()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    if not command or not _COMMIT_RE.search(command):
        no_decision()  # not a git commit invocation

    cwd = payload.get("cwd") or os.getcwd()
    if not _looks_like_this_plugin(cwd):
        no_decision()  # not this plugin's repo, this gate doesn't apply

    current_fp = compute_fingerprint(cwd)
    if current_fp is None:
        allow("SDD doc-audit gate: nothing staged under skills/agents/commands/hooks, "
              "nothing to audit.")

    state_path = os.path.join(memory_dir(cwd), "DOC-AUDIT-STATE.md")
    fields = _parse_state(state_path)
    status = fields.get("status", "")
    recorded_fp = fields.get("diff fingerprint", "")

    if status == "passed" and recorded_fp == current_fp:
        allow("SDD doc-audit gate: doc-consistency-auditor already ran clean against this "
              "exact staged diff.")

    deny(
        "SDD doc-audit gate: doc-consistency-auditor has not run against the currently "
        "staged skills/agents/commands/hooks diff (or its last run is stale/blocked). "
        "Run the doc-consistency-auditor skill, then retry this commit.\n"
        f"Current status: '{status or 'none recorded'}'. "
        "To bypass for one-off work: SDD_GATE=off in the environment."
    )


if __name__ == "__main__":
    main()
