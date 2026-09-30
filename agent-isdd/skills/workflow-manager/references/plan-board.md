# Plan Board

A living Artifact page that shows every spec-driven feature's phase, status and next step. One
page can cover several projects. The workflow keeps it current; nobody edits it by hand.

## How it works

- **The page** is `assets/plan-board.html`. It reads the collection `plans` from its own database
  (up to 200 records) and updates live. It only ever shows record text as text, never markup.
- **One record per feature**, built by `hooks/plan_board.py doc` from `workflow-state.md`. Never
  hand-write one.
- **A project opts in** by recording the page URL in `PLAN-BOARD.md`, next to `spec/` in its SDD
  memory directory: `- URL: https://claude.ai/artifact/...`. The URL must start with `https://`;
  anything else counts as unset. Without that file nothing here runs.
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

Statuses `Paused`, `Blocked` and `Awaiting …` (the template's `Awaiting Confirmation` and
`Awaiting Implementation Request`) show the current phase as paused, with its `pauseReason`.

## Turning it off

Delete `PLAN-BOARD.md`. The sync step and the `SessionStart` nudge both go quiet. Records already on
the page stay until deleted with `ArtifactData`.
