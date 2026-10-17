# Native Plan Mode Gate

Read by `workflow-manager` before calling `EnterPlanMode` at `before-design`, while drafting Design under plan mode, and before `ExitPlanMode` at handoff (verbatim from SKILL.md).

The Design and Tasks phases *are* the implementation plan — codebase research, architecture, task
breakdown — culminating in the moment code is about to be written. That maps directly onto the
harness's own plan mode, so this workflow rides it instead of only gating through conversational
confirmation:

- On `before-design`, call `EnterPlanMode` before routing into `design-author`. Skip the call (no
  error, no pause) if plan mode is already active — never enter twice.
- **Corrected 2026-09-24 [plan/design gap]**: while native plan mode is active, the harness
  itself restricts file edits to the single plan file it designated when `EnterPlanMode` was
  called — a `Write`/`Edit` to `design.md`, `workflow-state.md`, `research/cache.md`, or any
  agent-nelly memory file is refused outright, not merely discouraged. So Design does *not* write
  markdown "on agent-isdd's side" while plan mode holds, despite what an earlier version of this
  section claimed (one reported instance, unverified here: the model catching itself mid-edit and self-correcting).
  `design-author` instead drafts its full normal output — design summary, Research Basis,
  touchpoints, data contracts, edge cases, validation strategy, risks/tradeoffs, Improvement
  Opportunities, Phase Completion checklist, the `research/cache.md` payload, and the
  `file_summaries` payload destined for agent-nelly — in context, and writes/updates only the
  plan file with that running draft (using `artifact-templates.md`'s structure as its content).
  The plan file *is* the working design document for the duration of plan mode, not a mirror of
  one written elsewhere. `after-design`'s checklist evaluation runs against this in-context/
  plan-file draft exactly as it would against a written `design.md` — nothing about the Design
  Gate itself changes, only where the content physically lives until approval.
- **Corrected 2026-09-24 [plan/design gap]**: once the user approves the plan (`ExitPlanMode`
  returns approved), persist the finalized draft to the real artifacts in one step before moving
  on: write `design.md` from the approved content, create `research/cache.md`, persist
  `file_summaries` to agent-nelly (its dedicated `file summaries` request field, plus `folder
  summaries` and `research digest` — not a `new facts` batch), and write `workflow-state.md` (`Design`
  phase `State: Approved`, plus any design-gate discoveries queued during authoring — see
  `after-design`'s "Facts worth persisting" above). `tasks.md` does not exist at this point — per
  Phase 2+3, `agent-tdd` produces it (and runs its own Readiness Check) inside the same spawn that
  also implements, not as a prior agent-isdd-owned phase (see `INTEROP.md`'s "→ agent-tdd"
  section) — so nothing Tasks-shaped is written here either. If Design fails its gate or hits a
  blocker before the user approves the plan, report it through the plan file's content and the
  conversation, the same as any other plan-mode revision — never through the state files, since
  those still cannot be written until the plan is approved (or plan mode was never entered — see
  the availability fallback below).
- Only call `ExitPlanMode` once Design is approved and implementation has been requested — the
  same gate the `handoff` action already requires, not a separate or looser one.
- If `EnterPlanMode`/`ExitPlanMode` aren't available, or a call fails for a reason unrelated to
  the checklist (host declines, tool not present), fall back silently to the existing
  conversational Design Gate / Task Readiness confirmation already required elsewhere — and, in
  that fallback only, `design-author` writes `design.md`/`research/cache.md`/`workflow-state.md`
  as it goes, the same as any other phase, since no plan-mode file restriction is in effect there.
  Never block phase progress on plan-mode availability.
- A user-declined `EnterPlanMode` is a pause condition like any other missing confirmation (see
  `pause` in Action Rules), not a reason to proceed without it.
