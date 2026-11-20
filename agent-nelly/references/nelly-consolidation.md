# Consolidation write-back

Read by `agents/nelly-maintenance.md` when invoked via `/nelly-memory consolidate`.


Only runs when invoked via `/nelly-memory consolidate` (Phase 8), never
autonomously during brief assembly.

0. Start with the newest weekly report (`<memory root>/agent-nelly-memory/consolidation-reports/`):
   its near-duplicate pairs are your first candidates. Also treat every `<name>--<worktree>.md`
   entry (a clash copy left when a closed worktree's store was merged in, see
   `scripts/nelly_cleanup.py`) as a candidate pair with `<name>.md`.
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

## Resolving conflict sidecars

A sidecar in `<store>/conflicts/` is content a writer would have overwritten (or could not write while the store lock was held). It is never deleted automatically. Two formats exist:

- `entries--<slug>.<UTC ts>.<pid>.md`: a compare-and-swap write found `entries/<slug>.md` already present with different content (or the lock was unavailable). The sidecar holds the hook's text.
- `<subdir>--<name sans .md>--<label>.md`: a worktree-store merge found two differing copies of a cached entry (`file-folder-summary` or `research-digest`). The newest copy kept the canonical name; the sidecar holds the older one.

- `hotspots.<ts>.<pid>.json` and `nelly-index.<ts>.<pid>.json`: a corrupt derived file was kept before being rebuilt. Both are regenerated from the live store, so after a glance they are safe to archive.

To resolve one: diff it against the canonical `entries/<subdir/>name.md`, decide which content is right, write the winner through the store (`nelly_store.write_entry` with the canonical file's current sha, or `update_entry`), then move the sidecar to `archive/` (never delete it). A sidecar left in `conflicts/` is reported by SessionStart as a pending conflict.
