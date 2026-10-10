# Software Engineering board (monday.com)

- Board ID: `5105170755`
- New tickets go to group **Backlog**.
- Ticket name: `[<project>] <feature Title>` (exact match is used to link existing manual tickets).

## Columns

| Column | ID | Type | Written by sync |
|---|---|---|---|
| Status | `color_mm7na652` | status | always (diff only) |
| Type | `color_mm7n3b93` | status | on create: `Feature` |
| Project | `dropdown_mm7na5br` | dropdown | on create: sidecar `project` |
| Code link | `text_mm7nz61n` | text | PR URL once merged, else branch tree URL |
| Notes | `long_text_mm7nzhmb` | long text | `Phase: X · Next: Y · Spec: <slug>` while hook-owned |

Status labels (no others exist; never create new ones): `To do`, `Gather Requirements`,
`Implementation Ready`, `In progress`, `Review`, `Done`, `Stuck`. `To do` is now only the
unlinked-ticket default; moving a ticket to `Gather Requirements` asks the monday-kickoff poll to
spec it.

## Status mapping (planner.desired_status, first match wins)

| Condition | Status |
|---|---|
| Workflow Status = Blocked | Stuck |
| Phase Tasks, or Requirements / Design with Workflow Status = Awaiting Implementation Request | Implementation Ready (planning done) |
| Phase Requirements / Design | Gather Requirements |
| Phase Implementation/Complete, branch merged into origin/main | Done |
| ... branch on origin with >= 1 commit ahead, unmerged | Review |
| ... git unknown and last push came from git | keep (no status write) |
| ... otherwise | In progress |

The pre-implementation rows ignore git, so a rewind moves the ticket back.
Done is never inferred without a merge. A stale local `origin/main` keeps the ticket in Review.

## `writes` -> MCP column values

`cli.py plan` returns `writes` as `{column_id: plain value}`. Convert each entry, then pass the
whole object as a **JSON string** in `columnValues`:

| Column type | plan value | MCP value |
|---|---|---|
| status (`color_mm7na652`, `color_mm7n3b93`) | `"Review"` | `{"label": "Review"}` |
| dropdown (`dropdown_mm7na5br`) | `"file-organiser"` | `{"labels": ["file-organiser"]}` |
| text (`text_mm7nz61n`) | `"https://..."` | `"https://..."` (plain string) |
| long text (`long_text_mm7nzhmb`) | `"Phase: ..."` | `{"text": "Phase: ..."}` |

The status format was confirmed live with `update_items`. The dropdown format comes from the
`create_item` schema.

## MCP calls

| Call | Shape |
|---|---|
| `get_board_items_page` | board `5105170755`, `includeColumns: true`; filter by item id, or read the Backlog page; the kickoff also requests each item's `created_at` (oldest by creation is picked first) |
| `get_updates` | `itemId`; returns update ids, bodies, `created_at` |
| `update_items` | batch: `[{itemId, columnValues: "<JSON string>"}]`, one call per sync |
| `create_item` | `name`, `groupId` (the Backlog group id from the page, e.g. `topics`), `columnValues: "<JSON string>"` |
| `change_item_column_values` | single-item fallback if `update_items` is unavailable; same `columnValues` string |
| `create_update` | `itemId`, `body` (plain text; the kickoff markers below must start the body) |

Example `columnValues` string for a create:

```json
"{\"color_mm7na652\": {\"label\": \"Gather Requirements\"}, \"color_mm7n3b93\": {\"label\": \"Feature\"}, \"dropdown_mm7na5br\": {\"labels\": [\"file-organiser\"]}, \"long_text_mm7nzhmb\": {\"text\": \"Phase: Design · Next: ... · Spec: ...\"}}"
```

## Item JSON for `cli.py plan --item`

Pass the item exactly as `get_board_items_page` returns it (with `includeColumns`), plus the
`updates` list from `get_updates(itemId)`:

```json
{"id": "3251090620", "name": "[file-organiser] ...", "updated_at": "...Z",
 "column_values": {"color_mm7na652": "To do", "long_text_mm7nzhmb": "...", "text_mm7nz61n": null,
                   "dropdown_mm7na5br": "file-organiser", "color_mm7n3b93": "Feature"},
 "group": {"id": "topics", "title": "Backlog"},
 "updates": [{"id": "...", "body": "...", "created_at": "...Z"}]}
```

A list with one item or `{"items": [item]}` is also accepted. For `candidates --items`, pass the
whole page (list or `{"items": [...]}`).

## Kickoff markers (monday-kickoff)

The scheduled kickoff poll keeps its state on the board as item updates. `cli.py
kickoff-candidates` matches `^🤖 isdd kickoff (started|done|needs-project)\b` at the start of the
(tag-stripped) update body:

| Marker update | Meaning |
|---|---|
| `🤖 isdd kickoff started (attempt N)` | a draft run began; 3h or less old = still running |
| `🤖 isdd kickoff done` + spec path + questions | draft finished; never picked again |
| `🤖 isdd kickoff needs-project: set the Project label` | Project missing or unmapped; asked once |

One stale `started` (older than 3h, or with no readable time; no `done`) is retried as attempt 2;
a second stale `started` sets Status `Stuck` and appends a note to Notes (Notes are never
replaced). To restart, the user posts an update starting `isdd kickoff retry` (case-insensitive)
and moves the ticket back to Gather Requirements: markers posted before that update are ignored.

A ticket is linked to an isdd feature, and never a kickoff candidate, when Notes contain `Spec:`,
the Code link is set, or `kickoff-candidates --spec-index` lists a repo spec folder whose
`- Monday Item:` is the ticket id or whose `- Title:` makes the ticket name `[<project>] <Title>`
(whitespace and case ignored). The kickoff writes both lines into the new folder's
workflow-state.md, and appends `Phase: Design · Next: answer open questions · Spec: <YYYY-MM-DD-slug>`
to Notes when done.
