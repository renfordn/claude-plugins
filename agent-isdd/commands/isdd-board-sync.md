---
description: Verify the shared Plan Board against every project's SDD state, resync stale or missing records in one batch, and prune orphans after confirmation
---
Repair drift between the shared Plan Board and every project's feature state files, from any
session. Projects come from `sdd-memory/`: each one whose board is the shared `PLAN-BOARD.md` at
the `sdd-memory/` root and isn't `- Sync: off`. Skip silently when there is no shared board URL.
Let `SYNC` be `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board_sync.py" all`.

1. **Verify.** `ArtifactData list` collection `plans` on the Plan Board artifact (the URL in the
   shared `PLAN-BOARD.md`). Write a JSON file holding a list of `{id, contentHash, version}` for
   each record (`contentHash` is empty for old schema-1 records; `version` is needed to overwrite
   or delete an existing one). Run `SYNC verify --board-json <file>`. It prints, per project label,
   the `missing` and `mismatched` record ids, then `orphaned` (cards no project has) and `skipped`
   (project folders never synced, so their label is unknown; run `/isdd-board-sync` once from
   that project with `plan_board_sync.py resync --board-json <file>` to label it), and stamps
   `lastVerified` for each project.
2. **Resync.** If anything is missing or mismatched, run `SYNC resync --board-json <file>`. It
   prints one batch for every project: `writes` (`set` entries with collection `plans`, `doc_id`,
   `data`, and `if_version` for records already on the board) and their `ids`. Pass `writes`
   unchanged as one `ArtifactData batch`, then run `SYNC mark <id>...` with only the ids whose
   write succeeded; failed ones stay stale and SessionStart will list them. Never block on a
   failure: note it in the feature's recap.md and continue.
3. **Prune.** If there are orphans, run `SYNC prune --board-json <file>` to list them, show the
   list to the user, and ask for confirmation before deleting anything. Only after an explicit
   yes, run `SYNC prune --board-json <file> --confirm` and send the printed `board_instructions`
   (deletes with `doc_id` and `if_version`) as one `ArtifactData batch`. Without a yes, remove nothing.

Report one line per project for verify and resync, then one line for prune.
