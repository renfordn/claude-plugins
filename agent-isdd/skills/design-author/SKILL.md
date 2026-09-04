---
name: design-author
description: "[Internal — use /isdd instead] Turns approved requirements into a testable design.md, grounded in agent-nelly's brief (if available) and research-consolidator's unified codebase research (Phase 2+3)."
---

# Design Author

## Use This Skill When

After Requirements are approved and before detailed task planning starts. Typical inputs:
approved `requirements.md`, a reviewed PRD/ticket that already passed the requirements gate, or
migration notes needing implementation-facing design.

## Research First (Phase 2+3 revised)

Before drafting, delegate to subagents rather than relying only on what's already in context:

1. `agent-nelly:nelly-orchestrator` — reuse the brief the caller passed down; call agent-nelly
   directly only per the re-fetch triggers defined in `spec-driven-development`'s Goal-Aware
   Memory section, when agent-nelly is available (per the Availability Check defined in
   `workflow-manager/SKILL.md`). When a fresh call is made, it returns a holistic brief (Intent,
   prior decisions, open risks, relevant past entries, Intent-alignment check). Seed
   `research-consolidator` with it (whether reused or freshly fetched) so it isn't re-deriving
   project context the memory already has.

2. **[Phase 2+3]** `research-consolidator` — unified codebase research (single pass) that produces
   **dual output:**
   - `design_findings` — architecture touchpoints, interfaces, design risks (for design.md)
   - `task_findings` — file boundaries, test surfaces, slicing constraints (cached for agent-tdd)
   - `file_summaries` — per-file summaries for agent-nelly cache (cross-feature reuse)

   Reuse a still-valid `research-consolidator` finding already fetched earlier in this same
   continuous stretch of phase work (per `spec-driven-development`'s extended brief-reuse
   convention and its three re-fetch triggers) instead of re-delegating for the same touchpoints.
   
   Record `design_findings` in the `Research Basis` section of `design.md` (see
   `references/artifact-templates.md`) so a later reader can see the design is grounded, not
   guessed. Pass the caller's brief (including its `Relevant entries` section, which the
   orchestrator fetches with `surface relevant memory: true` before routing into this skill —
   see `spec-driven-development/SKILL.md`'s Goal-Aware Memory section) to `research-consolidator`
   so it can skip re-deriving context nelly already gave.

   After `research-consolidator` returns:
   - Use `design_findings` to draft design.md
   - Cache `task_findings` in `research/cache.md` (for agent-tdd to reuse)
   - Persist `file_summaries` to agent-nelly via `new facts` batch (type: "file_summary")
     - `file_summaries` are structured for cross-feature reuse: path, summary, exports,
       constraints, tech_debt, dependencies, test_surface, migration_risks, git_hash
     - Agent-nelly caches these in `~/.claude/agent-nelly-memory/<project>/files/`
   - If a summary describes a design approach already tried and rejected (not just current
     codebase shape), persist via `error lesson` instead (see `INTEROP.md`'s "→ agent-nelly"
     section for criterion)

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
- **[Phase 2+3]** file summaries extracted and ready for agent-nelly persistence
- when `agent-nelly:nelly-orchestrator` is available, its Intent-alignment check for this
  design is clean, or its flag has been surfaced to and resolved with the user
- no unresolved Security Finding remains unconfirmed by the user

If any of the above are weak or missing: stop, return a partial design draft, list the open
questions or contradictions, ask the next smallest clarifying question.

## Diagrams (`show_widget`)

When architecture, a data flow, or a state transition is genuinely clearer as a picture than as
prose or a table — not by default, and not for every design — render it with
`mcp__visualize__show_widget` (call `mcp__visualize__read_me` once first, silently, per its own
instructions). This is a lighter-weight, one-shot visual for explaining the design as you write
it; it is not the spec canvas (that's `agent-ux:ux-agent`'s redeployable Artifact over confirmed
requirements sections, a different artifact for a different phase). Reference the diagram from
`design.md` in prose (what it shows and why) rather than treating the widget itself as the
durable record — `design.md` stays the artifact of record.

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
- **[Phase 2+3]** file_summaries ready for agent-nelly persistence (type: "file_summary")

When writing or updating `design.md`, use the canonical template from
`references/artifact-templates.md`.

## Guardrails

- Do not invent new product requirements in design.
- Do not move unresolved requirement ambiguity into design as if it were settled.
- Do not hide risky migrations or weak testability.
- **[Phase 2+3]** Do not call `planning-agent` separately — use `research-consolidator` only.
  It wraps planning-agent and produces both design_findings and task_findings in one pass.
  Calling planning-agent separately re-introduces the redundant research this consolidation
  eliminates.
- Do not name a touchpoint or interface that `research-consolidator`'s design_findings didn't
  actually surface or that wasn't otherwise verified — a design grounded in a guess is exactly
  the failure mode this research step exists to prevent.
- Never fold a security-relevant finding into the general (non-blocking) subsections silently —
  it always routes to `Security Findings` and triggers the Design Gate pause.
- Prefer the smallest coherent design that supports the current requirement slice.
- Do not render a diagram for a design simple enough to state in a sentence or two — `show_widget`
  is for when a picture removes real ambiguity, not decoration.
