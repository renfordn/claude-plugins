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

### Sourced entries: deterministic `stale` flags (any type with `metadata.sources`)

Entries that carry `metadata.sources` are judged by the `stale` flag, not by you.
`hooks/nelly_freshness.py` compares each source's recorded blob hash with the current file at every
SessionStart and writes `stale: true`, `stale_since` and `stale_paths` itself (never deleting; digests
are skipped). There is no LLM "heavily changed" judgment for these entries, and you never hand-edit
`stale`, `stale_since` or `stale_paths` (`hooks/nelly_schema_guard.py` denies it). Sources are
repo-root-relative (git toplevel), the same base the hook uses.

5. For each entry with `stale: true`, list it with its `stale_paths`. Then, per entry, one of:
   - **Archive** (never delete) via `references/nelly-file-move.md` plus the `MEMORY.md` line removal
     of step 3, only after the user confirms; tag `(stale: sources changed)`.
   - **Recheck and clear**: read the current `stale_paths` and compare them with the entry's claim.
     `refresh` only re-pins hashes; it never proves the fact. If the fact changed, rewrite the entry
     body/description first (or archive it), then run
     `nelly_evidence.py refresh --cwd <repo-root> --slug <slug> --paths <paths>`
     (re-hashes only those paths; `stale` clears only when no stale path remains). If the entry still
     holds exactly as written, add `--confirm-unchanged` to that command (refused with exit 2 for a
     stale entry that was not rewritten since it was marked). Run it with the env prefix and
     absolute script path shown in the SessionStart line (`CLAUDE_PLUGIN_ROOT` is unset in Bash);
     `nelly_evidence.py stale --cwd <repo-root>` lists every stale entry with its command.
   - **Drop vanished sources**: for a source whose file no longer exists,
     `nelly_evidence.py refresh --cwd <repo-root> --slug <slug> --drop-paths <paths>` removes it from
     `sources` (and from `metadata.files` and the `MEMORY.md` `paths:` field). Note: `refresh`
     refuses paths with uncommitted changes (exit 2).
6. Never archive a sourced entry that is not `stale: true` for a file-change reason; the age
   threshold (steps 1-4) still applies to every entry.

### Legacy file-relevance check (entries WITHOUT `sources` only)

Applies only to `file-relevance` entries that have no `metadata.sources`; additive to the age check,
under `/nelly-memory prune` only, never autonomous.

7. Resolve every path in `metadata.files` against the git toplevel of the project's `cwd`
   (`resolve_repo_relative(cwd, path)`, `hooks/nelly_memory.py`; an absolute path is a malformed
   entry: skip that path, still evaluate the rest). Check existence with `Glob` or `Read`; add no new
   `Bash` use.
8. A missing path (deleted or renamed; renames are not detected, an accepted limitation) is stale
   regardless of `last_referenced`. There is no content-change judgment on this path: a file that
   still exists is left alone (record `sources` with the `nelly_evidence.py` `record` command to get deterministic
   change detection).
9. Multiple files: archive only when **all** referenced files are gone; if some remain, do not
   archive, and note in `Written` which paths are gone and which remain.
10. Archive qualifying entries with the same `references/nelly-file-move.md` mechanism and `MEMORY.md`
    update as step 3. Reason tags on each `Written` line:
    - `(age threshold)` - step 4.
    - `(stale: sources changed)` - step 5, user-confirmed.
    - `(referenced file no longer exists)` - step 8.
