# Shared: file-move mechanism

Extracted from `agents/agent-nelly.md` so `agents/nelly-maintenance.md` can reuse it without
duplicating the prose. Read this file when a task requires archiving an entry: supersession or
discard (`agent-nelly`), or staleness flagging / consolidation (`nelly-maintenance`).

## File-move mechanism (shared by staleness flagging, consolidation, and supersession)

To "move" `entries/<name>.md` to `archive/<name>.md`, use `Bash` to run a
literal, atomic move:

```
mkdir -p "<memory_dir>/archive" && mv -n "<memory_dir>/entries/<name>.md" "<memory_dir>/archive/<name>.md"
```

`mv -n` never overwrites: if `archive/<name>.md` already exists (an earlier archive of the same
name) it moves nothing. Check that `entries/<name>.md` is gone afterwards; if it is still there,
repeat the move to a unique name, e.g. `archive/<name>.<YYYYMMDD>.md`, instead of overwriting the
older archive (the weekly consolidation script does the same with `<name>.2.md`, `<name>.3.md`).

This, running `python3 hooks/nelly_memory.py --entries-path [cwd]` to
guarantee `entries/` exists before a new/overwritten entry is written (see
`agent-nelly.md`'s "Recording a new fact" and
`references/nelly-import.md`'s "Import"), and the R5 scripts
`nelly_evidence.py` (`record`, `refresh`, `stale`) and `nelly_pending.py`
(`add`, `list`, `resolve`), run with the env prefix and absolute script path
shown in the SessionStart line (`CLAUDE_PLUGIN_ROOT` is unset in Bash), are the
only uses `Bash` is put to by either `agent-nelly` or `nelly-maintenance`.
`mv` is
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

