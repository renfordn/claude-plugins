# Consolidation write-back

Read by `agents/nelly-maintenance.md` when invoked via `/nelly-memory consolidate`.


Only runs when invoked via `/nelly-memory consolidate` (Phase 8), never
autonomously during brief assembly.

1. Review the project's entries (via `Grep`/`Read` over `entries/*.md`) for
   pairs/groups whose `description` and body clearly describe the same
   underlying fact from different angles (e.g. "retry on flaky network
   calls" and "backoff strategy for HTTP timeouts" both describing
   retry-with-exponential-backoff for transient failures).
2. Propose and write **one new merged entry** under `entries/` with a
   **new** kebab-case `name` that doesn't reuse either original filename
   (e.g. `retry-with-exponential-backoff-for-transient-failures.md`),
   reconciling both originals' content into one coherent body, and linking
   back conceptually rather than duplicating shared context.
3. Move **both** original entries to `archive/` using
   `references/nelly-file-move.md`'s mechanism. Both files must remain fully readable at their new
   archive paths — this operation never deletes information, only
   relocates and supersedes it.
4. Update the project's `MEMORY.md` index: produce a field-annotated index
   line for the new merged entry (`type`, `confidence` if present, `files`
   if present, sourced from the merged entry's own frontmatter) following
   the format `hooks/nelly_memory.py`'s `write_index_line()` now defines,
   add that line, remove the two originals' lines, leave every other line
   untouched.
5. Append **exactly one** new log block to the project's consolidation log
   (`<memory_dir>/CONSOLIDATION-LOG.md`, created from
   `references/GLOBAL-CONSOLIDATION-LOG.md.template`'s shape if it doesn't
   exist yet — same append-only discipline, per-project rather than global
   since consolidation is a per-project operation):
   - `Action: consolidated`
   - `Merged Entries:` both original names, comma-separated
   - `Result Entry:` the new merged entry's name
   - `Reason:` why these were judged near-duplicates and how the merged
     entry reconciles them
   - `Trigger: user request via /nelly-memory consolidate`
6. Never touch any prior content already in the consolidation log — append
   only, one new block per consolidation action.
7. Report the merge in `Written`.

This log file is shared with `agent-nelly.md`'s "Supersession write-back", which appends
`Action: superseded` blocks to the same per-project `CONSOLIDATION-LOG.md`
alongside these `Action: consolidated` blocks — both append-only, never
editing or removing the other's prior entries.

