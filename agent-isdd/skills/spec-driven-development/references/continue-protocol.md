# Continue Protocol

Read by `spec-driven-development` when continuing or resuming a feature (`/isdd-continue`, "continue", "resume"): steps 0-4 including the Rollback Request Check (verbatim from SKILL.md).

0. **Rollback Request Check:**
   - The `before_continue` hook automatically checks for pending rollbacks from prior agent-tdd runs.
   - If agent-tdd found a slicing blocker (task conflicts, design contradiction, research gap), the rollback will be surfaced with reasoning and recommended target phase.
   - Address the issue and rewind using `/isdd-rewind <target>`, then return to continue the workflow.

1. Use `workflow-manager` to find the relevant feature folder and resolve state (see its
   Decision Order — `agent-nelly:agent-nelly`'s stored Intent first (when available),
   then `workflow-state.md`, then `workflow-state.json`, then open blockers, then phase files,
   then `recap.md`).
2. **[Phase 1.2]** Check the cached nelly brief in `workflow-state.json` → `nelly_brief_cache`;
   reuse it if valid, else fetch fresh (rules: `workflow-manager`'s Goal Field Contract).
3. Continue from the earliest blocked or incomplete phase; auto-advance through later phases
   whose entry gates are satisfied.
4. Pause only when a gate fails, a confirmation checkpoint is required, or implementation was
   not requested.

Do not restart from Requirements if a later phase is already the active incomplete phase,
unless requirement changes invalidate the design or tasks.
