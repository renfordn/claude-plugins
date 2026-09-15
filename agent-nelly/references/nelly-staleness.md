# Staleness flagging (prune write-back)

Read by `agents/nelly-maintenance.md` when invoked via `/nelly-memory prune
[--threshold-days N]`.


Staleness is **never autonomous**. During a normal brief-assembly call you
never scan `metadata.last_referenced` ages and you never move anything to
`archive/` for staleness reasons — a plain brief-assembly call leaves every
entry exactly where it is, however old its `last_referenced` date is.

This section only activates when you are invoked by the `/nelly-memory
prune` command surface (Phase 8) with an explicit prune request and a
`--threshold-days` value (default 90):

1. For each entry in `entries/`, read `metadata.last_referenced` and compare
   its age in days to the threshold.
2. For every entry at or beyond the threshold, move it to `archive/` using
   `references/nelly-file-move.md`'s file-move mechanism.
3. Update the project's `MEMORY.md` index: remove the archived entry's index
   line (via `Edit`), leaving all other index lines untouched.
4. Report what was archived in `Written` (and in the reply to whichever
   command invoked you) — never hard-delete, ever, tagging each archived
   entry's `Written` line with `(age threshold)` so it's distinguishable from
   the file-change-aware reasons below.

### File-change-aware staleness (additive, `file-relevance` entries only)

This check only ever applies to entries whose `metadata.type` is
`file-relevance` — they're the only type with a `metadata.files` list. It is
additive to the age check above (steps 1-4), never a replacement: a
`file-relevance` entry is still evaluated against the age threshold exactly
as before, and every other entry type's staleness behavior is completely
unchanged by this subsection. Like the age check, this only ever runs under
`/nelly-memory prune` — it is never autonomous, never runs during a plain
brief-assembly call, and never scans anything mid-task.

5. For each `file-relevance` entry, resolve every path in its
   `metadata.files` list against the project's `cwd` using
   `resolve_repo_relative(cwd, path)`'s documented rule (Phase 2,
   `hooks/nelly_memory.py`: `os.path.normpath(os.path.join(cwd, path))`,
   raising on an absolute `path` — per `metadata.files`' own invariant that
   entries are always plain repo-relative paths, an absolute path here
   indicates a malformed entry; skip that individual path as unresolvable
   rather than guessing, and still evaluate the entry's remaining paths).
   Construct this resolution yourself using the module's documented shape,
   the same path-resolution pattern `agent-nelly.md` uses for
   `memory_dir`/`entry_path`/`archive_path` (see its "Path resolution" note) —
   do not add a new `Bash` invocation for this; check each resolved path's
   existence with `Glob` (a single-file glob against the resolved path is
   sufficient) or a direct `Read` attempt. `nelly-maintenance`'s `Bash` usage
   stays scoped to exactly the uses documented in
   `references/nelly-file-move.md` and "Import"'s entries/-exists check;
   this existence check does not grow that surface.
6. **Three outcomes per referenced file:**
   - **Deleted** — the resolved path does not exist. Flag stale
     *regardless* of `metadata.last_referenced` age, even if the entry was
     referenced today.
   - **Renamed** — cannot be reliably distinguished from deleted without
     guaranteed git history, and `nelly-maintenance` does not add
     `git log --follow` or any other new inspection surface to attempt
     rename detection (see `agent-nelly.md`'s "Explicit exclusions"
     discipline on keeping tool usage narrow, which applies here too).
     Treat a renamed file exactly like a deleted one — this is a known,
     accepted limitation, not a bug to fix later.
   - **Heavily changed** — the file still exists, but reading its current
     content (`Read`) and comparing it against what the entry's body
     actually claims shows the file no longer matches what the entry
     describes. This is the same LLM plausibility judgment already used for
     near-duplicate detection in `references/nelly-consolidation.md`'s
     "Consolidation write-back" and `agent-nelly.md`'s supersession check —
     not a diff-percentage or line-count heuristic, no invented threshold.
7. **Multiple files per entry.** When an entry's `metadata.files` lists more
   than one path, archive it only when **all** referenced files are
   deleted/renamed (per step 6). If some referenced files still exist (and
   aren't heavily changed) while others are gone, do **not** auto-archive —
   instead add a partial-staleness note to `Written` naming which paths are
   gone and which remain, e.g.: `"<name>` references 2 files; `path/a.py` no
   longer exists, `path/b.py` still does — not archived, flagged for
   review`".
8. For any `file-relevance` entry that qualifies for archiving under step 6
   (single file, or every file in a multi-file entry), move it to `archive/`
   using the exact same `references/nelly-file-move.md` mechanism as the age
   check above (step 2) — reuse it verbatim, do not invent a second
   archiving mechanism — then update `MEMORY.md` (step 3 above) exactly the
   same way.
9. **Reporting.** Extend the existing per-entry archive report line from
   step 4 above with a reason tag distinguishing all three cases so a
   reviewer can tell why an entry was archived at a glance:
   - `(age threshold)` — the pre-existing age-based reason (step 4).
   - `(referenced file no longer exists)` — deleted or renamed, per step 6.
   - `(referenced file heavily changed)` — content mismatch, per step 6.

