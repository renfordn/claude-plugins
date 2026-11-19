# Code-Reviewer Checkpoint Tracking (High-Risk Slices)

Canonical description of how reviews are recorded and enforced. `<feature spec dir>/tasks/tasks.md`
carries each slice's `**Risk Tier:**`; `workflow-state.json` carries the `reviewed` map.

## Recording a review

`review_tracking` is the sole writer of the `reviewed` map in `workflow-state.json`. The path is
SubagentStop → `subagent_dispatch` → `high_risk_reviewer.main` → `review_tracking.evaluate`.

A review counts only when the code-reviewer stop carries both `<!--CODE-REVIEWER-REPORT-->` and
`<!--REVIEW-SCOPE: slice=N-->`. code-reviewer emits that scope marker when its prompt contains the
literal line `Review scope: slice=N`, so every review prompt for a slice must include it. A report
without the scope marker, or from any other agent, records nothing.

## Enforcement

- `complete_guard` blocks setting `Workflow Status: Complete` in two cases: a slice whose Risk Tier is
  `high-risk` has no `reviewed` entry, or the feature has `Risk: high` and any slice has no
  `reviewed` entry (with no tasks.md, at least one reviewed entry is required).
- `stop_check` is the backstop for writes the guard cannot see (e.g. Bash): on a recently Complete
  feature with unreviewed high-risk slices it blocks the stop once per change.
- `high_risk_reviewer` also emits a passive reminder listing unreviewed high-risk slices; it does not
  invoke code-reviewer or classify severity. Running code-reviewer, resolving findings and resuming
  work go through the ordinary review pause (see `agent-tdd/INTEROP.md` and this plugin's
  `INTEROP.md` "Code-Review Gate").

## Review Fallback

When the user explicitly accepts missing reviews, record the line
`Accepted via AskUserQuestion: <ids|all>: <reason>` as `Review Fallback` in `workflow-state.md`,
only after the user agrees via `AskUserQuestion`. It clears only the named slice ids; `all` clears
every slice, including the feature-level `Risk: high` rule. Any other text waives nothing.
