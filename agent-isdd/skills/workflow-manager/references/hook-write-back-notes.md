# Hook write-back Notes (after-design, after-tasks)

Read by `workflow-manager` at the `after-design` and `after-tasks` hooks to decide which "Facts worth persisting" to write back to agent-nelly (verbatim from SKILL.md's Lifecycle Hooks table, Notes column).

## after-design

`design-author` persists `research-consolidator`'s "File Summaries" (coverage gaps, unexpected interfaces, file-level findings) right after research completion — this is the only research pass in the Phase 2+3 architecture; `research-consolidator` produces design_findings, task_findings, and file_summaries together in one call. At this hook, do not re-persist those summaries (avoid duplication). Instead, persist only design-gate discoveries: tradeoff decisions made during authoring, scope choices between equivalent approaches, risk-classification calls (e.g. a risk promoted from feature-specific to project-wide), or constraints surfaced during checklist evaluation rather than research phase.

## after-tasks

The Design Spec completeness gate is `hooks/design_spec_gate.py`, and `hooks/slice_spec_gate.py` applies only to `Track: Fast`'s Slice Spec handoff — see `INTEROP.md`'s "Design Spec completeness gate" section for both (this row used to misdescribe them). File summaries were already persisted at `after-design` (task-slicing reuses `research-consolidator`'s cached `task_findings`, per `agent-tdd`'s own `INTEROP.md`, rather than re-researching) — nothing to re-persist here. Instead, persist only task-slicing discoveries surfaced back by `agent-tdd`'s escalations or its Design Spec Handoff Report: risk flags raised during task validation, especially `paused` reasons signaling project-wide constraints or missing capabilities (most likely to recur), and slicing approaches abandoned and resliced (as `error lesson` rather than fact).

## after-tasks: Evaluates column (moved verbatim)

**Corrected 2026-09-24**: there is no agent-isdd-evaluated `Tasks` checklist to run here — per Phase 2+3, task slicing happens entirely inside `agent-tdd` during the Design Spec handoff, and `tasks.md` does not exist until `agent-tdd` writes it (see `agent-tdd/agents/agent-TDD.md`'s "Design Spec workflow" step 5 (Readiness) and `agent-tdd/INTEROP.md`'s "Readiness Check & Escalation"). This hook's real trigger is simply "Design is approved and implementation was requested" — the same condition `spec-driven-development`'s Implementation Handoff section already spawns on. Decide handoff / pause-for-implementation-request / pause-for-blocker on that basis. If handing off, exit native plan mode (see "Native Plan Mode Gate") before setting `Current Phase: Implementation` and spawning `agent-tdd:agent-TDD`.

## Nelly write-back paragraph (moved verbatim)

**Nelly write-back (every `after-*` hook, after its Verification Step, only when advancing or
handing off)**: if `agent_nelly_available` is `true`, call `agent-nelly:agent-nelly` with a
`new facts` batch of project-level discoveries from this phase — only facts that would benefit a
future conversation independently of this feature's own artifacts; ephemeral workflow state never
qualifies. If a discovery instead describes a specific approach tried and rejected this phase (not
just a fact about the current state), call `error lesson` instead of folding it into `new facts` —
see `INTEROP.md`'s "→ agent-nelly" section for the full fact-vs-error-lesson criterion. If the
call fails, append a one-line note to `recap.md` and continue — never a blocking condition. The
table's "Facts worth persisting" column states what's specific to each hook and what an earlier
write-back already covers (do not duplicate).
