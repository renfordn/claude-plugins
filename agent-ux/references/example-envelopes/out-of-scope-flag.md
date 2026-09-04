# Example Envelope: out_of_scope_flag

## What this demonstrates

A single, already-identified, already-confirmed-out-of-scope issue the caller wants tracked via
`spawn_task`. `delta` is unchanged from today's shape per design.md — already minimal.

## Envelope

```json
{
  "caller": "agent-isdd",
  "event_type": "out_of_scope_flag",
  "phase_state": "Design",
  "delta": {
    "title": "Cross-tab session sync uses a polling fallback, not BroadcastChannel",
    "file_path": "src/session/session-context.ts",
    "context_summary": "Noticed while designing the timeout banner: session-context.ts polls localStorage every 2s to detect cross-tab sign-out instead of using BroadcastChannel, which is now supported in all target browsers. Out of scope for this feature — flagging for a follow-up cleanup task, not blocking the current design."
  }
}
```

## Notes

- No `artifact_path` — this event type doesn't redeploy or read an artifact; `spawn_task` takes
  the prompt directly from `context_summary` plus `file_path`.
- `delta` has exactly 3 keys: `title`, `file_path`, `context_summary`. The caller has already
  judged this concrete and out of scope before delegating — `agent-ux` never infers that judgment
  itself, only renders/spawns from what it's given.
- Expected output from `agent-ux`: breadcrumb line, plus one line confirming the task was spawned
  (including the id `spawn_task` returns, for later `dismiss_task` reference).
