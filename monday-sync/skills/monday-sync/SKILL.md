---
name: monday-sync
description: "Sync isdd features to the monday.com Software Engineering board. Use when the user asks to \"sync monday board\", \"update monday.com board\" or check tickets; after any isdd phase change; and when context shows \"monday: N features need board sync\" or \"monday: FEATURE changed phase/status\". Pushes Status/Notes/Code link and pulls Stuck and notes back."
---

# monday-sync

Keeps one board ticket per isdd feature in step with its workflow-state.md and its git branch.
All board I/O goes through the monday MCP connector. All git reads run on the linked computer
(`device_bash`). All decisions come from `cli.py`: never hand-compute a status or a diff.
Board column IDs, labels, value formats and MCP call shapes: `references/board.md`.
Status by phase: Requirements/Design = Gather Requirements; Tasks, or Awaiting Implementation
Request before implementation = Implementation Ready. Unlinked tickets moved to Gather Requirements
on the board are drafted by the scheduled `monday-kickoff` skill, not by this one.

Run every CLI call with the plugin data dir passed explicitly:

```sh
CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/cli.py" <command> ...
```

Below, `cli.py` means that full command. Every command prints JSON; `{"error": ...}` with exit 2
means stop and report that line. Keep per-feature scratch files (git.json, item.json, plan.json,
replan.json) in a temp directory.

## Which features

- Notice or phase change: `cli.py pending list` gives `[{dir, title, slug}]`. Sync each.
- Explicit run ("sync monday board"): the pending list, plus every feature dir under `linked` in
  `${CLAUDE_PLUGIN_DATA}/store.json`, then offer Backlog candidates (below).

## Per feature

1. **Begin.** If `<dir>/monday.json` has `unlinked: true`, the user opted this feature out: skip
   it entirely. Otherwise run `cli.py sync-begin <dir>`. While a sync is running, the flag hook
   still flags the feature but doesn't nudge about this sync's own workflow-state.md edits.
2. **Sidecar.** Read `<dir>/monday.json` if it exists. If `project` or `repo_path` is missing,
   derive them. project = basename of the git top-level of the
     feature's code repo; repo_path = that repo's path on the linked computer, `~` allowed.
     Confirm once with AskUserQuestion, then `cli.py record <dir> --project <p> --repo-path <path>`.
     Never ask again once recorded.
3. **Branch.** If Current Phase is Implementation or Complete and there is no `branch`, read the
   current branch on the device
   (`GIT_OPTIONAL_LOCKS=0 git -C <repo_path> branch --show-current` via `device_bash`). Confirm
   once with AskUserQuestion, then `cli.py record <dir> --branch <b>`. No branch: skip git.
4. **Git.** If a branch is recorded, Read `${CLAUDE_PLUGIN_ROOT}/hooks/git_probe.sh` and send its
   text inline to `device_bash` (the device can't see plugin files). The script expands `~`
   itself on the device:

   ```sh
   sh -s -- '<repo_path>' '<branch>' '<pushed_head or empty>' <<'PROBE'
   <git_probe.sh text, verbatim>
   PROBE
   ```

   Save its JSON to git.json. If the device is offline, leave out `--git` (git counts as unknown)
   and remember that git was unknown for step 13.
5. **Item.**
   - Linked (`item_id` set): `get_board_items_page` on board 5105170755 for that item id with
     `includeColumns`. Attach `get_updates(itemId)` as an `updates` list. Save to item.json. If the
     item is not on the board, use `--item-missing` in the next step instead of `--item`.
   - Not linked: look for an item whose name is exactly `[<project>] <Title>`. If one exists,
     `cli.py record <dir> --item-id <id>` and fetch it as above. Otherwise plan with neither flag
     (it will be a create).
6. **Plan.** `cli.py plan <dir> [--git git.json] [--item item.json | --item-missing] --now <ISO time>`
   and save plan.json.
   - `skipped` is set: nothing to do for this feature. Go to step 12.
   - `recreate == "ask"`: the item was deleted again after one recreate. Ask with
     AskUserQuestion:
     - Recreate: `cli.py record <dir> --forget-item`, then start this feature again from step 6.
       It becomes a plain create.
     - Unlink: `cli.py record <dir> --unlink`. The feature opts out: it drops from pending and is
       never recreated. Skip the remaining steps.
7. **Write the board.** One of:
   - `create` is true (new ticket, or the first recreate): `create_item` on board 5105170755 with
     `groupId` = the Backlog group, name `[<project>] <Title>`, and `columnValues` = every `writes`
     entry converted per `references/board.md`. Then
     `cli.py record <dir> --item-id <new id> --snapshot plan.json`. This saves the create's
     snapshot, including the recreate-once guard, before the re-plan.
   - Otherwise, if `writes` is non-empty: one `update_items` call on the item with the converted
     `columnValues`. Make no call when `writes` is `{}`. If `update_items` is unavailable, use
     `change_item_column_values` with the same `columnValues` string.
8. **Conflicts.** Ask about each entry in `conflicts` with AskUserQuestion. Never overwrite
   silently, and always persist the answer so the question isn't asked again next sync. Add
   `--git git.json` to every `--accept-board-status` call when step 4 produced it: the answer is
   pinned to that git state and lapses when git moves on. A merge-derived Done always wins over
   an accepted status.
   - `status` (the board shows X, isdd wants Y):
     - Keep the board: `cli.py record <dir> --accept-board-status X --git git.json`. X stays
       authoritative until the isdd phase or workflow status changes, or git moves on.
     - Overwrite: write Y with `update_items`, then `cli.py record <dir> --accept-board-status Y`.
   - `branch_gone` (the branch left origin unmerged, maybe a squash merge; "confirm Done?"):
     - Yes: write Done with `update_items`, then `cli.py record <dir> --accept-board-status Done`.
       This sets `confirmed_done`, so Done holds and the question stops, until a rewind.
     - No: `cli.py record <dir> --accept-board-status Review`.
9. **Apply isdd_updates.** If `isdd_updates` is non-empty (board set to Stuck), set each field in
   `<dir>/workflow-state.md` with the Edit tool, one `- Field: value` line at a time. The values
   are `Workflow Status: Blocked`, `Pause Reason: blocker` and `Hook Notes: <board note>`. Use
   Edit, not Write, so agent-isdd's workflow-state.json mirror stays in sync. Never change
   `Current Phase`.
10. **Board changes.** If `recap_line` is set, append it under a `## Board changes` heading in
    `<dir>/recap/recap.md` (create the heading if missing). List `changes` in the sync output.
11. **Re-plan.** Patch item.json locally with everything steps 7 and 8 wrote. After a create,
    build it from the new id plus the written `columnValues`. Then run `cli.py plan` again with
    the same git.json and the patched item, and save replan.json. Expect `writes == {}` and no
    `conflicts`. This also records the post-edit `synced_fields`. If it still has writes, report
    them and don't loop.
12. **Record.** `cli.py record <dir> --snapshot replan.json` (or plan.json when step 6 said
    `skipped`). This also ends the sync-begin window.
13. **Clear the flag.** `cli.py pending clear <dir> --expect-hash <replan.state_hash>`. The same
    rule applies to creates and updates:
    - Skip this step if git was unknown in step 4, so the flag stays and git is retried next time.
    - Skip it if any conflict is still unanswered.
    - If it answers `cleared: false`, the state changed meanwhile: leave the flag for the next sync.

## Unlink and relink

- Unlink: `cli.py record <dir> --unlink`. The feature leaves pending and the flag hook ignores
  it. `plan` answers `skipped: "unlinked"` and never creates a ticket.
- Relink: `cli.py record <dir> --item-id <id>` with an existing ticket's id. This clears
  `unlinked`, and the next sync treats the feature as linked. To relink to a new ticket, create it
  on the board first (group Backlog, name `[<project>] <Title>`), then record its id the same way.

## Backlog candidates (explicit run)

Read all board items with `get_board_items_page` (group Backlog, `includeColumns`) and save to
items.json. Then run `cli.py candidates --items items.json` to get `[{id, name}]`: To do tickets
with no linked feature. Offer them with AskUserQuestion:

- Start: run `/isdd` with the ticket name as the goal. Once its spec folder exists,
  `cli.py record <new feature dir> --item-id <id>`.
- Dismiss: `cli.py candidates --dismiss <id>`.
- Skip: do nothing.

Start an isdd workflow only after the user confirms.

## Failure rules

- monday connector unavailable or erroring:
  - make no further calls for that feature and leave the flag set (no `pending clear`);
  - append one line to `<dir>/recap/recap.md`: `- <date> monday sync failed: <reason>`;
  - report the same line.
- Linked computer offline: sync status by phase only (the plan handles unknown git). Leave the
  flag set and report one line.
- Never change isdd phase state because of a failure. Never retry in a loop: the next session's
  notice retries. A sync-begin marker left by a failed run expires after 10 minutes.

## Report (one block per sync)

Per feature, one line with the ticket name, the status (old -> new or "unchanged") and any
created/recreated/conflict/failure. Then the board changes, then candidates if offered.
