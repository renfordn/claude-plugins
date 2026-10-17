# File & Folder Summary Cache

Read by `agent-nelly` when the caller passes `file summary lookup`, `file summaries` or `folder summaries` (look up or persist per-file/per-folder summaries). Text moved verbatim from agent-nelly.md.

### File & Folder Summary Cache

Purpose: a targeted change usually starts with searching the whole repo to
find the right files — this cache exists so a caller can check a much
smaller place first (one JSON read per project, via
`scripts/build_index.py`) before paying for that search. It stores exactly
two things: a short (≤240 char) "what this file/folder does" summary per
path, and a staleness signal so a caller knows when the cached answer can no
longer be trusted.

**Write path — `file summaries` / `folder summaries`.**

When the caller passes `file summaries` (a list of `{path, summary, exports,
constraints, dependencies, tech_debt, git_hash}` items — `research-
consolidator`'s "File Summaries" output is already shaped this way) and/or
`folder summaries` (a list of `{folder, summary}` items):

1. For each **file summary** item: `name` is `file-summary-<slug of path>`
   (replace `/` with `-`); `metadata.type: file-summary`;
   `metadata.files: [<path>]` (that one path only); `metadata.git_hash:
   <the item's git_hash>`; `description` is the item's `summary`, truncated
   to `nelly_memory.SUMMARY_CHAR_LIMIT` (240) characters using
   `truncate_summary()`'s exact rule (strip, then if over the limit cut to
   239 chars and append `…`) if the caller's summary ran long — never write
   an over-length `description`, `hooks/nelly_summary_guard.py` denies the
   write anyway. Body: `references/nelly-entry.template.md`'s `file-summary`
   shape (Exports/Constraints/Dependencies/Tech debt from the item's other
   fields). Write to `entries/<SUMMARY_SUBDIR>/<name>.md` (see step 4 below
   for `<SUMMARY_SUBDIR>` — never directly under `entries/`, unlike every
   other entry type).
2. For each **folder summary** item: `name` is `folder-summary-<slug of
   folder>`; `metadata.type: folder-summary`; `metadata.folder: <folder>`;
   `description` is the item's `summary`, capped the same way. Body: the
   one-paragraph shape from the template. Same `entries/<SUMMARY_SUBDIR>/`
   location as file summaries.
3. **Overwrite, don't duplicate.** If an entry for the same path (`file-
   summary-<slug>`) or folder (`folder-summary-<slug>`) already exists,
   overwrite it in place (same filename, so `Write` naturally replaces it) —
   a file/folder has at most one summary entry, always the latest. This is
   different from every other entry type in this file, which never silently
   overwrites; a file-summary is a cache of current-state facts about a
   path, not a fact about something that happened, so there is nothing to
   preserve about the old version once the path has changed.
4. Guarantee `entries/<SUMMARY_SUBDIR>/` exists once before the batch — run
   `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/nelly_memory.py" --summary-entries-path [cwd]`
   via `Bash` (its printed path names `<SUMMARY_SUBDIR>` — `nelly_memory.SUMMARY_SUBDIR`,
   currently `file-folder-summary` — use that path verbatim rather than
   hand-computing it). This is a **different** directory from plain
   `--entries-path` (used by every other write-back path in this file):
   file-summary/folder-summary entries live one level deeper than every
   other entry type, specifically so a caller listing `entries/` for
   ordinary facts/lessons/preferences doesn't wade through one row per
   cached file in the repo. Then write each item sequentially. Skip the
   promotion judgment and the in-batch duplicate check entirely for this
   batch kind — both exist to catch the same underlying fact restated
   twice, which cannot happen here (one entry per path, overwritten rather
   than duplicated) and cross-project promotion makes no sense for a fact
   this project-specific.
5. Add or refresh each entry's `MEMORY.md` index line via
   `write_index_line()`'s format, with the link target
   `entries/<SUMMARY_SUBDIR>/<name>.md` (not `entries/<name>.md` — see step
   4) and `paths:` set to the one `files` path (file-summary) or left absent
   (folder-summary — `folder` isn't part of `write_index_line()`'s `paths`
   field, since that field means "files this entry is about" in the
   `file-relevance` sense, not a directory).
6. `Written` reports one line per item: `Wrote file summary for <path>` /
   `Wrote folder summary for <folder>` (or `Updated ...` when it overwrote
   an existing entry).

**Read path — `file summary lookup`.**

For each path the caller lists:

1. Run `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py" --lookup-path <path> --cwd [cwd]`
   via `Bash` — this answers entirely from `nelly-index.json`, never opening
   an `entries/*.md` file, which is the whole reason this stays cheap enough
   to call before every targeted search.
2. If it returns a `"file"` record: report a **cache hit** for that path —
   its `description` and `git_hash`. The caller (not this agent — a lookup
   never shells out to git) compares that `git_hash` against the file's
   current content hash; a mismatch means the cache is stale and the caller
   should treat it as a **miss**, read the file fresh, and send back an
   updated `file summaries` item afterward.
3. If it returns one or more `"folders"` records (nearest ancestor first)
   but no `"file"` record: report a **partial hit** — no file-level summary,
   but the nearest folder-summary's `description` as coarser context. A
   folder-summary carries no `git_hash`; its staleness is judged only by
   `metadata.last_referenced` age (same documented limitation
   `nelly-staleness.md` already accepts for entries with no stronger
   signal) — never claim a folder-summary is guaranteed current.
4. If neither is present: report a plain **cache miss** for that path — the
   caller falls back to reading/searching it directly, and is expected to
   send back a `file summaries` item afterward so the next lookup for the
   same path is a hit.
5. This never touches `metadata.last_referenced` and never appears in
   `Written` — it's a read, not a surfaced memory or a recorded fact.
