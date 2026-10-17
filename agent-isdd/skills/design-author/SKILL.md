---
name: design-author
description: "[Internal — use /isdd instead] Turns approved requirements into a testable design.md, grounded in agent-nelly's brief (if available) and research-consolidator's unified codebase research."
---

# Design Author

## Use This Skill When

After Requirements are approved and before detailed task planning starts. Typical inputs:
approved `requirements.md`, a reviewed PRD/ticket that already passed the requirements gate, or
migration notes needing implementation-facing design.

## Plan-Mode Drafting

`workflow-manager` puts this skill's work inside native plan mode (see its SKILL.md's "Native
Plan Mode Gate"). While that's active, the harness allows editing only the one plan file it
designated — every `design.md` / `research/cache.md` / agent-nelly-persistence instruction below
means "draft this content and hold it (in context, and in the plan file as the visible working
copy)" until the user approves the plan, not "write this file now." Only once `ExitPlanMode`
returns approved does any of it actually get written to disk, in one step, per
`workflow-manager`'s contract. If plan mode was never entered or isn't available (the
availability-fallback case in `workflow-manager`'s SKILL.md), write these files as you go instead
— there's no restriction to defer against in that case.

## Research First (Phase 2+3 revised)

Before drafting, delegate to subagents rather than relying only on what's already in context:

1. `agent-nelly:agent-nelly` — reuse the brief the caller passed down; call agent-nelly
   directly only per the re-fetch triggers defined in `spec-driven-development`'s Goal-Aware
   Memory section, when agent-nelly is available (per the Availability Check defined in
   `workflow-manager/SKILL.md`). When a fresh call is made, it returns a holistic brief (Intent,
   prior decisions, open risks, relevant past entries, Intent-alignment check). Seed
   `research-consolidator` with it (whether reused or freshly fetched) so it isn't re-deriving
   project context the memory already has.

   Read `references/nelly-cache-lookup.md` when you call agent-nelly for the brief: on that same
   call pass `file summary lookup` and `research digest lookup`. It holds the **[File & Folder
   Summary Cache]** and **[Research Digest Cache]** read-side steps (hash-verify cache hits, pass
   confirmed paths and `fresh`/`stale` digests down to `research-consolidator`).

2. **[Phase 2+3]** `research-consolidator` — unified codebase research (single pass) that produces
   **dual output:**
   - `design_findings` — architecture touchpoints, interfaces, design risks (for design.md)
   - `task_findings` — file boundaries, test surfaces, slicing constraints (cached for agent-tdd)
   - `file_summaries` — per-file summaries for agent-nelly cache (cross-feature reuse)

   Reuse a still-valid `research-consolidator` finding already fetched earlier in this same
   continuous stretch of phase work (per `spec-driven-development`'s extended brief-reuse
   convention and its three re-fetch triggers) instead of re-delegating for the same touchpoints.
   
   For each named touchpoint file `research-consolidator` reports at or over the resolved
   `Line-Count Ceiling`, add one bullet to `design.md`'s existing `Refactor & Reduction
   Opportunities (non-blocking)` section: `<path>: <line_count> lines, at/over the
   <ceiling>-line ceiling (source: <AGENTS.md | CLAUDE.md | default>) — recommend
   splitting/extracting before or alongside this feature's changes.` This is non-blocking
   (recording, not resolving, gates approval) and only ever produced for a file
   `research-consolidator` actually reported on — never a proactive whole-repo sweep.

   Record `design_findings` in the `Research Basis` section of `design.md` (see
   `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`) so a later reader can see the design is grounded, not
   guessed. Pass the caller's brief (including its `Relevant entries` section, which the
   orchestrator fetches with `surface relevant memory: true` before routing into this skill —
   see `spec-driven-development/SKILL.md`'s Goal-Aware Memory section) to `research-consolidator`
   so it can skip re-deriving context nelly already gave.

   After `research-consolidator` returns:
   - Use `design_findings` to draft design.md
   - Carry every `Prerequisite Work` item into `design.md`'s `Prerequisite Fixes & Refactors`
     section, and design the feature against the code *as it will be after* those items land —
     not as you hoped it already was. If a `fix` item changes what the feature can assume (e.g.
     the function it calls turns out to swallow errors), say so in the affected design section.
     An `unverified` item either gets verified (a quick targeted read or asking the user) or goes
     into `Risks And Tradeoffs` as a named risk. This is what keeps the design grounded: bugs and
     awkward code found now become sequenced prep work, instead of surprises a TDD slice has to
     absorb.
   - Also cache the `Prerequisite Work` list in `research/cache.md` so task slicing sees it.
   - Cache `task_findings` in `research/cache.md` (for agent-tdd to reuse)
   - Persist `file_summaries` to agent-nelly's `file summaries` field (see its
     `agents/agent-nelly.md`'s "File & Folder Summary Cache" section). Read
     `references/nelly-persistence.md` when persisting: it holds the full rules for `file summaries`,
     `folder summaries` and `research digest` items (skip confirmed cache hits, 240-character
     truncation, 30-path digest split).
   - If a summary describes a design approach already tried and rejected (not just current
     codebase shape), persist via `error lesson` instead (see `INTEROP.md`'s "→ agent-nelly"
     section for criterion)

3. **Independent verification** — once `design.md` has a draft (even a rough one) with a
   `Research Basis` section, invoke the `plan-reviewer` skill (ships with this plugin at
   `skills/plan-reviewer/`) against it before the Design Gate is checked. This replaces any ad
   hoc use of the harness's built-in `Plan` subagent, which is open-scoped and reported to take
   10+ minutes (unverified here) for a single design check — `plan-reviewer`'s tiered, claim-scoped subagents
   (`plan-reviewer-tier1/2/3`, also in this plugin's `agents/`) verify only the design's own
   factual claims and stay fast in the common case.
   - Extract the design's falsifiable claims yourself (per `plan-reviewer/SKILL.md`'s Step 0) —
     don't skip straight to spawning Tier 1 with the whole document.
   - Fold `plan-reviewer`'s Blockers into the design before the gate check; fold Resolved
     concerns into `Research Basis` as confirming evidence; surface any Genuinely unresolved item
     to the user rather than silently proceeding.
   - Skip this step only when the design is a trivial, low-risk change the user has explicitly
     asked to fast-track — note the skip in `design.md` rather than doing it silently.

## Design Gate

Move forward only when all of the following are true:
- requirement coverage is explicit
- architecture or code touchpoints are named, grounded in `research-consolidator`'s design_findings
- interfaces or contracts that change are described
- edge-case handling is documented
- validation strategy is credible
- key tradeoffs are visible
- no unresolved contradiction remains
- **[Phase 2+3]** research cache created (research/cache.md with design_findings + task_findings)
- `Prerequisite Fixes & Refactors` lists every `Prerequisite Work` item `research-consolidator`
  returned (or states "none found" because its audit found none), each saying which part of the
  design depends on it — and no design section still assumes the pre-fix behavior
- **[Phase 2+3]** a `Refactor & Reduction Opportunities` bullet exists for every touchpoint file
  `research-consolidator` reported at or over the resolved line-count ceiling — non-blocking
  (recording the recommendation gates approval; resolving it doesn't)
- `plan-reviewer` has been run against this design (or its skip was explicitly noted, per
  Research First step 3) — no unresolved Blocker or Genuinely-unresolved finding remains
- **[Phase 2+3]** file summaries extracted and ready for agent-nelly persistence
- when `agent-nelly:agent-nelly` is available, its Intent-alignment check for this
  design is clean, or its flag has been surfaced to and resolved with the user
- no unresolved Security Finding remains unconfirmed by the user

If any of the above are weak or missing: stop, return a partial design draft, list the open
questions or contradictions, ask the next smallest clarifying question.

**`Track: Fast`**: the Design Gate above is unchanged. Read `../spec-driven-development/references/fast-track.md`
when `Track: Fast` is set (the Phase Decision wording "Ready to move to Tasks" and the escape hatch differ).

## Diagrams (`show_widget`)

Read `references/diagrams.md` when a design's architecture, data flow, or state transition is clearer as a picture
than as prose; render it with `mcp__visualize__show_widget` (not by default, not for every design).

## Design Validation: Deep Review (Before Implementation Handoff)

After the Design Gate passes, invoke `/code-reviewer` at **Deep** review level against the design
content to validate design coherence and slice feasibility before the Implementation handoff.
Read `references/deep-review.md` when running this Deep Review (Design Validation) pass: it holds the plan-mode scoping rule,
the `/code-reviewer` invocation (mode, scope, `review_level: Deep`) and the six focus areas.

**Gate logic:**
   - **Critical findings**: Block advancement to Implementation. Surface issues to user, suggest design rework.
   - **Non-critical findings** (warnings, improvement suggestions): Document as follow-up notes,
     allow advancement to Implementation.
   - **No findings**: Proceed to Implementation.

**Findings:** fold any Deep review findings worth preserving into the design content itself (or the plan file while plan mode is
active) before the Design Spec is constructed, so they travel with `design_md`; there is no separate handoff channel for them.

## Required Output

- a concise design summary
- the `Research Basis` (wide-pass candidates, deep-pass findings, memory brief used,
  research cache path: `research/cache.md`)
- scope mapping back to approved requirements
- architecture or code touchpoints
- data contracts and interfaces
- states, flows, and edge-case handling
- validation strategy
- risks and tradeoffs
- the `Improvement Opportunities & Blast Radius` section (`Blast Radius`, `Security Findings
  (blocking)`, `Refactor & Reduction Opportunities (non-blocking)`, `Best-Practice Notes
  (non-blocking)`)
- the explicit `Phase Completion` checklist status
- open questions
- phase status: `blocked` or `approved`
- **[Phase 2+3]** `research/cache.md` created with design_findings + task_findings + file_summaries
- **[Phase 2+3]** file_summaries ready for agent-nelly persistence (type: "file-summary")

When writing or updating `design.md` (whether that means the plan file, per "Plan-Mode Drafting"
above, or the file itself once approved), use the canonical template from
`${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`.

## Guardrails

- Do not invent new product requirements in design.
- Do not move unresolved requirement ambiguity into design as if it were settled.
- Do not hide risky migrations or weak testability.
- Use `research-consolidator` for research — it produces both design_findings and task_findings
  in one pass; a second, separate deep-read of the same files re-introduces the redundant
  research this consolidation eliminates.
- Do not name a touchpoint or interface that `research-consolidator`'s design_findings didn't
  actually surface or that wasn't otherwise verified — a design grounded in a guess is exactly
  the failure mode this research step exists to prevent.
- Never fold a security-relevant finding into the general (non-blocking) subsections silently —
  it always routes to `Security Findings` and triggers the Design Gate pause.
- Prefer the smallest coherent design that supports the current requirement slice.
- Do not render a diagram for a design simple enough to state in a sentence or two — `show_widget`
  is for when a picture removes real ambiguity, not decoration.
- `/code-reviewer`'s Design Validation Deep Review pass never checks line counts at any level —
  the line-count-ceiling gate belongs entirely to this skill's Design Gate, not to code-reviewer.
