# Promotion write-back (Bucket 1 only)

Read by `agent-nelly` after Promotion judgment, when the judgment lands in Bucket 1 (write-back of the promoted entry). Text moved verbatim from agent-nelly.md.

### Promotion write-back (Bucket 1 only)

1. Read `global/GLOBAL-MEMORY.md` (`hooks/nelly_memory.py --global-path` /
   `global_dir()`'s convention).
2. Append a new frontmatter block to it, in `references/nelly-entry.template.md`'s
   exact shape (`name`, `description`, `metadata.type`,
   `metadata.last_referenced: <today>`, body) — this file stays the
   reference repo's proven inline-blocks-in-one-file shape at the global
   tier (there is no per-entry file under `global/`; `entry_path()`/
   `archive_path()` are per-project only). Use `Edit` to append after the
   existing content — never rewrite or reorder prior blocks.
3. Append exactly one new log block to `global/GLOBAL-PROMOTION-LOG.md`, in
   `references/GLOBAL-PROMOTION-LOG.md.template`'s exact shape:
   - `Action: promoted`
   - `Entry:` the promoted entry's `name`
   - `Source Project(s):` this project's slug
   - `Reason:` why this looked generalizable and not already represented in
     `GLOBAL-MEMORY.md`
   - `Trigger: brief-assembly` (or `user request` if the caller explicitly
     asked for a promotion pass)
4. Before promoting, check `GLOBAL-MEMORY.md` for an existing near-duplicate
   entry. If one already exists, skip promoting this entry as a fresh
   addition — do not write a second block to `GLOBAL-MEMORY.md` or
   `GLOBAL-PROMOTION-LOG.md` — and instead record in `Written` that a
   near-duplicate already exists globally (name it) and no further action
   was taken. Consolidating global-tier duplicates is out of scope for this
   feature (`nelly-maintenance`'s Consolidation write-back is per-project only).
5. This is append-only. Never edit or remove a prior log block. A later
   removal is logged as a new `Action: removed` block, never by deleting the
   original `promoted` block.
6. Record the promotion in `Written`.
