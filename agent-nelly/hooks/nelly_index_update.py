#!/usr/bin/env python3
"""PostToolUse hook: keep nelly-index.json fresh after every Write/Edit/
MultiEdit that touches Agent Nelly's memory store, so nelly-orchestrator can
read one JSON file instead of opening every entries/*.md file.

Three path shapes matter here, matched purely from the written path (see
scripts/build_index.py for the actual index logic -- this hook is a thin
dispatcher over it):

  - <memory_dir>/entries/<name>.md  -> lightweight upsert of that one entry
    (scripts/build_index.py::upsert_project_entry). This is the common case
    -- most write-back paths in nelly-orchestrator.md write or edit exactly
    one entry file.
  - <memory_dir>/MEMORY.md          -> full rescan of that project's store
    (scripts/build_index.py::build_project_index). Every write-back path
    that archives an entry (staleness flagging, consolidation, supersession)
    edits MEMORY.md right after its Bash `mv` -- a move this hook never sees
    directly, since it only fires on Write/Edit/MultiEdit. Rescanning
    entries/ (the source of truth) on every MEMORY.md edit is what actually
    catches that drift; the entry-file upsert path above cannot, since a
    moved file no longer exists at its old entries/<name>.md path for the
    hook to even observe.
  - <BASE>/global/GLOBAL-MEMORY.md  -> full rescan of the global index
    (scripts/build_index.py::build_global_index) -- a single-file read, so
    "full" is already the cheap, minimal operation here.

Anything else (including every non-Nelly Write/Edit/MultiEdit in any other
project) is a silent no-op -- this hook fires on every Write/Edit/MultiEdit
in the session, so the non-matching path must stay fast and quiet.

Never blocks or reports failure back to the tool call: PostToolUse cannot
undo a write that already happened, and an index rebuild failure must never
surface as if the underlying Write/Edit itself failed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from nelly_memory import memory_dir, global_dir  # noqa: E402
import build_index  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    norm = os.path.normpath(abspath)

    try:
        global_memory_path = os.path.normpath(os.path.join(global_dir(), "GLOBAL-MEMORY.md"))
        if norm == global_memory_path:
            build_index.build_global_index()
            sys.exit(0)

        mem_root = os.path.normpath(memory_dir(cwd))
        if not (norm == mem_root or norm.startswith(mem_root + os.sep)):
            sys.exit(0)  # not under this project's memory store at all

        entries_dir = os.path.join(mem_root, "entries") + os.sep
        if norm.startswith(entries_dir) and norm.endswith(".md"):
            build_index.upsert_project_entry(cwd, norm)
        elif norm == os.path.join(mem_root, "MEMORY.md"):
            build_index.build_project_index(cwd)
        # Any other path under the store (archive/, CONSOLIDATION-LOG.md,
        # etc.) carries no index-relevant content -- silent no-op.
    except OSError:
        pass  # index refresh is best-effort; never fail the underlying write

    sys.exit(0)


if __name__ == "__main__":
    main()
