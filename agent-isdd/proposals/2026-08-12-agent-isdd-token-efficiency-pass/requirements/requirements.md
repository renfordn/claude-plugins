# Requirements: agent-isdd cross-cutting token-efficiency pass

## Status

- Phase: Requirements
- State: Draft
- Last Updated: 2026-08-12

## Source Inputs

- Origin: idea (in-conversation exploration, set aside as a follow-up from the agent-ux proposal)
- References:
  - `CHANGELOG.md` 0.1.3 (existing precedent: brief-reuse convention, line-count reduction
    reported as "368→360 lines")
  - `agents/planning-agent.md` (existing "Excluded — and why" convention)
  - `hooks/diff_fingerprint.py`, `README.md`, `CHANGELOG.md` 0.1.0 ("agent-isdd never touches
    source files, only planning artifacts")

## Problem Statement

Several planning-phase touchpoints spend more tokens per phase/session than the information they
carry requires. Non-functional constraints live only as free prose inside `design.md`'s Risks
section rather than compact fields visible to every phase that needs them. Task-to-task ordering
is narrated in prose ("dependency notes") rather than referenced by id. And conventions already
proven in one place — the agent-nelly brief-reuse rule, `planning-agent`'s exclusion reporting —
aren't consistently generalized to the other places the same pattern would help. None of this is
a correctness gap; it's overhead that compounds across every feature the plugin processes.

## User Outcome

- Materially lower token spend per phase-cycle for equivalent workflow rigor — same EARS
  coverage, same gate checklists, no capability lost.
- Savings come from structure and reuse, not from cutting content.

## Constraints

- [ ] No change may remove or weaken an existing Phase Completion / Approval Checkpoint / Task
      Readiness Checklist item — savings must come from format and reuse, not scope cuts.
- [ ] Must stay inside `agent-isdd`'s existing stated scope: it "never touches source files, only
      planning artifacts" (README / CHANGELOG 0.1.0) — rules out any mechanism that reads or
      diffs the user's actual implementation code.
- [ ] Additive to `references/artifact-templates.md` — new fields must be optional/backward-
      compatible so in-flight features whose artifacts predate them (missing NFR block, missing
      `Depends On`) remain valid, not corrupted state.
- [ ] Reuse existing mechanisms (`doc-consistency-auditor`, the agent-nelly brief-dedup
      convention, `planning-agent`'s exclusion pattern) instead of inventing new hooks or
      subsystems — a new subsystem is its own token and maintenance cost, which would undercut
      the point of this pass.

## Non-Goals

- [ ] A spec-vs-implementation drift checker against the user's actual codebase. An earlier
      framing of this idea (in conversation, before this repo's own scope was checked) is
      corrected here: `hooks/diff_fingerprint.py` is explicitly scoped to this plugin's *own*
      `skills/`/`agents/`/`commands/`/`hooks/` directories for `doc-consistency-auditor`'s use,
      and its docstring states plainly that "workflow-state.json carries no diff-fingerprint
      field of its own; that concept belonged to the now-external `code-reviewer` plugin's
      REVIEW-STATE.md tracking, which this plugin does not own." Building a spec-vs-code checker
      here would either duplicate `code-reviewer`'s already-external responsibility or violate
      `agent-isdd`'s own stated boundary. Dropped, not carried forward.
- [ ] The `agent-ux` plugin extraction — tracked separately in
      `proposals/2026-08-12-agent-ux-plugin-extraction/`.
- [ ] Redesigning EARS format or the phase-gate structure itself.

## Dependencies

- [ ] `references/artifact-templates.md` (NFR block, `Depends On` field).
- [ ] `skills/spec-driven-development/SKILL.md`'s existing brief-reuse / re-fetch-trigger
      convention (0.1.3) as the pattern to generalize.
- [ ] `agents/planning-agent.md`'s existing "Excluded — and why" convention as the pattern to
      generalize, scoped correctly (see Design — confirmed no other current subagent needs it).
- [ ] `skills/doc-consistency-auditor/SKILL.md` as the existing drift-detection mechanism to
      dogfood, not a new one to build.

## Edge Cases

- [ ] A feature has genuinely no meaningful non-functional constraints — the block must accept
      an explicit `N/A: <reason>` rather than force fabricated content or block the gate.
- [ ] A pre-existing in-flight feature's `requirements.md` predates the NFR block —
      `workflow-manager`'s repair/continue path must treat its absence as "not yet backfilled,"
      not as corrupted state.
- [ ] A rewind invalidates only part of a cached subagent finding (e.g. one file's worth) —
      re-fetch must be scoped to the invalidated subset, not force a full re-fetch of every
      finding cached this session.

## Success Criteria

- [ ] Each accepted change states a concrete before/after token or line comparison (mirroring
      CHANGELOG 0.1.3's own "368→360 lines" precedent), not just a qualitative claim.
- [ ] No Phase Completion / Approval Checkpoint / Task Readiness Checklist shrinks in item count
      without an equivalent replacement.
- [ ] `doc-consistency-auditor` (or an existing hook) can mechanically verify the new conventions
      are followed, rather than relying on the model remembering them unprompted each session.

## EARS Requirements

- `Ubiquitous`: When `requirements-agent` captures non-functional constraints, the system shall
  store them as fixed-key structured fields (Throughput, Data Volume, Concurrency, Latency
  Budget), not paragraph prose.
- `Event-driven`: When a subagent's finding remains valid and referenced across multiple later
  calls within one continuous stretch of phase work, the calling skill shall reuse the cached
  finding instead of re-invoking the subagent for the same content.
- `Event-driven`: When a rewind or Mid-Phase Change Classification invalidates only part of a
  cached finding, the calling skill shall re-fetch only the invalidated subset.
- `State-driven`: While a phase is gate-approved, the calling skill shall summarize it into
  `recap.md` and treat the full phase artifact as filesystem-of-record rather than re-quoting it
  into prompts for the remainder of the session.
- `Optional-feature`: Where a subagent performs candidate-file triage (evaluates more files than
  it deep-reads), its return contract shall include an "Excluded — and why" section.
- `Unwanted-behavior`: If a new artifact-template field is added without a documented backward-
  compatibility rule for pre-existing in-flight features, `doc-consistency-auditor` shall flag
  the resulting drift.

## Open Gaps

- [ ] Exact NFR field set — fixed four-key schema versus extensible — deferred to Design.
- [ ] Which specific skills' subagent-output caching actually has anything to dedup (some skills
      already call their subagent once per phase and have nothing to reuse) — deferred to Design,
      requires checking each skill's actual call pattern rather than assuming.

## Approval Checkpoint

- [ ] Problem statement is clear
- [ ] User outcome is clear
- [ ] Constraints are clear
- [ ] Non-goals are clear
- [ ] Dependencies are clear
- [ ] Edge cases are clear
- [ ] Success criteria are clear
- [ ] EARS requirements are present
- [x] No unresolved ambiguity remains — two Open Gaps are explicit Design-phase decisions, not
      hidden assumptions.

## Phase Completion

- [ ] All required requirement sections are populated
- [ ] Open Gaps contains no blocking unresolved item
- [ ] State can be marked `Approved`
