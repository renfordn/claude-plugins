# Rewind Contract, Rollback Request Intake, Mid-Phase Change Classification — full details

## Rewind Contract

`commands/isdd-rewind.md` delegates all rewind state-mutation logic to this contract.

A rewind request names a target phase (`Requirements`, `Design`, or `Tasks`) earlier than or
equal to the current `Current Phase`. On a valid rewind:

- Set `Current Phase` (both files) backward to the target phase.
- Set `Workflow Status`/`phase_state` for re-entry (typically `In Progress`); clear
  `Pause Reason`/`pause_reason` only if the pause was specific to the phase being left.
- Do not clear, reset, or overwrite the `Status`/blocked fields of any later phase — rewinding
  only moves the *current* pointer, never retroactively resolves later-phase state.
- Log the rewind (from, to, actor, timestamp) in `recap.md` and as a `hook_history` entry.
- If the target is later than `Current Phase` or doesn't exist, refuse and pause with a concrete
  reason.

## Rollback Request Intake

Part of `before-continue` — checked first, before anything else in that hook.

A rollback request reaches agent-isdd two ways, per `INTEROP.md`'s "← agent-tdd / code-reviewer
(rollback request)" section: automatically, via `rollback_pending` in `workflow-state.json`
(written by `hooks/subagent_report.py` when it recognizes the marker on `agent-tdd`'s initial
spawn report), or via human-relay, when the marker text appears directly in the user's message
re-entering agent-isdd.

On either form:

- Determine the target phase from the request. If it doesn't clearly map to what changed, default
  to the more conservative (earlier) phase rather than guessing narrowly.
- Invoke the existing Rewind Contract at that target phase — the only mutation path; don't
  duplicate its state-mutation logic here.
- Clear `rollback_pending` (via `sdd_state.clear_rollback_pending`) once the rewind is applied.
- Log the event in `recap.md` distinctly from a routine rewind — e.g. "Rollback
  (mid-implementation): <from> → <to>, reason: <reason>" rather than the Rewind Contract's plain
  "Rewind: <from> → <to>" phrasing — so a later reader can tell a rollback (triggered by an
  implementation-side finding) apart from a routine user-initiated rewind.
- Applies even when `Workflow Status` is `Complete` — `before-continue` is the standard re-entry
  point regardless of prior status, so a rollback request reopens the workflow at the target phase
  rather than requiring manual state repair.
- **Loop prevention**: if the same target phase is requested twice in a row, pause and surface the
  repetition to the user rather than rewinding again automatically.

## Mid-Phase Change Classification

When the user raises a new idea or a differing task while Design or Tasks is the active phase,
classify the change before reacting, reusing the Rewind Contract for its only mutation path:

- Does satisfying the change require editing an **already-approved earlier phase's own
  artifact** — a `requirements.md` EARS/constraint/non-goal for a Design-phase idea, or a
  `design.md` Architecture/Data-Contracts-And-Interfaces section for a Tasks-phase idea? →
  **earlier-phase invalidation** → invoke the Rewind Contract to that phase.
- Does it only require editing the **current phase's own artifact**, staying inside what that
  phase already owns? → **current-phase refinement** → redo the current phase in place; no
  `Current Phase` change.
- If ambiguous, ask exactly one narrow question: "Does this change *what* we're building (would
  require editing `requirements.md`) or *how* we're building it (stays inside
  `design.md`/`tasks.md`)?"
- Always record the classification, its reasoning, and the branch taken in `recap.md`, so a later
  reader can see why a mid-phase change did or didn't trigger a rewind.
