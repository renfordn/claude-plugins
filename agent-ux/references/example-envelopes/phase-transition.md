# Example Envelope: phase_transition

## What this demonstrates

A phase boundary crossing (Design → Tasks) that should trigger a `mark_chapter` call. `delta`
carries exactly the four fields design.md specifies — no full artifact body, no checklist state.

## Envelope

```json
{
  "caller": "agent-isdd",
  "event_type": "phase_transition",
  "phase_state": "Tasks",
  "delta": {
    "from_phase": "Design",
    "to_phase": "Tasks",
    "feature_slug": "2026-07-01-session-timeout-warning-banner",
    "one_line_summary": "Design approved; entering Tasks to slice the warning-banner rollout."
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/design/design.md"
}
```

## Notes

- `artifact_path` points at the artifact that was just finalized (the design doc), not the one
  about to be produced — `agent-ux` never regenerates it, and only reads further from it if it
  decides to (e.g. to confirm the summary before marking the chapter).
- `delta` has exactly 4 keys: `from_phase`, `to_phase`, `feature_slug`, `one_line_summary`. No
  section bodies, no findings, no full document text.
- Expected output from `agent-ux`: breadcrumb line, plus one line confirming the chapter was
  marked (title `Tasks`, summary drawn from `one_line_summary`) — never a chapter mark for a
  TDD-stage boundary or a session's first message (out of scope for this example).
