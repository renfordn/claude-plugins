# Shared: file-move mechanism

Extracted from `agents/agent-nelly.md` so `agents/nelly-maintenance.md` can reuse it without
duplicating the prose. Read this file when a task requires archiving an entry: supersession or
discard (`agent-nelly`), or staleness flagging / consolidation (`nelly-maintenance`).

## File-move mechanism (shared by staleness flagging, consolidation, and supersession)

To "move" `entries/<name>.md` to `archive/<name>.md`, use `Bash` to run a
literal, atomic move:

```
mkdir -p "<memory_dir>/archive" && mv "<memory_dir>/entries/<name>.md" "<memory_dir>/archive/<name>.md"
```

This, and running `python3 hooks/nelly_memory.py --entries-path [cwd]` to
guarantee `entries/` exists before a new/overwritten entry is written (see
`agent-nelly.md`'s "Recording a new fact" and
`references/nelly-import.md`'s "Import"), are the only uses `Bash` is put to
by either `agent-nelly` or `nelly-maintenance` — a minimal, justified
addition to the toolset for exactly these two operations. `mv` is
atomic and content-preserving: the file's full content is never destroyed,
only relocated to `archive/<name>.md`, where it remains fully readable and
recoverable (moving it back is the same command in reverse). This is not a
delete — "archive, not delete" is satisfied by the file still existing,
intact, at the new path.

Using a real move (not a copy-then-overwrite/tombstone) matters beyond
"never delete": `entries/` must reflect only currently-live entries,
because `list_entries(cwd)` (`hooks/nelly_memory.py`) and Phase 5's
`nelly_session_start.py` both read `entries/` directly to decide what to
surface. A copy left behind at the old path — even a placeholder — would
still show up in `list_entries()` and get announced at `SessionStart` as if
it were current. A real `mv` is the only mechanism that keeps `entries/`
accurate.

After this mechanism runs: `entries/<name>.md` no longer exists,
`archive/<name>.md` holds the complete, unmodified original.

