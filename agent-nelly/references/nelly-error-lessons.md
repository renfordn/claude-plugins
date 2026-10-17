# Error lessons (record, supersede, confirm, discard, list, auto-detect)

Read by `agent-nelly` for `error lesson`, `confirm error lesson`, `discard`, `list inferred`, or when a lesson contradicts an entry. Text moved verbatim from agent-nelly.md.

### Recording an error lesson

When the caller passes `error lesson`, write it as a new `error-prevention`
entry before running the promotion judgment below — same write-then-verify
discipline as "Recording a new fact" above, with the type and confidence
fixed and the body shape specific to this entry type.

**First, check for supersession.** Before writing anything, judge whether
the caller's `error lesson` text describes a failure that is clearly the
same underlying failed approach as an EXISTING `error-prevention` entry —
not merely a related or similar-sounding one. Use the same near-duplicate/
plausibility judgment already used for near-duplicate detection in
"Promotion write-back" (below) and `nelly-maintenance`'s "Consolidation
write-back", applied here specifically to `error-prevention` entries: compare the new lesson's failed
approach against every existing `error-prevention` entry's `Failed
approach:`/`Context:` body content.

- **This check only ever targets an existing `error-prevention` entry that
  is `explicit`-confidence.** An `inferred`-confidence entry has no business
  superseding anything, and no `inferred`-confidence entry may ever be
  treated as the "old entry" being superseded either — an unconfirmed,
  never-surfaced lesson cannot be the established guidance a newer flag
  replaces. If the only same-failure match you find is an `inferred` entry,
  treat it as no match: this is not a supersession.
- If you find a same-failure match against an existing `explicit`-confidence
  entry: stop here and follow "Supersession write-back" below instead of
  the plain numbered steps that follow — supersession replaces this
  subsection's plain write path, it doesn't run alongside it.
- If no existing entry describes the same failed approach (including the
  "treat an inferred match as no match" case above): this is not a
  supersession — proceed with the plain write below.

1. Choose a kebab-case `name` that summarizes the failed approach (this
   becomes the filename, per `entry_path(cwd, name)`'s convention).
2. Write a one-line `description` for relevance matching.
3. Set `metadata.type: error-prevention`.
4. Set `metadata.confidence: explicit` — this call is a caller-affirmed
   lesson, so it is immediately eligible for surfacing (subject to the
   exclusion rule in "Relevant entries" above, which only restricts
   `inferred`-confidence entries).
5. Set `metadata.last_referenced` to today (`YYYY-MM-DD`).
6. Before writing the entry file, guarantee `entries/` exists — run
   `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/nelly_memory.py" --entries-path [cwd]` via `Bash`, same as
   step 5 of "Recording a new fact" above. Do not skip this step.
7. Write the entry to `entries/<name>.md` in
   `references/nelly-entry.template.md`'s exact `error-prevention` shape
   (frontmatter with `type`, `confidence`, `last_referenced`; body structured
   as `Failed approach:` / `Context:` / `Why it failed:` / `How to avoid:`).
   Leave `metadata.supersedes` absent — this plain write path only runs
   when the supersession check above found no same-failure match, so there
   is no old entry to name; `metadata.supersedes` is only ever populated by
   the "Supersession write-back" path below.
8. Add one line for it to the project's `MEMORY.md` index: produce a
   field-annotated index line (`type`, `confidence` if present, `files` if
   present, sourced from this entry's own `metadata.type`/
   `metadata.confidence`/whether it carries a `files` reference) following
   the format `hooks/nelly_memory.py`'s `write_index_line()` now defines,
   then append it via `Edit`, leaving every other index line untouched.
9. Verify the write: re-read `entries/<name>.md` (`Read`) and confirm it
   exists with the content you just wrote — do not report success in
   `Written` until this check passes. If the file is missing or empty, retry
   the `entries/` directory-creation step and the write once before
   surfacing a failure.
10. Record the new entry in `Written`.

Then run the promotion judgment (below) on this newly-written entry — an
`error-prevention` entry is judged for Bucket 1/2/3 promotion exactly like
any other fact type; nothing about this entry type changes that judgment.
(This plain write-and-promote path only runs when the supersession check
above found no same-failure match; when it did, follow "Supersession
write-back" below instead.)

### Supersession write-back

When the supersession check above identifies a same-failure match against
an existing `explicit`-confidence `error-prevention` entry (the "old
entry"), perform this write sequence — order matters, and the old entry is
never edited in place, only moved:

1. **Write the new entry first**, using the full write-then-verify sequence
   from "Recording an error lesson" above (steps 1-9: name, description,
   type, confidence, `last_referenced`, ensure `entries/` exists, write,
   index line, verify by re-reading), with one addition: set
   `metadata.supersedes: <old-name>` in the new entry's frontmatter,
   naming the old entry being replaced. Do not proceed to step 2 below
   until this write has been verified (re-read and confirmed) — if the
   write or its verification fails, retry once per the existing retry rule,
   and if it still fails, stop here and report the failure in `Written`
   without archiving the old entry. This ordering is deliberate: a failure
   partway through must never leave the fact undocumented by archiving the
   only entry that stated it.
2. **Archive the old entry second**, only after step 1's write is verified,
   using `references/nelly-file-move.md`'s mechanism verbatim — the same
   `mkdir -p "<memory_dir>/archive" && mv
   "<memory_dir>/entries/<old-name>.md" "<memory_dir>/archive/<old-name>.md"`
   command already used by staleness flagging and consolidation (both in
   `nelly-maintenance`). Do not read or edit the old entry's content first,
   and do not copy it — this is a real move, exactly like every other use
   of this mechanism. The old entry's content is never altered; it becomes
   a byte-for-byte archived copy at its new path.
3. **Update `MEMORY.md`**: produce a field-annotated index line for the new
   entry (`type`, `confidence` if present, `files` if present, sourced from
   the new entry's own frontmatter) following the format
   `hooks/nelly_memory.py`'s `write_index_line()` now defines, then via
   `Edit` — same pattern as `nelly-maintenance`'s "Consolidation write-back"
   step 4 — add that line, remove the old entry's index line, leave every
   other line untouched.
4. **Append exactly one new `Action: superseded` block** to the project's
   `CONSOLIDATION-LOG.md` (`<memory_dir>/CONSOLIDATION-LOG.md`, created from
   `references/GLOBAL-CONSOLIDATION-LOG.md.template`'s shape if it doesn't
   exist yet — the same per-project log file `nelly-maintenance`'s
   "Consolidation write-back" already writes to; no new log file):
   ```
   ### <YYYY-MM-DDTHH:MM:SSZ>
   - Action: superseded
   - Superseded Entry: <old-name>
   - New Entry: <new-name>
   - Reason: <why the newer explicit flag replaces the older guidance>
   - Trigger: explicit error-prevention flag via <brief-assembly | /nelly-memory>
   ```
   Append-only, same discipline as every other write to this log — never
   edit or remove a prior block (`consolidated` or `superseded`).
5. **Record in `Written`**, e.g. `Written: created <new-name> (supersedes
   <old-name>); archived <old-name>; logged supersession to
   CONSOLIDATION-LOG.md`.

Then run the promotion judgment on the new entry, same as the plain
"Recording an error lesson" path above — supersession does not change how
the new entry is judged for promotion.

### Confirming an inferred error lesson

When the caller passes `confirm error lesson: <name>`, this is the *only*
action in this agent that changes an `error-prevention` entry's
`metadata.confidence` from `inferred` to `explicit`:

1. Read `entries/<name>.md` (`Read`) and confirm it is `type:
   error-prevention` with `metadata.confidence: inferred`. If the entry
   doesn't exist, isn't `type: error-prevention`, or is already `explicit`,
   record that in `Written` (nothing to confirm) and take no further action.
2. Edit `metadata.confidence` from `inferred` to `explicit` via `Edit` — a
   metadata-only edit, same style as the existing `last_referenced` bump in
   "Relevant entries" step 3 above. Do not alter the entry's `name`,
   `description`, `metadata.last_referenced`, or body.
3. Record the confirmation in `Written` (e.g. `Written: confirmed error
   lesson <name> (inferred → explicit)`). From this point forward, this
   entry is a normal `explicit`-confidence entry and is eligible for
   surfacing under the same matching judgment as any other entry — the
   exclusion rule in "Relevant entries" no longer applies to it.

### Discarding an inferred error lesson

When the caller passes `discard error lesson: <name>`, this takes an
`inferred`-confidence `error-prevention` entry out of
consideration (archived, never deleted) without ever confirming it — the reject side of the
list-then-decide loop `/nelly-memory review-inferred` drives (see
"Listing inferred error lessons" below for the read-only counterpart):

1. Read `entries/<name>.md` (`Read`) and confirm it is `type:
   error-prevention` with `metadata.confidence: inferred`. If the entry
   doesn't exist, isn't `type: error-prevention`, or is already `explicit`
   (an explicit entry is a confirmed, live lesson — discarding it is out of
   scope for this action; the caller wants "prune" or manual archiving
   instead), record that in `Written` (nothing to discard) and take no
   further action.
2. Move it to `archive/` using `references/nelly-file-move.md`'s mechanism
   — never delete. (archive-not-delete guarantee applies, same as every
   other write-back in this agent.)
3. Update the project's `MEMORY.md` index: remove the discarded entry's
   index line (`Edit`), leaving every other line untouched.
4. Append exactly one new log block to the project's
   `CONSOLIDATION-LOG.md` (created from
   `references/GLOBAL-CONSOLIDATION-LOG.md.template`'s shape if it doesn't
   exist yet, same as `nelly-maintenance`'s "Consolidation write-back") —
   this log is already shared across write-back actions beyond plain
   consolidation (see "Supersession write-back" above), so a discard reuses
   it rather than inventing a third log file:
   - `Action: discarded`
   - `Entry:` the discarded entry's `name`
   - `Reason: inferred error-prevention lesson rejected during review — never confirmed`
   - `Trigger: user request via /nelly-memory review-inferred`
5. Record the discard in `Written` (e.g. `Written: discarded <name>
   (archived, never confirmed)`).

### Listing inferred error lessons

When the caller passes `list inferred lessons`, this is a read-only
operation — it never updates `metadata.last_referenced`, never runs the
promotion judgment, and never mutates anything:

1. Scan this project's `entries/` (`Grep` over `entries/*.md` frontmatter
   for `type: error-prevention` and `confidence: inferred`, or `Read` each
   candidate — either is fine, this is a small directory scan, not a
   hot path) and collect every entry matching both.
2. For each match, read its `name` (filename stem), `description`, and
   `metadata.last_referenced`.
3. Also check `global/GLOBAL-MEMORY.md` for any `confidence: inferred`
   block. **This should always come back empty, by construction**, and the
   reply should say so rather than silently omitting the check: the
   automatic-detection path (below) explicitly never runs promotion
   judgment on an `inferred` entry, and "Promotion write-back"'s frontmatter
   shape for a promoted block never even carries a `metadata.confidence`
   field at all — so nothing at the `global/` tier can ever be `inferred`.
   If this check ever does find one, that's a bug elsewhere in this agent,
   not a normal outcome — surface it plainly rather than hiding it.
4. Return a numbered list, one line per project-tier match: `<n>. <name> —
   <description> (last written: <metadata.last_referenced>)`. If no matches
   exist in `entries/`, say so explicitly: "No inferred lessons pending."
   Never fabricate a placeholder entry.

This action is the read-only counterpart to "Discarding an inferred error
lesson" above and the pre-existing "Confirming an inferred error lesson" —
`/nelly-memory review-inferred` calls this first to render the list, then
drives the user's confirm/discard choices through those two write-back
actions, one call per entry the user selects.

### Automatic (best-effort) inferred-lesson detection

This is a narrowly-scoped, judgment-based, best-effort path — not an active
failure-pattern-mining system. Do not build scanning/heuristic logic for
this; it is the same kind of LLM judgment call used for every other
classification in this agent, and it runs at lower priority than the
explicit `error lesson` capture path above.

While assembling a brief, if you notice the caller's `task description`
strongly and unambiguously echoes the context of a previously-recorded
`error-prevention` entry's failure (not a loose or speculative resemblance —
only when the connection is clear and specific), you MAY write a new
`error-prevention` entry with `metadata.confidence: inferred`, using the
same write-then-verify mechanics as "Recording an error lesson" above
(steps 1-3, 5-10; skip step 4 and set `metadata.confidence: inferred`
instead). Record the write in `Written` (e.g. `Written: recorded inferred
error lesson <name> (not yet surfaced — unconfirmed)`).

**This entry is written, never surfaced.** It does not appear in
`Relevant entries`, `File relevance:`, or any other output this call or any
future call — see the exclusion rule in "Relevant entries" above — until a
separate, later `confirm error lesson: <name>` call flips it to `explicit`.
Do not run the promotion judgment on an `inferred` entry either — an
unconfirmed lesson has no business being promoted to the global tier; defer
promotion judgment until (if ever) it is confirmed.
