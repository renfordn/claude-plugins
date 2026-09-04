---
description: View or manage this project's independent Agent Nelly memory (view | import | prune | consolidate | error-lesson | confirm-lesson | list-inferred | review-inferred)
argument-hint: "[view [task description] | import <source-dir> [--force] | prune [--threshold-days N] | consolidate | error-lesson <description> | confirm-lesson <name> | list-inferred | review-inferred] (default: view)"
allowed-tools: Bash(python3 *)
---

Manage this project's memory store, which lives under
`~/.claude/agent-nelly-memory/<project-slug>/` (and the cross-project
`~/.claude/agent-nelly-memory/global/` tier). This store is entirely
independent of the SDD plugin's `~/.claude/sdd-memory/` — no SDD plugin
needs to be installed for this command to work. `nelly-orchestrator` is the
**sole owner** of every file under that root. This command file never reads,
writes, moves, or overwrites a memory file itself, for any subcommand,
including `view` — every outcome described below is produced by asking
nelly-orchestrator to do it, not by this command doing it directly.

Requested action (default `view`): $ARGUMENTS

Resolve the memory directory first, for logging/context only (never used to
read/write entry files directly from here):

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/nelly_memory.py" --path
```

## view

No required arguments beyond an optional trailing task description.

Delegate entirely to nelly-orchestrator's brief-assembly contract: ask
nelly-orchestrator for a brief given this project's `cwd` and the task
description. Return nelly-orchestrator's four sections verbatim, in order —
`Intent`, `Relevant entries`, `Intent alignment`, `Written`.

Whenever a task description was actually supplied (i.e. `/nelly-memory view
<task description>`), also pass nelly-orchestrator the surface-relevant-memory
flag for this call — the user explicitly running `view` with a stated task
IS the per-call opt-in that flag was designed for, not autonomous/unprompted
surfacing (nelly-orchestrator's proactive-surfacing behavior only ever fires
when this flag is explicitly passed, never on its own). When no task
description is given at all (bare `/nelly-memory view`), do not set the
flag — nelly-orchestrator has nothing to match relevance against, and should
report `Relevant entries: none requested this call` for that bare
invocation, falling back to a generic "reviewing project memory" task
description only for the `Intent alignment` comparison, not for surfacing.

If the caller also names one or more files they're currently looking at
alongside the task description, pass those along to nelly-orchestrator as
`target files`. When nelly-orchestrator finds a match, its returned
`Relevant entries` section carries an additional `File relevance:` sub-list —
return that sub-list verbatim, nested under `Relevant entries` exactly as
nelly-orchestrator produced it, never as a separate top-level section. This
sub-list is only ever present when `target files` was actually passed and a
match was found; otherwise it is simply absent from the four-section output.

This command must never read or print raw entry-file contents itself — it
has no direct visibility into `entries/*.md`; nelly-orchestrator alone reads
those files and returns only the condensed brief.

If nelly-orchestrator reports that the project has no `Intent` captured and
no entries at all (a genuinely empty project — never invented, never
inferred), do not degrade to printing the four brief sections with
placeholder/empty values. Instead report exactly: "No memory recorded yet
for this project." with no error, traceback, or partial brief output.

## import

Usage: `import <source-dir> [--force]`.

Ask nelly-orchestrator to import every plain file in `<source-dir>` as one
new entry per source file, in `references/nelly-entry.template.md`'s exact
shape, under this project's `entries/`:

- For each source file, nelly-orchestrator derives `name` from the source
  filename's slug (strip the extension, keep the rest as-is — e.g.
  `docker-compose-local-dev-setup.md` becomes `docker-compose-local-dev-setup`).
- `description` is a real one-line summary that nelly-orchestrator writes by
  actually reading the source file's content and naming its specific
  subject matter — never a generic placeholder like "Imported from
  `<filename>`".
- `metadata.type` is nelly-orchestrator's best-fit pick from the project's
  `types.yaml` taxonomy if one exists, otherwise the default
  `user | feedback | project | reference` — any one of the four is
  acceptable; there is no fixed source-file-to-type mapping.
- `metadata.last_referenced` is set to today's date (`YYYY-MM-DD`, the
  import date).
- Exactly one new entry file is created per source file — N source files in,
  N new entries under `entries/`.

Collision handling, per source filename that would collide with an existing
`entries/<name>.md`:

- Without `--force`: ask nelly-orchestrator to skip that file, leaving the
  existing entry byte-for-byte unchanged, and report a line such as
  "Skipped `<name>.md` (already exists; use `--force` to overwrite)."
- With `--force`: ask nelly-orchestrator to overwrite that entry with a
  freshly synthesized `description`/`metadata` (fresh `last_referenced`) and
  report a line such as "Overwrote `<name>.md` (--force)."

Report, per file, whether it was created, skipped, or overwritten. This
command never writes the entry files itself — every create/skip/overwrite
above is nelly-orchestrator's action, asked for by this command.

## prune

Usage: `prune [--threshold-days N]` (default `N=90`).

Ask nelly-orchestrator to run its staleness-flagging write-back: for every
entry in this project's `entries/` whose `metadata.last_referenced` is at or
beyond the threshold, nelly-orchestrator moves it to `archive/` (never
deletes it) and updates the project's `MEMORY.md` index accordingly.

This same invocation also runs nelly-orchestrator's file-change-aware
staleness check — an entry whose `metadata.files` no longer match the
current state of the repo (per nelly-orchestrator's own file-change
detection) is folded into the same pass, not a separate command or a second
call. There is still exactly one `prune` command; the file-change-aware
check is additive behavior inside it, not a new subcommand.

(archive-not-delete guarantee applies — see Cross-cutting rules.)

Report, per archived entry, a line such as: "Archived `<name>` (last
referenced `<date>`, over the `<N>`-day threshold). This entry was moved to
`archive/`, not deleted — its full content is preserved and recoverable by
moving it back to `entries/`." If nothing crosses the threshold, report
"Nothing to prune — no entries older than `<N>` days."

## consolidate

No required arguments.

Ask nelly-orchestrator to run its consolidation write-back: review this
project's entries for pairs/groups describing the same underlying fact from
different angles, and for each such group nelly-orchestrator writes one new
merged entry under `entries/` with a new name, moves both (or all) original
entries to `archive/` (never deletes them), updates `MEMORY.md`, and appends
exactly one new block to `CONSOLIDATION-LOG.md`.

(archive-not-delete guarantee applies — see Cross-cutting rules; consolidation
additionally always leaves an audit trail via `CONSOLIDATION-LOG.md`.)

Report, per consolidation performed, a line such
as: "Consolidated `<name1>` and `<name2>` into a new entry, `<merged-name>`.
Both original entries were moved to `archive/`, not deleted — their full
content remains intact and recoverable there. One log line was appended to
`CONSOLIDATION-LOG.md`." If nelly-orchestrator finds no near-duplicate
group, report "Nothing to consolidate — no overlapping entries found."

## error-lesson

Usage: `error-lesson <description>`.

Ask nelly-orchestrator to record `<description>` as its `error lesson`
input, exactly as documented under "Recording an error lesson" in
`agents/nelly-orchestrator.md` — nelly-orchestrator writes it as a new
`error-prevention` entry with `metadata.confidence: explicit` before running
its promotion judgment. This command never writes the entry file itself;
`<description>` is passed through verbatim as the `error lesson` brief
input and nelly-orchestrator performs the write.

Report nelly-orchestrator's reply verbatim (including the `Written` line
naming the new entry).

## confirm-lesson

Usage: `confirm-lesson <name>`.

Ask nelly-orchestrator to run its `confirm error lesson: <name>` input,
exactly as documented under "Confirming an inferred error lesson" in
`agents/nelly-orchestrator.md` — this is the only mechanism that flips an
existing `inferred`-confidence `error-prevention` entry named `<name>` to
`explicit`, making it eligible for surfacing. This command never edits the
entry file itself; `<name>` is passed through as the `confirm error lesson`
brief input and nelly-orchestrator performs the write.

Report nelly-orchestrator's reply verbatim (including the `Written` line
confirming the flip, or an error if no `inferred` entry named `<name>`
exists).

## list-inferred

No arguments.

Ask nelly-orchestrator to run its `list inferred lessons` input, exactly as
documented under "Listing inferred error lessons" in
`agents/nelly-orchestrator.md`. This is read-only — it never confirms,
discards, or otherwise mutates anything.

Report the returned numbered list verbatim: one line per entry, `<n>. <name>
— <description> (last written: <date>)`. If nelly-orchestrator reports no
matches, report exactly: "No inferred lessons pending."

## review-inferred

No arguments. Interactive — this subcommand spans multiple turns.

1. Run `list-inferred` above (same nelly-orchestrator call, same output
   format). If the result is "No inferred lessons pending.", report that
   and stop — there is nothing to review.
2. Otherwise, show the numbered list to the user and ask them to choose
   what to do with each entry: confirm it as a real, reusable lesson, or
   discard it. Accept a reply in the form of entry numbers to confirm,
   entry numbers to discard, `all` (confirm every listed entry), or `none`
   (discard nothing, confirm nothing — cancel the review with no changes).
   Wait for the user's reply before taking any action; do not guess intent
   from the list alone.
3. For every number the user marks to confirm, ask nelly-orchestrator to
   run `confirm error lesson: <name>` (the same action `confirm-lesson`
   above uses) for that entry's `<name>` — one nelly-orchestrator call per
   confirmed entry.
4. For every number the user marks to discard, ask nelly-orchestrator to
   run `discard error lesson: <name>`, documented under "Discarding an
   inferred error lesson" in `agents/nelly-orchestrator.md` — one
   nelly-orchestrator call per discarded entry. This archives the entry
   (archive-not-delete guarantee applies) without ever confirming it.
5. Report per-entry outcomes: "Confirmed `<name>` (inferred → explicit)."
   for each confirmed entry, and "Discarded `<name>` (archived, not
   deleted — never confirmed)." for each discarded entry. If the user
   replied `none`, report "No changes made." and take no further action.

This command never edits or moves an entry file itself for either outcome —
every confirm and every discard above is nelly-orchestrator's action, asked
for by this command, exactly like every other subcommand in this file.

## Cross-cutting rules

- **Archive-not-delete guarantee.** No subcommand in this file ever deletes
  memory content. Archiving (via `prune` or `consolidate`) always moves the
  affected file(s) to `archive/`, leaving them fully intact and recoverable
  by moving them back to `entries/`.
- Every subcommand above delegates its work to nelly-orchestrator; this
  command file contains no direct file-mutation instructions of its own —
  no instruction here tells this command to `Write`, `Edit`, move, archive,
  or overwrite a memory file directly. Any sentence describing such a
  mutation names nelly-orchestrator as the actor performing it, in the same
  or an immediately preceding sentence.
- This command never reads a raw entry file's contents for any subcommand,
  including `view` — only nelly-orchestrator does, and it returns condensed
  summaries, never full bodies.
- Never invent or infer this project's `Intent` line from this command —
  that discipline belongs entirely to nelly-orchestrator.
