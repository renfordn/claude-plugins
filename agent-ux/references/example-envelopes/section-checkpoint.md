# Example Envelope: section_checkpoint

## What this demonstrates

A single requirements section just got confirmed/locked. `delta` carries that one section's body
in full, but every *other* section is named only — never its body. This is the one explicit
exception to "never a full artifact body" named in design.md's Invariants: the single confirmed
section's body is allowed, nothing else's.

## Envelope

```json
{
  "caller": "agent-isdd",
  "event_type": "section_checkpoint",
  "phase_state": "Requirements",
  "delta": {
    "section_name": "Acceptance Criteria",
    "section_body": "- Session countdown banner appears at 60s remaining, dismissible, non-blocking.\n- Banner re-appears once per countdown window if dismissed.\n- No banner shown if the user is actively typing in a form field.",
    "remaining_section_names": [
      "Problem Statement",
      "Success Metrics",
      "Constraints",
      "Out Of Scope"
    ],
    "open_gaps": [
      "No decision yet on cross-tab session sync behavior."
    ]
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/requirements/requirements.md"
}
```

## Notes

- `remaining_section_names` is a list of names only (`Problem Statement`, `Success Metrics`,
  etc.) — none of those sections' bodies appear anywhere in this envelope, confirmed or draft.
- `open_gaps` is a list of short strings, not a nested structure with rationale or evidence.
- Expected output from `agent-ux`: breadcrumb line, plus one line confirming the spec-canvas
  Artifact was published or redeployed to `artifact_path` (same path every time within the
  Requirements phase, per the pull-over-push / stable-URL invariant) — or, if the Artifact tool
  isn't available, one line saying so and stopping, never blocking the caller.
