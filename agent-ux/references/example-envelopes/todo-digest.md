# Example Envelope: todo_digest

## What this demonstrates

A caller (here, `code-reviewer`) asking `agent-ux` to (re)publish a visible dashboard of the
`spawn_task`-flagged items it has been tracking in its own `TODO-LEDGER.md`, next to its
`REVIEW-STATE.md`. `agent-ux` never wrote any of those rows itself — it only reads and renders
them.

## Envelope

```json
{
  "caller": "code-reviewer",
  "event_type": "todo_digest",
  "phase_state": "Implementation",
  "delta": {
    "ledger_path": "proposals/2026-07-01-session-timeout-warning-banner/review/TODO-LEDGER.md"
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/review/todo-dashboard.md"
}
```

## Notes

- `delta` has exactly 1 key: `ledger_path` — the file `agent-ux` reads for current rows. Distinct
  from `artifact_path`, which is the stable target it publishes/redeploys the dashboard to; the
  two are usually siblings in the same review-state directory but are never the same value.
- `agent-ux` does not validate that `ledger_path`'s rows are still accurate (e.g. that a `task_id`
  hasn't already been resolved by the user outside this flow) — it renders the file's content as
  of the read, same staleness discipline as any other pull-over-push read in this contract.
- Expected output: breadcrumb line, plus one line confirming the dashboard was
  published/redeployed with however many open items the ledger currently lists. A companion
  counter-example (not included as a separate file) would be a `ledger_path` that doesn't exist
  yet — expected output is `No todo ledger found at <ledger_path> — nothing to render` instead.
