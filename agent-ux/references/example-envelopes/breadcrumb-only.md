# Example Envelope: breadcrumb_only

## What this demonstrates

The highest-frequency, cheapest event type. `delta` is the empty object `{}` — `phase_state`
alone is sufficient for `agent-ux` to render the breadcrumb line. This example is the reference
for the invariant: **no fields beyond `phase_state`** anywhere in this envelope.

## Envelope

```json
{
  "caller": "agent-isdd",
  "event_type": "breadcrumb_only",
  "phase_state": "Design",
  "delta": {}
}
```

## Notes

- No `artifact_path` — this event type never reads or writes an artifact.
- `delta` contains zero keys. If a future caller adds any key here (e.g. a stray `notes` or
  `summary` field), that is a contract violation for this event type, not a stylistic choice —
  flag it in review rather than silently accepting it.
- Expected output from `agent-ux`: exactly one breadcrumb line, e.g.
  `Requirements ▸ **Design** ▸ Tasks ▸ Implementation`.
