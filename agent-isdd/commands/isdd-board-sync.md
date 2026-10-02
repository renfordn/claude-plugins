---
description: Verify the Plan Board against local SDD state, resync stale or missing records in one batch, and prune orphans after confirmation
---

Repair drift between this project's Plan Board and its feature state files. Skip silently when the
project has no `PLAN-BOARD.md`, its `- URL:` is not https, or it says `- Sync: off`.

Let `SYNC` be `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board_sync.py"`.

1. **Verify.** `ArtifactData list` collection `plans` on the Plan Board artifact (URL in
   `PLAN-BOARD.md`). Write a JSON file holding a list of `{id, contentHash, version}` for each record
   from that result (`contentHash` is empty for old schema-1 records; `version` is shown beside each
   document and is needed to overwrite or delete an existing one). Run `SYNC verify --board-json <file>`. It
   prints `missing`, `mismatched` and `orphaned` record ids and stamps `lastVerified`.
2. **Resync.** If anything is missing or mismatched, run `SYNC resync --board-json <file>`. It prints
   one batch: `writes` (`set` entries with collection `plans`, `doc_id`, `data`, and `if_version` for
   records already on the board) and their `ids`. Pass `writes` unchanged as one `ArtifactData batch`. Then run `SYNC mark <id>...` with only the
   ids whose write succeeded; failed ones stay stale and SessionStart will list them. Never block
   on a failure: note it in the feature's recap.md and continue.
3. **Prune.** If there are orphans (board records or sync entries with no feature directory), run
   `SYNC prune --board-json <file>` to list them, show the list to the user, and ask for
   confirmation before deleting anything. Only after an explicit yes, run
   `SYNC prune --board-json <file> --confirm` (removes the sync entries) and send the printed
   `board_instructions` (delete entries with `doc_id` and `if_version`) as one `ArtifactData batch`. Without a yes, remove nothing.

Report one line each for verify, resync and prune.
