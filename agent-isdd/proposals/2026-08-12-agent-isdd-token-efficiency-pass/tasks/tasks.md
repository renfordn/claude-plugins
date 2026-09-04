# Tasks: agent-isdd cross-cutting token-efficiency pass

## Phase Status

- Current Phase: Tasks
- State: Ready For Implementation
- Last Updated: 2026-08-12

## Execution Rules

- Preserve approved requirements and design intent: additive only, no Phase Completion /
  Approval Checkpoint / Task Readiness Checklist item shrinks without an equivalent replacement.
- Keep slices to one behavior change and/or one file or module touched if possible.
- Tests first where implementation follows — for these template/skill-text changes, "test" means
  the Validation Target's worked-example or auditor run, not code unit tests.
- Refactor only after green.
- Pause on ambiguity, conflicting constraints, weak testability, high-risk migration, or oversized
  tasks.
- Tag each task's Risk Tier (`standard` or `high-risk`) per design.md's Risks And Tradeoffs
  section.
- `Depends On` uses this proposal's own new task-id convention (Phase 6, step 1 dogfoods it) —
  bare ids, no embedded prose; a genuinely narrative dependency stays in `Prerequisites` instead.

## Phase 1: Non-Functional Constraints block

### Objective

Add the fixed four-key `## Non-Functional Constraints` section to `references/artifact-templates.md`'s
`requirements.md` template, resolving design.md's one Open Question (fixed schema, recommended
there) as part of this task rather than leaving it open.

### Risk Tier

- `standard` — additive template section, no existing field removed or renamed.

### Prerequisites

- None.

### Depends On

- []

### Ordered Steps

1. Insert `## Non-Functional Constraints` into the `requirements.md` template, positioned after
   `Success Criteria` and before `EARS Requirements` (per design.md's Architecture section).
2. Fixed keys: `Throughput`, `Data Volume`, `Concurrency`, `Latency Budget`. Each accepts a
   concrete value/range or `N/A: <one-line reason>`.
3. Add an `Approval Checkpoint` line: "Non-Functional Constraints are populated (value or
   explicit N/A)" — mirrors how every other section already gates the checkpoint; do not let
   this section skip the pattern the rest of the template already uses.
4. Update `requirements-agent/SKILL.md`'s interview-mode question list to include eliciting NFRs
   (one question, closed-set-friendly per its existing `AskUserQuestion` preference) so the field
   isn't silently left blank in practice.

### Test Intent

- Add or update:
  - One worked example in `references/example-feature/` (pick the feature whose NFRs are least
    trivial to show a non-`N/A` case — assess during execution) gets its `requirements.md`
    updated to include the new section.
- Expected failing behavior:
  - Before this task, nothing in the template or `requirements-agent` prompts for NFRs, so a
    reviewer has no structured place to check for them — that's the gap this task closes.

### Validation Target

- Command:
  - Manual: confirm the new section round-trips through one real Requirements-phase run
    (interview mode) producing either concrete values or explicit `N/A: <reason>` for all four
    keys, never a blank.
- Evidence:
  - Updated worked example plus one live interview transcript showing the new question being
    asked.

### Unlocks

- Enables:
  - Phase 6 (worked-example refresh) needs this section's final shape before it can update
    `references/example-feature/`.

### Blockers Or Escalation

- [ ] None.

## Phase 2: `Depends On` task field

### Objective

Add a structured `### Depends On` (bare `task-id` list) field per task phase in the `tasks.md`
template, distinct from and alongside the existing narrative `### Prerequisites`.

### Risk Tier

- `standard` — additive field, `Prerequisites` unchanged and unmerged (design.md explicitly
  rejects merging them).

### Prerequisites

- None.

### Depends On

- []

### Ordered Steps

1. Insert `### Depends On` into the `tasks.md` template's per-phase structure, directly after
   `### Prerequisites`.
2. Document the field's contract inline in the template: ids only, references other task ids in
   the same `tasks.md`, empty list `[]` when a task has no task-level dependency.
3. Update `tdd-planner/SKILL.md`'s task-slicing rules to emit `Depends On` ids when it slices
   tasks with a genuine ordering dependency, replacing its current informal "dependency notes"
   mention (agents/tdd-planner.md line 42) with a pointer to the new structured field.
4. Update `INTEROP.md`'s Slice Spec field-mapping table only if `Depends On` is relevant to the
   `agent-tdd` handoff (assess during execution — likely not needed for a single-slice handoff,
   confirm rather than assume before touching that file).

### Test Intent

- Add or update:
  - Same worked example chosen in Phase 1, or a second one if that feature's tasks have no real
    dependency to demonstrate — `tasks.md` gets at least one non-empty `Depends On` list.
- Expected failing behavior:
  - Before this task, task ordering is only visible as prose, so nothing can mechanically check
    "is task 3 actually safe to start before task 2 finishes" — that check has no structured
    input to run against yet.

### Validation Target

- Command:
  - Manual: confirm `tdd-planner` produces a valid, non-prose `Depends On` list on a live Tasks-
    phase run with a genuine multi-task dependency.
- Evidence:
  - Updated worked example; `INTEROP.md` either updated or explicitly confirmed not needed, not
    left unaddressed.

### Unlocks

- Enables:
  - Phase 6's worked-example refresh.

### Blockers Or Escalation

- [ ] None.

## Phase 3: Recap-and-Drop rule

### Objective

Add the Recap-and-Drop procedural rule to `skills/workflow-manager/SKILL.md`: once a phase's
Phase Completion checklist passes, summarize into `recap.md`; subsequent same-session prompts
reference `recap.md` rather than re-quoting the full prior-phase artifact body by default.

### Risk Tier

- `standard` — procedural rule addition, no schema change, `recap.md` template untouched (per
  design.md's Architecture section).

### Prerequisites

- None.

### Depends On

- []

### Ordered Steps

1. Add a "Recap-and-Drop" subsection to `workflow-manager/SKILL.md` at the point where phase
   transitions are already handled, stating the rule and its one explicit exception: the full
   artifact stays on disk and is re-readable on demand — this governs default prompt
   construction only, never access.
2. Cross-check `spec-driven-development/SKILL.md` and `design-author`/`tdd-planner` SKILL.md
   files for any place that currently re-quotes a full prior-phase artifact by default, and
   update those callsites to reference `recap.md` instead, per design.md's Risks mitigation
   (recap summarizes, doesn't delete).

### Test Intent

- Add or update:
  - None new — this task's correctness is checked via the worked example's session transcript
    in Validation Target.
- Expected failing behavior:
  - Before this task, nothing stops a skill from re-quoting a full approved `requirements.md`
    into a Design-phase prompt "just in case" — that's the unbounded-cost pattern this rule
    closes off.

### Validation Target

- Command:
  - Manual: run one real feature through Requirements→Design→Tasks, inspect the actual prompts
    constructed at each phase transition, confirm prior-phase content is referenced via
    `recap.md` summary, not re-pasted in full.
- Evidence:
  - Session transcript showing the rule held at at least one phase transition.

### Unlocks

- Enables:
  - Phase 6's token-count comparison depends on this rule actually being followed to show a
    measurable difference.

### Blockers Or Escalation

- [ ] None.

## Phase 4: Generalize the brief-reuse convention

### Objective

Extend `spec-driven-development/SKILL.md`'s existing three-trigger brief-reuse convention (no
prior brief in context / a rewind or Mid-Phase Change Classification since / a divergence flagged
since) from covering only the agent-nelly brief to also covering `planning-agent`'s and
`spec-reviewer`'s returned findings within the same continuous stretch of phase work.

### Risk Tier

- `high-risk` — design.md's Risks section flags this specifically: reusing a stale finding
  across a change that should have invalidated it trades a token saving for a correctness bug.
  Must reuse the exact existing triggers, not loosen them.

### Prerequisites

- None (independent of Phases 1-3).

### Depends On

- []

### Ordered Steps

1. Locate the exact 0.1.3 convention text in `spec-driven-development/SKILL.md` (the single
   documented fetch point for the agent-nelly brief).
2. Extend its stated scope to include `planning-agent`/`spec-reviewer` findings, same three
   triggers, explicitly noting this is the identical rule applied to a wider set of cached
   content — not a new rule.
3. Update `design-author/SKILL.md` and `tdd-planner`'s caller-side logic (where they currently
   invoke `planning-agent`) to check for a still-valid cached finding before re-delegating,
   mirroring how they already check for a reusable agent-nelly brief.
4. Explicitly re-verify each of the three triggers against a finding-cache scenario (not just the
   brief scenario it was written for) to confirm none of them silently assumed brief-specific
   semantics that don't hold for a `planning-agent` finding.

### Test Intent

- Add or update:
  - None new — validated via the Phase 6 worked-example rerun showing a skipped re-delegation
    where one would previously have happened.
- Expected failing behavior:
  - Before this task, `design-author` and `tdd-planner` always call `planning-agent` fresh
    within one continuous stretch even when nothing invalidated a prior finding — that's the
    redundant call this task removes.

### Validation Target

- Command:
  - Manual: run a Design→Tasks sequence within one session where `tdd-planner` would need
    `planning-agent` research already produced during Design; confirm it reuses the cached
    finding instead of re-invoking.
- Evidence:
  - Session transcript showing the skip, plus confirmation a rewind in the same session still
    correctly triggers a re-fetch (the trigger logic must still work, not just the reuse path).

### Unlocks

- Enables:
  - Phase 6's token-count comparison — this is likely the single largest saving in the pass,
    since a full `planning-agent` re-invocation is expensive.

### Blockers Or Escalation

- [ ] None, but flagged `high-risk` — do not skip step 4's explicit re-verification.

## Phase 5: Document the "Excluded — and why" house convention

### Objective

Write `references/subagent-conventions.md` documenting "Excluded — and why" as the expected
return-contract section for any subagent that performs candidate-file triage (evaluates more
candidates than it deep-reads), citing `agents/planning-agent.md` as the canonical, already-
compliant example. No change to `planning-agent.md`, `spec-reviewer.md`, or `tdd-planner.md`
themselves — confirmed in design.md's Research Basis that only `planning-agent` currently does
this kind of triage.

### Risk Tier

- `standard` — pure documentation addition, zero behavioral surface today.

### Prerequisites

- None.

### Depends On

- []

### Ordered Steps

1. Write `references/subagent-conventions.md` with one section: what candidate-file triage is,
   why "Excluded — and why" matters (padding a report with irrelevant files costs tokens without
   adding signal), and the worked citation from `planning-agent.md`.
2. Add a one-line pointer to this new file from `agents/planning-agent.md`'s own guardrails
   section, so the convention's canonical home is discoverable from the example itself, not just
   the other direction.
3. Note explicitly in the new file that `spec-reviewer` and `tdd-planner` are confirmed
   non-applicable today (single-document review; delegated research respectively) so a future
   contributor doesn't retrofit it onto them without re-checking that premise still holds.

### Test Intent

- Add or update:
  - None — documentation only, no artifact output to validate against a live run.
- Expected failing behavior:
  - N/A.

### Validation Target

- Command:
  - `doc-consistency-auditor` run against the new file plus `planning-agent.md`'s updated
    pointer, confirmed as part of Phase 6's audit pass rather than run standalone.
- Evidence:
  - No new contradiction or dangling reference flagged.

### Unlocks

- Enables:
  - Nothing else in this pass depends on it; it exists to prevent future duplicated effort, not
    to unlock a subsequent task.

### Blockers Or Escalation

- [ ] None.

## Phase 6: Worked-example refresh and token-count validation

### Objective

Update `references/example-feature/`'s worked examples to reflect the new template fields, run
`doc-consistency-auditor` across every file touched by this pass, and produce the before/after
token comparison design.md's Validation Strategy and requirements.md's Success Criteria both
require.

### Risk Tier

- `standard` — validation and documentation-sync task; no new behavior introduced here, only
  measured and recorded.

### Prerequisites

- Phases 1-4 complete (final field shapes and the extended reuse convention must be settled
  before the comparison is meaningful).

### Depends On

- [Phase 1, Phase 2, Phase 3, Phase 4]

### Ordered Steps

1. Pick one `references/example-feature/` entry and regenerate its `requirements.md`/`tasks.md`
   sections to include the new NFR block and `Depends On` field, keeping everything else
   unchanged so the diff isolates exactly what this pass added.
2. Run `doc-consistency-auditor` against all files touched across Phases 1-5
   (`artifact-templates.md`, `workflow-manager/SKILL.md`, `spec-driven-development/SKILL.md`,
   `requirements-agent/SKILL.md`, `design-author/SKILL.md`, `tdd-planner/SKILL.md`,
   `references/subagent-conventions.md`, `agents/planning-agent.md`) and resolve any finding
   before closing this phase.
3. Measure token counts for one real feature's Requirements→Design→Tasks run against the updated
   templates/conventions, compared to a comparable pre-change baseline (the unmodified
   `references/example-feature/` entries serve as the baseline reference point).
4. Record the comparison in `CHANGELOG.md`'s next version entry, in the same style as the 0.1.3
   precedent ("368→360 lines"), per requirements.md's Success Criteria.

### Test Intent

- Add or update:
  - The regenerated worked example itself is the test artifact.
- Expected failing behavior:
  - A `doc-consistency-auditor` finding on any of the touched files is this phase's red
    condition — must resolve before marking Tasks complete.

### Validation Target

- Command:
  - `doc-consistency-auditor` run (per Execution Rules, invoked as a skill, findings via
    `ReportFindings`).
- Evidence:
  - Zero unresolved findings; recorded token comparison meeting requirements.md's Success
    Criteria (concrete before/after, no checklist item shrunk without replacement).

### Unlocks

- Enables:
  - Closes out this proposal's stated success criteria; nothing further depends on this phase.

### Blockers Or Escalation

- [ ] If the measured comparison shows a net token *increase* for any phase, escalate back to
      the relevant Phase (1-4) for revision rather than recording a regression as accepted.

## Task Readiness Checklist

- [x] At least one concrete implementation phase exists
- [x] Each phase has explicit objective, Risk Tier, steps, test intent, and validation target
- [x] Slices are safe for TDD-equivalent (worked-example-first) execution
- [x] No unresolved blocker requires confirmation before implementation
- [x] State can be marked `Ready For Implementation`
