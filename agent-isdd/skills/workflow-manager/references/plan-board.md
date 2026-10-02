# Plan Board

A living Artifact page that shows every spec-driven feature's phase, status, next step and a brief
(goal, requirements and design state, risks, slice progress, decisions, open items). One page can
cover several projects. The workflow keeps it current; nobody edits it by hand.

## How it works

- **The page** is `skills/workflow-manager/assets/plan-board.html`. It reads the collection `plans` from its own database
  (up to 200 records) and updates live. It only ever shows record text as text, never markup.
- **One record per feature** (schema 2), built by `hooks/plan_board.py doc` from `workflow-state.md`
  and its sibling state files. A script derives the brief; the model never writes it. Never
  hand-write a record.
- **It refreshes on every state-file write.** The post-write hook watches `workflow-state.md`,
  `requirements/requirements.md`, `design/design.md`, `tasks/tasks.md` and `recap/recap.md`. It
  rebuilds the record and, when its `contentHash` differs from the last synced one, adds a reminder
  with the `ArtifactData` steps below to its message. Hooks cannot call MCP tools, so the model
  makes the one write; `SessionStart` still catches any miss.
- **The page** has an Open / Recently closed toggle and a detail pane showing the selected
  feature's brief. Recently closed holds Complete features closed within 14 days or among the 10
  most recently closed (the larger set); older ones are listed under Archive. Schema-1 records still
  render with the status fields they have.
- **A project opts in** by recording the page URL in `PLAN-BOARD.md`, next to `spec/` in its SDD
  memory directory: `- URL: https://claude.ai/artifact/...`. The URL must start with `https://`;
  anything else counts as unset. Without that file nothing here runs.
- **Per-project switch:** `- Sync: off` in `PLAN-BOARD.md` stops reminders and writes for that
  project only (default on). An optional `- Brief Board: https://...` line adds a link to the
  focus-ux Brief Board for ad-hoc briefs; without it no link shows.
- **`plan-board-sync.json`** in the same directory remembers which records were written. A feature
  whose current record differs from what was written is "out of date". `SessionStart` lists those
  features with the exact commands, so a missed update is noticed at the next session start.

## Commands

All are `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board.py" <command>`:

| Command | Does |
|---|---|
| `doc <workflow-state.md> --project <label> [--out <file>]` | Prints the record as JSON, or writes it to the file and prints its `id` |
| `page <out.html>` | Writes the board page |
| `stale [--cwd <project folder>]` | Lists every out-of-date feature and its state path |
| `mark-synced <workflow-state.md> --project <label>` | Records that the record was written |

`<label>` is the basename of the project's git top-level folder, the value the `SessionStart` nudge
prints after `--project`. Use the same label every time: a different one makes a different record
id, and the feature would stay out of date. Two projects whose folders share a name would also
share ids. `stale`, and any state file outside the `spec/` layout, need `CLAUDE_PLUGIN_DATA` and
`CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT` in front, as in the `sdd_memory.py` commands elsewhere in
this skill; the `SessionStart` nudge prints them ready to run. Otherwise they are harmless.

## First-time setup

Do this once, then every project can share the page.

1. Build the page file: `plan_board.py page <out.html>`.
2. Publish it with the Artifact tool, passing
   `capabilities: {db: {rules: [{path: "", read: "view", write: "owner"}]}}`, a short description
   and the icon `board`. **Without that rule the default lets Contributors write records**, so
   publish with it. Everyone who can open the page can read; only the owner can write.
3. Write the returned URL into `PLAN-BOARD.md` in the project's memory directory: `# Plan Board`,
   then `- URL: <url>`. Find the directory with
   `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --path`,
   or use the one the `SessionStart` context names ("SDD per-feature state for this project").
   To put several projects on one board, use the same URL in each project's file.
4. Seed it: run `stale --cwd <project folder>` to list every feature and its state path, then do
   the "Syncing a feature" steps for each. `SessionStart` lists up to three at a time, with the
   rest under `stale`.
5. Check it once: `ArtifactData` `list` on collection `plans`, and confirm one record per feature.

## Syncing a feature

Do it after any write to `workflow-state.md` that changes the phase, status, pause reason or next
action: a phase transition, a pause, a resume, a rewind, a handoff, or completion.

1. Build the record into a temp file: `plan_board.py doc <workflow-state.md> --project <label> --out <temp file>`.
   It prints the record's `id`.
2. Write it. `ArtifactData` action `get` with `url` = the URL in `PLAN-BOARD.md`, collection
   `plans`, `doc_id` = the `id`, to see whether the record exists and what its `version` is. Then
   action `set`, same `url`, collection and `doc_id`, with `file_path` = the temp file. If the
   record already exists, also pass `if_version` = the `version` from the `get`: a `set` on an
   existing record is refused without it, so leaving it out makes the first sync work and every
   later one fail. Omit it only when creating the record.
3. Mark it written: `plan_board.py mark-synced <workflow-state.md> --project <label>`.

If any step fails, note it in one line in `recap.md` and carry on. A sync failure never blocks the
workflow. The feature stays out of date and `SessionStart` will list it again.

## Record fields

| Field | Meaning |
|---|---|
| `id` | Document id: `<project>--<feature slug>`, limited to characters a database path allows |
| `project`, `slug`, `title` | Where the feature lives and what it is called |
| `goal` | The feature goal, cut to 300 characters |
| `track` | `Standard` or `Fast` (Fast shows the Tasks phase as skipped) |
| `phase`, `status` | Current phase and workflow status, as written in `workflow-state.md` |
| `phases` | Four entries (`Requirements`, `Design`, `Tasks`, `Implementation`), each `done`, `active`, `paused`, `pending` or `skipped` |
| `pauseReason`, `nextAction` | Cut to 240 and 300 characters; empty when the file says `None` |
| `implementationRequested` | `true`, `false` or `null` when unknown |
| `updatedAt` | The date in `## Last Updated`, else the file's modified date |
| `closedAt` | The `Last Updated` date when the feature is Complete, else empty |
| `brief` | Built by `hooks/plan_brief.py`: `goal`, `requirements {state, openGaps}`, `design {state, summary, risks, openQuestions}`, `slices {total, done, items}`, `decisions`, `openItems`. At most 8 items per list, 160 characters per item, about 6 KB in all; clipped with an ellipsis, never dropped. A missing file just omits its section. `slices.done` is known only when `direct-mode-state.json` sits beside `workflow-state.json`, else null |
| `contentHash` | Hash of the record's own content (not `updatedAt`); what drift checks compare |
| `briefBoardUrl` | The `- Brief Board:` URL, when set |

Statuses `Paused`, `Blocked` and `Awaiting …` (the template's `Awaiting Confirmation` and
`Awaiting Implementation Request`) show the current phase as paused, with its `pauseReason`.

## Drift repair

`/isdd-board-sync` runs `plan_board_sync.py` (same folder as `plan_board.py`):

- `verify --board-json <file>` compares the board's `plans` records (an `ArtifactData list` saved to
  a file) with local state and prints missing, mismatched and orphaned ids. It stamps
  `lastVerified`; `SessionStart` reminds you to verify when that is over 24 hours old.
- `resync [--board-json <file>]` prints one `ArtifactData batch` of `set` writes for every stale or
  missing record. `mark <id>...` then records only the ids that succeeded; failed ones stay stale.
- `prune [--board-json <file>]` lists orphans (board records or sync entries with no feature) and
  deletes nothing. Only after the user confirms, `prune --confirm` removes the sync entries and
  prints the board deletes to apply.

`slices.done` comes from `direct-mode-state.json`, which is not a watched file, so the count
refreshes only on the next watched write or `/isdd-board-sync`. The `resync` and `prune` batches
pass straight to `ArtifactData batch` (`writes` entries with `doc_id`; `if_version` for records already
on the board, taken from the `version` in the dump). Create, overwrite with `if_version` and delete
were verified against a live board on 2026-10-02.

The first sync after upgrading to schema 2 marks every feature stale once, because the hash changes.

## Turning it off

Set `- Sync: off` in `PLAN-BOARD.md` to pause one project, or delete the file. The sync step and the `SessionStart` nudge both go quiet. Records already on
the page stay until deleted with `ArtifactData`.
