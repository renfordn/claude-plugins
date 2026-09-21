# State Repair Rules

Treat `workflow-state.md` as stale when: a later phase file has a newer `Last Updated` with an
approved state, the recorded current phase is earlier than the newest approved phase, the stored
pause reason doesn't match the actual blocker, or the stored next action doesn't match the
earliest incomplete phase. When repairing: prefer the newest internally consistent artifacts,
update `workflow-state.md`, note the repair in `recap.md`, never silently discard unresolved
contradictions, keep phase pass/fail status aligned with the repaired state.

A `workflow-state.json` missing the `agent_nelly_available` field (an in-flight feature whose
file predates it) is not a staleness/error condition — treat it as "not yet checked" and let the
next `before-continue` hook populate it via the Availability Check.
