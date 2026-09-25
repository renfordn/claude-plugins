---
name: design-author
description: "[Internal — use /isdd instead] Turns approved requirements into a testable design.md, grounded in agent-nelly's brief (if available) and research-consolidator's unified codebase research (Phase 2+3)."
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

   **[File & Folder Summary Cache]** On that same call (fresh or reused), also pass `file summary
   lookup` for every path the brief's `Relevant entries`/`File relevance:` sub-list already names
   plus any file explicitly named in the approved `requirements.md` — this is a smaller place to
   check than re-deriving those paths' purpose from scratch. For each **cache hit**, verify
   freshness yourself before trusting it: compute the file's current content hash (`Grep`
   `pattern: "^"`, `output_mode: "count"` isn't a hash — use a `Bash` `git hash-object <path>`
   call, the same primitive `research-consolidator` uses for `git_hash`) and compare it to the
   returned `git_hash`; a match is a **confirmed** cache hit, a mismatch is a miss. Pass the list
   of paths with a confirmed hit down to `research-consolidator` as "already summarized, skip
   deep-reading unless something in this feature's scope specifically requires re-reading it" —
   the same skip mechanic it already applies to the brief's `Relevant entries` (see its Pass 1,
   step 1). This is the read side of the cache; the write side is step 2 below.

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
   - Cache `task_findings` in `research/cache.md` (for agent-tdd to reuse)
   - Persist `file_summaries` to agent-nelly's `file summaries` field (see its
     `agents/agent-nelly.md`'s "File & Folder Summary Cache" section) — **not** for a file that
     was a confirmed cache hit and skipped deep-reading in step 1 above (nothing changed about it,
     so there's nothing to re-persist), only for files `research-consolidator` actually deep-read
     this pass. Each item's `summary` is `research-consolidator`'s one-line file summary,
     truncated to 240 characters if needed (`file-summary` entries are capped — see the reference
     above); `exports`/`constraints`/`dependencies`/`tech_debt` and `git_hash` carry straight
     through from `research-consolidator`'s output.
   - Also persist one `folder summaries` item per directory containing two or more of the files
     `research-consolidator` deep-read this pass, when that directory has no existing
     `folder-summary` cache hit from step 1: a short (≤240 char) description of the directory's
     overall role, drawn from those files' summaries — not a mechanical file-by-file listing.
     Skip a directory that already has a confirmed-fresh folder-summary; its purpose hasn't
     changed just because one more file inside it got touched.
   - If a summary describes a design approach already tried and rejected (not just current
     codebase shape), persist via `error lesson` instead (see `INTEROP.md`'s "→ agent-nelly"
     section for criterion)

3. **Independent verification** — once `design.md` has a draft (even a rough one) with a
   `Research Basis` section, invoke the `plan-reviewer` skill (ships with this plugin at
   `skills/plan-reviewer/`) against it before the Design Gate is checked. This replaces any ad
   hoc use of the harness's built-in `Plan` subagent, which is open-scoped and observed to take
   10+ minutes for a single design check — `plan-reviewer`'s tiered, claim-scoped subagents
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

**`Track: Fast`** (see `spec-driven-development/SKILL.md`'s "Fast Track" section): the Design
Gate above is unchanged — still run in full, against a smaller scope. The one difference is the
`design.md` template's Phase Decision item "Ready to move to Tasks": for `Track: Fast` it means
"ready for direct Slice Spec handoff to `agent-tdd`" instead, since no `tasks.md` is ever
produced on this track. **Escape hatch**: if satisfying the Design Gate turns out to need real
architecture/interface decisions this scope assumed away, say so and report it back to
`spec-driven-development` instead of forcing a thin design through — same escalation path
`requirements-agent`'s Fast Track mode uses.

## Diagrams (`show_widget`)

When architecture, a data flow, or a state transition is genuinely clearer as a picture than as
prose or a table — not by default, and not for every design — render it with
`mcp__visualize__show_widget` (call `mcp__visualize__read_me` once first, silently, per its own
instructions). This is a lighter-weight, one-shot visual for explaining the design as you write
it; it is not the spec canvas (that's `agent-ux:ux-agent`'s redeployable Artifact over confirmed
requirements sections, a different artifact for a different phase). Reference the diagram from
`design.md` in prose (what it shows and why) rather than treating the widget itself as the
durable record — `design.md` stays the artifact of record.

## Design Validation: Deep Review (Before Tasks Advancement)

After the Design Gate passes, invoke `/code-reviewer` at **Deep** review level against the design
content to validate design coherence and slice feasibility before advancing to the Tasks phase.
**Corrected 2026-09-24 [plan/design gap]**: the Design Gate passing does not by itself mean
`design.md`/`research/cache.md` are on disk — per "Plan-Mode Drafting" above, that only happens
once the user approves the plan, which can be after this step (Design Gate approval and the
implementation request that triggers `ExitPlanMode` are separate events — see `workflow-manager`'s
"Native Plan Mode Gate"). So while plan mode is still active, point `/code-reviewer` at the
in-context draft / plan file content directly rather than at `design.md`/`research/cache.md`
file paths; only use the file-path scope once those files have actually been persisted (plan mode
was skipped or has already exited).

**Step: Design Coherence Validation**

1. Invoke `/code-reviewer` skill with:
   - **Mode**: `direct-review` (or `review-improve` if piping findings into user review)
   - **Scope**: the design content and research basis — as `design.md` + `research/cache.md` file
     paths once persisted, or as inline content from the plan file / context while plan mode is
     still active and those files don't yet exist on disk
   - **`review_level`**: `Deep` (design pattern validation, coherence checks)

2. Focus areas for Deep review in design context:
   - Design pattern alignment (is the implementation matching the stated patterns?)
   - Single Responsibility Principle (SRP) validation (do modules/classes have focused scope?)
   - File touchpoint correctness (are the right files being touched for the right reasons?)
   - Slice feasibility (can the proposed slices be implemented independently?)
   - Interface consistency (do stated contracts match across touchpoints?)
   - Architecture coherence (do design decisions hang together or conflict?)

3. Gate logic:
   - **Critical findings**: Block advancement to Implementation. Surface issues to user, suggest design rework.
   - **Non-critical findings** (warnings, improvement suggestions): Document as follow-up notes,
     allow advancement to Implementation.
   - **No findings**: Proceed to Implementation.

4. **Corrected 2026-09-24**: there is no separate `task-slicer`/"next phase" handoff on
   `agent-isdd`'s side to attach findings to — per Phase 2+3, task slicing happens entirely
   inside `agent-tdd` during the Design Spec handoff (see `INTEROP.md`'s "→ agent-tdd" section),
   and the Design Spec's fixed fields (`requirements_md`, `design_md`, `research_cache`,
   `recap_md`) carry no dedicated review-findings field. Output: fold any Deep review findings
   worth preserving into the design content itself (e.g. its Design Summary or a Risks/Constraints
   note) before the Design Spec is constructed, so they travel with `design_md` — do not rely on a
   separate handoff channel that no longer exists. **Corrected 2026-09-24 [plan/design gap]**: if
   plan mode is still active, fold findings into the plan file's draft (the same in-context/
   plan-file content this step reviewed), not into `design.md` directly — it isn't writable yet.

**Rationale**: This upfront Deep review catches wrong-shape designs early, before task slicing 
and implementation, reducing rework during Red-Green-Refactor cycles. See 
`code-reviewer/skills/code-reviewer/SKILL.md`'s "Review Levels" section for Deep level definition.

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
