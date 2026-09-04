# Example Envelope: phase_transition (TDD-internal stage exclusion)

## What this demonstrates

A `phase_transition` envelope where `from_phase`/`to_phase` are TDD-internal stages
(`red` → `green`) rather than one of Requirements/Design/Tasks/Implementation. Per `INTEROP.md`'s
"`caller`-keyed rendering rules" ("TDD-internal stage exclusion"), this must **not** trigger
`mark_chapter` — only the breadcrumb renders. Fills the coverage gap flagged in
`EXPECTED-OUTPUTS.md`'s "Open questions": none of the original 5 fixtures exercised this specific
rule, only the general phase-vs-non-phase case (`phase-transition.md`).

`caller` here is `agent-isdd` — the orchestrating skill that would be resuming/monitoring an
`agent-tdd` slice, per `agent-tdd/INTEROP.md`'s "Rendering TDD-stage progress with agent-ux"
recipe. It is never `agent-tdd` itself: `agent-TDD` (the subagent) has no `Agent` tool and can
never be the literal actor sending this envelope (see `INTEROP.md`'s envelope-shape table). The
exclusion below fires on `from_phase`/`to_phase` being TDD-internal stage names, not on `caller`.

## Envelope

```json
{
  "caller": "agent-isdd",
  "event_type": "phase_transition",
  "phase_state": "TDD:green",
  "delta": {
    "from_phase": "red",
    "to_phase": "green",
    "feature_slug": "2026-07-01-session-timeout-warning-banner",
    "one_line_summary": "Red test written for the countdown-dismiss debounce; entering Green to implement."
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/tasks/tasks.md"
}
```

## Notes

- `delta` has the same exact 4-key shape as any other `phase_transition` envelope — the
  exclusion is decided from the *values* of `from_phase`/`to_phase` alone, not a different
  `delta` shape and not `caller`. There is no separate envelope schema for TDD-internal
  transitions.
- `phase_state: "TDD:green"` is the compact-token form `INTEROP.md`'s envelope-shape table cites
  as an example (`e.g. Design, TDD:green`). Per the Breadcrumb dispatch rule (`agents/ux-agent.md`
  — "`Implementation` renders plain once the handoff to `agent-tdd` has been made — this plugin
  tracks no finer-grained stage detail past that point"), any non-`Requirements`/`Design`/`Tasks`
  `phase_state` collapses to `Implementation` for breadcrumb purposes; the breadcrumb never shows
  `TDD:green` literally.
- Expected output from `agent-ux` (exactly one line — same shape as `breadcrumb-only.md`'s
  output, even though `event_type` here is `phase_transition`, not `breadcrumb_only`):

  ```
  Requirements ▸ Design ▸ Tasks ▸ **Implementation**
  ```

  No chapter-marked line, no error line — the exclusion is silent by design (`INTEROP.md`:
  TDD-internal stage boundaries are excluded "only to the phase-level transitions excluded
  generally," not reported as a misuse or a skipped action).
- Contrast with `phase-transition.md`: same `event_type`, same `delta` key set, **same `caller:
  agent-isdd`** — the only thing that differs is whether `from_phase`/`to_phase` are phase-level
  or TDD-internal stage names. This is deliberate: `caller` alone was never a reliable signal
  (`agent-tdd` can't send envelopes itself), so the exclusion has to be decided from the stage
  names regardless of who's sending on `agent-tdd`'s behalf.
- The rule is verified directly against `agent-tdd`'s own repo (its real six stages: Plan → Red →
  Green → Review → Refactor → Validate), not carried over as an unconfirmed assumption. What's
  still open is adoption, not stage-naming or the exclusion's keying: no orchestrator in this
  ecosystem sends this envelope today (`agent-isdd`'s own handoff to `agent-tdd` is deliberately
  one-directional and doesn't monitor past the initial spawn — see `agent-isdd`'s own
  `INTEROP.md`); this fixture illustrates what a future orchestrator that does would send.
