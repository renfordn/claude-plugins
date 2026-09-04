# Design: agent-isdd cross-cutting token-efficiency pass

## Status

- Phase: Design
- State: Draft
- Last Updated: 2026-08-12

## Design Summary

Five additive, template/skill-level edits — deliberately no new hooks or subsystems, since a new
subsystem would be its own token/maintenance cost and undercut the point of this pass: (1)
structured Non-Functional Constraints fields in `requirements.md`; (2) generalize the existing
brief-reuse convention to `planning-agent`/`spec-reviewer` findings, not just the agent-nelly
brief; (3) a structured `Depends On` task-id list replacing prose "dependency notes" in
`tasks.md`; (4) an explicit Recap-and-Drop rule at phase-approval transitions; (5) a documented
(not retrofitted) "Excluded — and why" house convention for future candidate-triage subagents.

## Research Basis

- Read `hooks/diff_fingerprint.py` directly before designing the drift-check idea carried over
  from this proposal's originating conversation. Its docstring is explicit: it fingerprints only
  this plugin's own `skills/`/`agents/`/`commands/`/`hooks/` directories for
  `doc-consistency-auditor`'s use, and states "`workflow-state.json` carries no diff-fingerprint
  field of its own; that concept belonged to the now-external `code-reviewer` plugin's
  REVIEW-STATE.md tracking, which this plugin does not own." Combined with `README.md`/
  `CHANGELOG.md` 0.1.0's "agent-isdd never touches source files, only planning artifacts," this
  rules a spec-vs-implementation-code drift checker out entirely — it is now a Non-Goal, not a
  deferred task.
- Read `agents/spec-reviewer.md` and `agents/tdd-planner.md` directly to check whether the
  "Excluded — and why" convention (currently only in `agents/planning-agent.md`) has other
  adoption sites. Neither does candidate-file triage: `tdd-planner` defers research to
  `planning-agent` rather than surveying files itself, and `spec-reviewer` reviews one
  caller-given document, not a candidate set. Narrowed this item from a multi-file retrofit to a
  documented convention for whichever future subagent needs it — matches this pass's own
  token-efficiency lens (don't spend edits generalizing a pattern into files it doesn't apply to).
- Read `skills/spec-driven-development/SKILL.md`'s existing 0.1.3 brief-reuse convention (three
  re-fetch triggers: no prior brief in context, a rewind/Mid-Phase Change Classification since,
  an Intent-alignment divergence flagged since) as the pattern to generalize rather than
  reinvent.

## Scope Mapping To Requirements

- Requirement: structured NFR fields
  - Design Response: fixed four-key `## Non-Functional Constraints` section added to
    `requirements.md`'s template.
- Requirement: reuse cached subagent findings within a continuous stretch
  - Design Response: extend the existing three-trigger dedup convention to
    `planning-agent`/`spec-reviewer` returns, identical triggers, no new invalidation logic.
- Requirement: structured task dependency ordering
  - Design Response: `Depends On: [<task-id>, ...]` field added per task in `tasks.md`'s
    template, distinct from the existing narrative `Prerequisites` field.
- Requirement: Recap-and-Drop at phase-approval boundaries
  - Design Response: procedural rule added to `workflow-manager/SKILL.md`; no new field, no new
    hook — `recap.md`'s template is unchanged.
- Requirement: "Excluded — and why" for candidate-triage subagents
  - Design Response: documented as a house convention (new short reference doc), not applied
    to `spec-reviewer`/`tdd-planner`, which don't do candidate-file triage today.
- Requirement: mechanical verification of these conventions
  - Design Response: `doc-consistency-auditor` run against the changed files themselves as part
    of Validation, dogfooding the existing mechanism rather than building a new checker.

## Architecture Or Code Touchpoints

- `references/artifact-templates.md`:
  - `requirements.md` template — new `## Non-Functional Constraints` section (Throughput, Data
    Volume, Concurrency, Latency Budget; each accepts `N/A: <reason>`), placed after `Success
    Criteria` and before `EARS Requirements`.
  - `tasks.md` template — each task phase gains `### Depends On` (bare `task-id` list) alongside
    the existing `### Prerequisites` (narrative/product dependencies stay there, unmerged).
  - `recap.md` template — unchanged; Recap-and-Drop is a procedural rule, not a schema change.
- `skills/workflow-manager/SKILL.md` — add a "Recap-and-Drop" rule: once a phase's Phase
  Completion checklist passes, summarize it into `recap.md`; subsequent prompts in the same
  session reference `recap.md` rather than re-quoting the full prior-phase artifact body. The
  full artifact stays on disk and is re-readable on demand — this rule governs default prompt
  construction, not access.
- `skills/spec-driven-development/SKILL.md` — extend the 0.1.3 brief-reuse convention's scope
  from "the agent-nelly brief" to "the agent-nelly brief, and any `planning-agent`/
  `spec-reviewer` finding still valid," same three triggers, same place this convention is
  already documented (no duplicate definition elsewhere, per this repo's own existing pattern).
- `agents/planning-agent.md` — no change; serves as the canonical example cited by the new
  reference doc.
- New `references/subagent-conventions.md` — documents "Excluded — and why" as the house
  convention for any subagent performing candidate-file triage, citing `planning-agent` as the
  worked example, so a future subagent addition follows it without a fresh design discussion.

## Data Contracts And Interfaces

- Interface: Non-Functional Constraints block
  - Inputs (author time): Throughput, Data Volume, Concurrency, Latency Budget — each a concrete
    value/range or `N/A: <one-line reason>`.
  - Outputs: referenced by key from `design.md`/`tasks.md`, not re-summarized in prose each time.
  - Invariants: never left blank — `N/A` with a reason is a complete, valid value; an actually
    empty field is an Open Gap that blocks the Requirements gate like any other missing section.
- Interface: `Depends On` task field
  - Inputs: list of `task-id` strings referencing other tasks in the same `tasks.md`.
  - Outputs: read by `spec-driven-development`'s Implementation Handoff and by anyone skimming
    readiness, to determine safe execution order without re-reading prose per task.
  - Invariants: ids only, no embedded prose. A task with a genuinely narrative dependency (a
    product/architecture decision, not another task) keeps using `Prerequisites` — the two
    fields are not merged, since collapsing them would reintroduce the prose-parsing cost this
    pass removes.

## States, Flows, And Edge-Case Handling

- Primary flow: `requirements-agent` captures NFR fields once at Requirements time →
  `design-author`/`tdd-planner` reference them by key → `tdd-planner` emits `Depends On` ids
  when slicing tasks → `workflow-manager` applies Recap-and-Drop at each phase-approval boundary
  → `spec-driven-development` reuses cached `planning-agent`/`spec-reviewer` findings per the
  extended three-trigger convention.
- Edge case — no meaningful NFRs: `N/A: <reason>` is accepted; the gate is not blocked by an
  honest "not applicable."
- Edge case — pre-existing in-flight feature missing the NFR block: `workflow-manager`'s
  state-repair path treats a missing (not malformed) NFR section as "not yet backfilled" and
  offers to backfill on the next Requirements touch, rather than failing state-consistency
  checks.
- Edge case — rewind invalidates part of a cached finding: re-fetch is scoped to the invalidated
  file/topic only, per the existing (now-extended) three-trigger convention — never a blanket
  re-fetch of everything cached this session.

## Validation Strategy

- Unit: not applicable — these are documentation/template changes, not executable code; no hook
  or `workflow-state.template.json` field is touched by this proposal.
- Integration: run one real feature end-to-end (Requirements→Design→Tasks) through the updated
  templates and record actual token counts per phase against a comparable baseline feature (the
  existing `references/example-feature/` set), reporting the before/after per Success Criteria.
- Manual: run `doc-consistency-auditor` against every changed file in this pass — dogfooding the
  exact mechanism this proposal leans on to keep the new conventions from drifting the same way
  the 0.1.5 changelog entry (Design Gate summary drift) had to be caught manually.

## Risks And Tradeoffs

- Risk: structured NFR fields become busywork on trivial features, adding a fixed per-feature
  cost that could outweigh savings on features small enough to have no real NFRs.
  - Mitigation: `N/A: <reason>` is a one-line, low-cost valid answer — the fixed floor stays
    small by design; if it proves not small enough in practice, that's a Design-revision signal,
    not a reason to skip the field silently.
- Risk: generalizing the brief-dedup convention to `planning-agent`/`spec-reviewer` findings
  risks reusing a stale finding across a change that should have invalidated it — trading a
  correctness bug for a token saving would be a bad trade.
  - Mitigation: reuse the exact three re-fetch triggers already proven for the agent-nelly brief
    rather than loosening them — no new invalidation logic to get wrong.
- Risk: Recap-and-Drop applied too aggressively could cause a later phase to lose detail it
  actually needed from a dropped full artifact.
  - Mitigation: recap.md summarizes, it doesn't delete — the full artifact remains on disk and
    is re-readable on demand; the rule governs default prompt construction only, never access.

## Improvement Opportunities & Blast Radius

### Blast Radius

Touches `references/artifact-templates.md` (two templates), `skills/workflow-manager/SKILL.md`,
`skills/spec-driven-development/SKILL.md`, and adds one new reference doc. Does not touch
`agents/planning-agent.md`, `agents/spec-reviewer.md`, `agents/tdd-planner.md`, or any hook —
each confirmed either already compliant or genuinely out of scope for this pass (see Research
Basis).

### Security Findings (blocking)

- [ ] None identified.

### Refactor & Reduction Opportunities (non-blocking)

- [ ] `references/example-feature/`'s three worked examples should get one updated example
      showing the new NFR block and `Depends On` field once implemented — otherwise the
      canonical reference silently under-represents the current template.

### Best-Practice Notes (non-blocking)

- [ ] None beyond what's already captured in Risks.

## Open Questions

- [ ] Fixed four-key NFR schema (Throughput / Data Volume / Concurrency / Latency Budget) versus
      an extensible key set. Recommend fixed: cheaper to reference by key across phases, and an
      extensible set risks reintroducing the prose-sprawl this pass is trying to remove. Revisit
      only if a real feature repeatedly needs a fifth key.

## Phase Decision

- [x] Design supports current requirements
- [x] Design is testable
- [x] Design avoids unresolved contradictions
- [x] No unresolved Security Finding remains
- [x] Ready to move to Tasks — the one Open Question (NFR schema shape) has a stated
      recommendation and doesn't block slicing; it can be confirmed as part of Task Phase 1.

## Phase Completion

- [x] Requirement coverage is explicit
- [x] Architecture or code touchpoints are named
- [x] Interfaces or contracts are described
- [x] Validation strategy is credible
- [ ] State can be marked `Approved`
