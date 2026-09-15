# Import (bulk recording from files)

Read by `agents/nelly-maintenance.md` when invoked via `/nelly-memory import <source-dir>
[--force]`.


Runs when invoked via `/nelly-memory import <source-dir> [--force]` (Phase
8) rather than a single `new fact`. Same destination shape as `agent-nelly.md`'s "Recording a
new fact", but sourced from a directory of existing files instead of
one piece of caller text, and applied per-file rather than once:

1. List every file directly under `<source-dir>` (`Glob`).
2. For each source file:
   1. Read the file's actual content (`Read`) — the synthesized fields below
      must reflect what the file actually says, never a placeholder.
   2. Derive `name` from the source filename's slug: strip the extension,
      keep the rest as-is (e.g. `docker-compose-local-dev-setup.md` →
      `docker-compose-local-dev-setup`).
   3. Check whether `entries/<name>.md` already exists.
      - If it exists and `--force` was **not** passed: skip this file
        entirely — do not write, do not touch the existing entry (it must
        remain byte-for-byte unchanged) — and record the skip (e.g.
        "Skipped `<name>.md` (already exists; use `--force` to
        overwrite).").
      - If it exists and `--force` **was** passed: proceed to overwrite it
        below and record the overwrite (e.g. "Overwrote `<name>.md`
        (--force)."), with a freshly synthesized `description`/`metadata`
        (including a fresh `last_referenced`) rather than reusing the old
        entry's fields.
      - If it does not exist: proceed to write it as a new entry.
   4. Write a one-line `description` that is a real summary of this
      specific file's content — name its actual subject matter, never a
      generic "Imported from `<filename>`" placeholder.
   5. Pick `metadata.type` — the project-defined taxonomy if this project
      has a `types.yaml`, otherwise the default `user | feedback | project |
      reference`; any one valid value is acceptable, there is no fixed
      per-file mapping.
   6. Set `metadata.last_referenced` to today (`YYYY-MM-DD`, the import
      date).
   7. Before writing, guarantee `entries/` exists — run
      `python3 hooks/nelly_memory.py --entries-path [cwd]` via `Bash`, same
      as step 5 of `agent-nelly.md`'s "Recording a new fact". Do this even on an
      overwrite; it is idempotent and cheap, and skipping it is the known
      failure mode where the index gets updated but the file never lands.
   8. Write (or overwrite) the entry to `entries/<name>.md` in
      `references/nelly-entry.template.md`'s exact shape, same as step 6 of
      `agent-nelly.md`'s "Recording a new fact".
   9. Add (or update) one line for it in the project's `MEMORY.md` index:
      produce a field-annotated index line (`type`, `confidence` if present,
      `files` if present, sourced from this entry's own frontmatter) following
      the format `hooks/nelly_memory.py`'s `write_index_line()` now defines,
      then add/update it via `Edit`, leaving every other index line
      untouched.
   10. Verify the write: re-read `entries/<name>.md` (`Read`) and confirm it
       exists with the expected content before recording success, same as
       step 8 of `agent-nelly.md`'s "Recording a new fact".
   11. Record the entry in `Written` as created/skipped/overwritten.
3. Run `agent-nelly.md`'s promotion judgment on every newly-written or
   newly-overwritten entry from this import, exactly as you would for any
   other new entry — importing does not exempt an entry from the same
   cross-project promotion check.

