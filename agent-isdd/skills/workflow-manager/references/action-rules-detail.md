# Action Rules detail (continue / handoff) and the Tasks row

Read by `workflow-manager` when `Current Phase: Tasks` is the current phase on `continue`, when completing a `handoff` (resync of stale fields), and when evaluating the Tasks row of Phase Pass/Fail Rules (verbatim from SKILL.md).

## `continue`: Tasks special case

**`Current Phase: Tasks` special case (added 2026-09-24)**: there is no Tasks-phase artifact or checklist to evaluate here (see the `Tasks` row of "Phase Pass/Fail Rules" below) — `Current Phase: Tasks` only ever arises as a rollback-landing state, whether reached via `/isdd-rewind Tasks` directly or an automatic/human-relayed rollback request (see `INTEROP.md`'s "← agent-tdd / code-reviewer (rollback request)" and `MIGRATION_GUIDE.md`'s "Can I rewind to Tasks phase?"). Treat it as "ready for (re-)implementation handoff": re-invoke `spec-driven-development`'s Implementation Handoff step directly, rebuilding the Design Spec from the still-approved `requirements.md`/`design.md` (plus fresh research on request) and re-spawning `agent-tdd:agent-TDD` — never re-enter Requirements or Design authoring for this case alone.

## `handoff`: resync after the spawn returns

Once that spawn returns its report, set `Workflow Status: Complete` **and, in the same write, resync every field that still reflects the pre-handoff state**: `### Tasks`'s `Status` (to `Complete`), `Current Owner` (to `Completed` or the completing agent), `Final Handoff` (today's date), `Next Action` (to `None`, or a concrete post-completion action like a pending release — never left at its pre-handoff value), and the `Notes` section (replace stale pre-implementation notes — e.g. "N slices to be defined" — with the actual outcome: slice count, test results, from the spawn's report/`recap.md`). Do not leave any field describing an in-progress or not-yet-started state once the spawn has returned success; track no further implementation-stage state beyond this sync.

## Phase Pass/Fail Rules: Tasks row

**Pass when:** **Corrected 2026-09-24**: not evaluated by `agent-isdd` — per Phase 2+3, task slicing and its Readiness Check happen entirely inside `agent-tdd` during the Design Spec handoff, using `agent-tdd`'s own slice-based schema (`agent-tdd/references/tasks-schema.json`), not a phase-based one. `agent-isdd` never writes or gates a pre-handoff `tasks.md`; what this row used to describe is `agent-tdd`'s own Readiness step (`agent-tdd/agents/agent-TDD.md`'s "Design Spec workflow" step 5) returning `Ready For Implementation` via its `slicing_complete` marker. Applies to `Track: Standard` only — `Track: Fast` never produces a `tasks.md` at all (see "Track Field Contract" above).

**Fail when:** N/A on agent-isdd's side — see `agent-tdd/INTEROP.md`'s "Readiness Check & Escalation" for `agent-tdd`'s actual fail/escalation conditions (research gap, design contradiction, slicing blocked, high-risk unsplittable).
