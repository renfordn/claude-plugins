#!/usr/bin/env python3
"""PreToolUse gate: deny a `Write` of a `file-summary`/`folder-summary`
entry (`entries/<name>.md` under Agent Nelly's memory store) whose
`description` exceeds `nelly_memory.SUMMARY_CHAR_LIMIT` (240) characters.

Rationale: the whole point of the file/folder summary cache (see
references/nelly-entry.template.md and agent-nelly.md's "File & Folder
Summary Cache" section) is a smaller place to look first instead of
grepping the whole repo -- a summary long enough to need its own scrolling
defeats that. Mirrors nelly_slug_guard.py's approach: make the cap
structural instead of relying solely on instructions telling the caller to
count characters itself.

Scoped to `Write` only, not `Edit`/`MultiEdit`: a `Write` payload carries the
full intended file content, so the resulting `description` can be checked
directly. An `Edit`/`MultiEdit` payload carries only `old_string`/
`new_string` fragments -- reconstructing the resulting frontmatter from
those would mean reading the current file from inside a hook for a check
this narrow, so those tool calls are left to `no_decision()` (matching this
plugin's existing discipline of not growing a hook's own file-I/O surface
beyond its one job -- see nelly-staleness.md's "does not add a new Bash
invocation" note for the same discipline applied elsewhere). In practice
every `file-summary`/`folder-summary` entry is authored with `Write`
(they're generated content, not hand-edited in place), so this covers the
real write path.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import BASE, LOCAL_BASE, SUMMARY_CHAR_LIMIT  # noqa: E402

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_TYPE_RE = re.compile(r"^\s*type:\s*(\S+)", re.M)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_CAPPED_TYPES = ("file-summary", "folder-summary")


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


def _under_memory_store(norm):
    for base in (BASE, LOCAL_BASE):
        prefix = os.path.normpath(base) + os.sep
        if norm.startswith(prefix):
            return True
    return False


def main():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        allow()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    if payload.get("tool_name") != "Write":
        no_decision()  # Edit/MultiEdit don't carry full content -- see module docstring

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    content = tool_input.get("content")
    if not file_path or content is None:
        no_decision()

    cwd = payload.get("cwd") or os.getcwd()
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    norm = os.path.normpath(abspath)

    if not norm.endswith(".md") or (os.sep + "entries" + os.sep) not in norm:
        no_decision()
    if not _under_memory_store(norm):
        no_decision()

    match = _FRONTMATTER_RE.search(content)
    if not match:
        no_decision()
    block = match.group(1)

    type_m = _TYPE_RE.search(block)
    if not type_m or type_m.group(1).strip() not in _CAPPED_TYPES:
        no_decision()

    desc_m = _DESCRIPTION_RE.search(block)
    description = desc_m.group(1).strip() if desc_m else ""
    if len(description) > SUMMARY_CHAR_LIMIT:
        deny(
            f"Agent Nelly summary guard: '{os.path.basename(norm)}' is a "
            f"{type_m.group(1).strip()} entry whose description is "
            f"{len(description)} characters, over the {SUMMARY_CHAR_LIMIT}-character "
            f"cap. Shorten it (or run it through "
            f"nelly_memory.truncate_summary()) before writing -- the cache "
            f"only stays useful as a smaller place to look first if every "
            f"summary in it stays scannable at a glance."
        )

    no_decision()


if __name__ == "__main__":
    main()
