#!/usr/bin/env python3
"""PreToolUse gate: deny a `Write` of a research-digest entry
(`entries/<DIGEST_SUBDIR>/<name>.md` under Agent Nelly's memory store) whose body -- the text
after the frontmatter block -- exceeds `nelly_memory.DIGEST_CHAR_LIMIT` (2,000) characters.

Digests are normally written by scripts/research_digest.py, which hashes the sources, truncates
the body deterministically, and writes atomically -- none of which goes through the Write tool.
This guard makes the cap structural for a digest written by hand instead. One guard per concern,
same shape as nelly_summary_guard.py (Write only: an Edit/MultiEdit payload doesn't carry the
full resulting content).

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable entirely; the guard
then returns no decision (it never emits "allow", so disabling it can't widen permissions).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import BASE, LOCAL_BASE, DIGEST_CHAR_LIMIT, DIGEST_SUBDIR  # noqa: E402

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)


def _emit(decision, reason=None):
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision}}
    if reason:
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    print(json.dumps(out))
    sys.exit(0)


def no_decision():
    sys.exit(0)


def _under_memory_store(norm):
    return any(norm.startswith(os.path.normpath(base) + os.sep) for base in (BASE, LOCAL_BASE))


def main():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        no_decision()  # disabled: step aside, never widen permissions with an "allow"

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    if payload.get("tool_name") != "Write":
        no_decision()

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    content = tool_input.get("content")
    if not file_path or content is None:
        no_decision()

    cwd = payload.get("cwd") or os.getcwd()
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    norm = os.path.normpath(abspath)
    digest_segment = os.sep + os.path.join("entries", DIGEST_SUBDIR) + os.sep
    if not norm.endswith(".md") or digest_segment not in norm or not _under_memory_store(norm):
        no_decision()

    match = _FRONTMATTER_RE.search(content)
    body = (content[match.end():] if match else content).strip()
    if len(body) > DIGEST_CHAR_LIMIT:
        _emit("deny",
              f"Agent Nelly digest guard: '{os.path.basename(norm)}' is a research-digest whose "
              f"body is {len(body)} characters, over the {DIGEST_CHAR_LIMIT}-character cap. "
              f"Write digests through scripts/research_digest.py write (it truncates "
              f"deterministically and records source hashes) or shorten the body.")

    no_decision()


if __name__ == "__main__":
    main()
