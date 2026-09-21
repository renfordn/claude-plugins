---
name: spec-driven-development
description: Orchestrates the intent spec-driven workflow — EARS requirements through design and tasks — with hard phase gates, a visible breadcrumb/checklist UI, and goal-aware memory. Hands off to separate implementation/review/memory plugins.
---

# Spec Driven Development

## Purpose

Use this skill when the user wants one workflow that can:
- generate or review specs
- enforce a spec-driven process with hard phase gates
- research the codebase and produce a testable design
- hand off to implementation (research validation, task slicing, Red-Green-Refactor)
- keep visible progress (breadcrumb + checklist) and goal-aware memory throughout

This is the only user-facing entrypoint for the workflow unless the user explicitly asks for a
focused skill by name. It routes work across the companion skills internally:
- `workflow-manager`
- `requirements-agent`
- `design-author`
- **[Phase 2+3]** `research-consolidator` (unified research, replaces separate planning-agent calls)

It owns Requirements and Design only. Task slicing and implementation are owned by agent-tdd
(`agent-tdd`), invoked once via a one-directional Design Spec handoff — this skill never drives
task slicing, the Red-Green-Refactor loop, or the code-review gate itself. See `INTEROP.md` at
the repo root for the full handoff contract.

The user should not need to manually prompt each phase skill in order to move through the
workflow.

## Entry Commands

Support these natural-language intents through this single skill: start the workflow, continue
it, resume this feature's workflow, advance to the next phase, continue from the current phase.
Interpret the request and continue automatically — never ask the user to name another skill
first.

## Workflow Contract

Phase-driven, always in this order: `Requirements` → `Design` → `Tasks` → `Implementation`.
`Recap` is maintained throughout as ongoing memory and handoff context. `workflow-state.md` is
the source of truth for current phase and continuation state. `Implementation` here means "the
handoff to `agent-tdd` has been made" (a Design Spec, or — for `Track: Fast` — a Slice Spec; see
`references/fast-track.md`) — this skill's own responsibility ends there.

Do not skip forward across phases unless the current phase is complete and not blocked.

## Review Level Guidance per Phase

Each ISDD phase uses specific `/code-reviewer` review levels to validate artifacts at appropriate
depth, tailored to each phase's concerns. See `references/review-levels.md` for the full
per-phase table, review-level definitions, and how findings feed back into each phase.

## Fast Track

`Track: Fast | Standard` is set once at Start for a small, well-defined change and changes how
`requirements-agent` enters and how the Implementation Handoff is shaped (Slice Spec instead of
Design Spec, no `tasks.md`). See `references/fast-track.md` for the full contract, including the
escape hatch back to `Track: Standard`.

## Visible Progress (every phase-transition or status response)

Two distinct rendering paths — use the right one based on whether a phase transition is occurring:

**Phase transitions** (Requirements → Design → Tasks → Implementation, or a restart/rewind):
delegate to `agent-ux:ux-agent` (via the `Agent` tool) with a `phase_transition` event envelope
(`caller: agent-isdd`, `event_type: phase_transition`, `phase_state`) so it can mark a session
chapter and update the spec-canvas Artifact. See `INTEROP.md`'s "→ agent-ux (UX rendering)"
section for the envelope contract and the unavailability fallback. Never drive `Artifact`/
`mark_chapter` directly from this skill — those are `agent-ux:ux-agent`'s job.

**Status responses that are not a phase transition** (formerly `breadcrumb_only` delegations):
render a progress line **inline** — no `Agent` tool call. A one-line string does not warrant a
full subagent spawn. Format:

```
**SDD** Requirements [✓] → Design [▶] → Tasks [·] → Implementation [·]
```

Use `workflow-state.md` to determine each phase's status marker: `✓` approved/complete,
`▶` in progress, `✗` blocked, `·` pending. Emit the line before the rest of the response.

The phase `TaskCreate` checklist is different: ux-agent cannot reach `TaskCreate`/`TaskUpdate`/
`TaskList` from its subagent context (see `agent-ux:ux-agent`). Render/refresh the checklist
**directly from this skill instead**, in the same response: self-load the three
tools via `ToolSearch` (`select:TaskCreate,TaskUpdate,TaskList`) once per session if not already
loaded, call `TaskList` to check for existing items before creating, then `TaskCreate`/
`TaskUpdate` per `agent-ux`'s `references/ux-conventions.md`'s Phase tick list conventions (the
convention itself, driven by the calling skill and not `agent-ux:ux-agent`, is unchanged by the
extraction — only where it's documented moved).

## Goal-Aware Memory

Before starting or continuing meaningful phase work, when agent-nelly is available (per the
Availability Check defined in `workflow-manager/SKILL.md`), delegate to
`agent-nelly:agent-nelly` for a holistic brief (Intent, Relevant entries, Intent alignment,
Written) instead of reading `~/.claude/sdd-memory/` files directly. If it flags an
Intent-alignment concern, surface it to the user before proceeding — don't silently continue
past a stated drift. Reuse an already-fetched brief or subagent finding within the same
continuous stretch of phase work rather than re-fetching. See `references/goal-aware-memory.md`
for the full reuse/re-fetch trigger rules, brief-caching mechanics, and the memory write-back
contract at phase boundaries.

## Start Protocol

1. Use `workflow-manager` to identify or derive the feature title and slug, and to scaffold or
   locate the per-feature artifact structure (including `intent/` directory).
2. If `agent-nelly:agent-nelly` is available, call it to read the project's stored
   Intent and seed the feature's `Goal` field in `workflow-state.md` from it when Intent is more
   specific than "not yet captured". Otherwise ask the user for the Goal directly.
3. **[NEW Phase 1.1]** Create `intent/intent.md` with:
   - Project Intent (from agent-nelly brief, or "not yet captured")
   - Feature Goal (seeded from step 2)
   - Success Signals (brief, 2-3 observable outcomes)
   - Anti-Patterns (failure indicators)
   - Intent Anchor: compute SHA256 hash of intent.md content
4. Update `workflow-state.md` with:
   - `Intent Hash: <anchor>`
   - `Intent Alignment Status: unreviewed`
5. Initialize `workflow-state.md` with `Current Phase: Requirements` and `recap.md` to match.
6. **Fast Track classification** (see `references/fast-track.md` for the full contract): judge
   whether this request is a small, well-defined change — a single behavior change, no new
   external interface, no data migration, no cross-plugin `INTEROP.md` contract change, testable
   in one sentence. This is a judgment call, never a keyword regex. Skip this judgment and honor
   the user's own words directly if they explicitly asked for the full workflow or explicitly
   asked to fast-track. Set `Track: Fast` or `Track: Standard` in `workflow-state.md`
   accordingly. When `Track: Fast`, tell the user in one line: "Fast-tracking this as a small
   change — say 'full workflow' if you'd rather go through the full Requirements interview and
   task slicing."
7. Route into `requirements-agent`: it interviews from scratch when the input is vague, or
   reviews-and-rewrites when the user hands over an existing ticket/PRD/draft, or — when
   `Track: Fast` — drafts and self-approves a minimal requirement directly (its own Fast Track
   entry mode; see `requirements-agent/SKILL.md`) — three entry modes, same gate.
8. **After Requirements are approved, immediately invoke `design-author` in this turn** (see
   "Turn Management: Continuation Guarantee" below for the critical constraint). Do not end your
   turn after approving requirements — advance to Design without stopping.
9. **After Design is approved, immediately prepare and invoke `agent-tdd` for Implementation
   handoff in this turn** (same constraint applies). Do not end your turn after approving design
   — proceed to handoff without stopping.
10. After Implementation handoff, stop with a clear handoff message. (Implementation ownership
    transfers to `agent-tdd`.)

## Continue Protocol

0. **Rollback Request Check:**
   - The `before_continue` hook automatically checks for pending rollbacks from prior agent-tdd runs.
   - If agent-tdd found a slicing blocker (task conflicts, design contradiction, research gap), the rollback will be surfaced with reasoning and recommended target phase.
   - Address the issue and rewind using `/isdd-rewind <target>`, then return to continue the workflow.

1. Use `workflow-manager` to find the relevant feature folder and resolve state (see its
   Decision Order — `agent-nelly:agent-nelly`'s stored Intent first (when available),
   then `workflow-state.md`, then `workflow-state.json`, then open blockers, then phase files,
   then `recap.md`).
2. **[Phase 1.2]** Check cached nelly brief in `workflow-state.json` → `nelly_brief_cache`:
   - If valid (Intent Hash match + timestamp fresh): reuse cached brief
   - If invalid: fetch fresh brief via agent-nelly, update cache
3. Continue from the earliest blocked or incomplete phase; auto-advance through later phases
   whose entry gates are satisfied.
4. Pause only when a gate fails, a confirmation checkpoint is required, or implementation was
   not requested.

Do not restart from Requirements if a later phase is already the active incomplete phase,
unless requirement changes invalidate the design or tasks.

## Turn Management: Continuation Guarantee

**Critical constraint to prevent mid-workflow stalls:**

After advancing to a new phase (Requirements → Design → Tasks → Implementation), the orchestrator **must stay in this turn** to invoke the next phase skill. Providing guidance, decisions, or explanations at a phase boundary is not a stopping point — it is a prerequisite to invoking the next skill.

### When to NOT End Your Turn
- **After Requirements approval**: You have approved requirements. Do NOT stop here. Immediately invoke `design-author` in this turn.
- **After Design approval**: You have approved design. Do NOT stop here. Immediately invoke `agent-tdd` for implementation handoff in this turn.
- **After delegating to a subagent**: You invoked `design-author`, `research-consolidator`, or another subagent. Do NOT end your turn and wait passively. When the subagent's work is complete, immediately integrate its results and continue to the next phase in this turn.

### Guidance is a Step, Not a Stop
Providing guidance ("These are the tradeoffs," "Consider this approach," "Next we'll...") or decisions ("Proceed with Category 1") is an intermediate step within a turn, not a turn-ending checkpoint. **Always follow guidance with the next actionable step** — invoke the next skill or confirm a decision — in the same turn. If you cannot proceed in this turn, explicitly tell the user why and ask for permission to pause.

### Exception: Explicit Pause Conditions
Stop your turn **only** when:
1. A hard gate blocks you (Requirements ambiguous, Design contradicts requirements, Tasks validation fails) → surface the blocker and pause for user input
2. The user explicitly asks you to stop or wait for confirmation
3. The next phase requires the user's explicit permission (`EnterPlanMode` gate, implementation approval)

If none of these apply, **do not end your turn.**

### Recovery from Stalls
If you realize mid-turn that you provided guidance and ended without invoking the next skill, **do not rely on the user to notice and run /sdd-continue**. Recognize the stall immediately and invoke the next phase skill retroactively in your very next message — the session may have ended, but the workflow state already reflects phase completion, so continuing via `/sdd-continue` will resume correctly.

## Internal Routing Rule

Use focused skills internally rather than asking the user to switch prompts:
- `workflow-manager` — orchestration, phase detection, state repair, transitions, scaffolding.
- `requirements-agent` — requirements from scratch or from an existing draft/ticket/PRD.
- `design-author` — design, informed by `research-consolidator` and `agent-nelly:nelly-
  orchestrator` (when available).

Only expose these skill names when the user explicitly asks which one is being used, wants to
invoke one directly, or a pause message needs to explain which capability produced the output.

## Subagent Delegation

Four capabilities ship as **subagents** (`agents/`) so their bounded work runs in an isolated
context and returns only a conclusion, keeping this orchestrator thread lean across a long
workflow:

- `spec-reviewer` — delegate when `requirements-agent` needs to assess an existing draft before
  rewriting it.
- **[Phase 2+3]** `research-consolidator` — delegate during Design to produce unified research
  (design_findings, task_findings, file_summaries) in one pass, eliminating redundant research
  between design-author and agent-tdd. Replaces the prior separate planning-agent calls.
- `agent-nelly:agent-nelly` — an external peer-plugin subagent, not one of this plugin's
  own `agents/`, invoked the same way (via the `Agent` tool with that literal `subagent_type`
  string), gated by the Availability Check — delegate before any phase starts, when available,
  for a goal-aware brief (Intent, Relevant entries, Intent alignment, Written); it is
  the sole writer into agent-nelly's own memory store, which agent-isdd never reads or writes
  directly. **[Phase 2+3]** Also used to query and cache file summaries for cross-feature reuse.
- `agent-ux:ux-agent` — an external peer-plugin subagent, delegate at every **phase transition**
  for chapter markers and the spec-canvas Artifact, via the UX Event Envelope (`caller:
  agent-isdd`, `event_type: phase_transition`, `phase_state`, `delta`, `artifact_path` — see
  `INTEROP.md`'s "→ agent-ux (UX rendering)" section). Status breadcrumbs between transitions
  are rendered inline (see "Visible Progress" above). It does not own the `TaskCreate` checklist
  — see "Task Tracker Sync" below.

Delegation rules:
- Prefer the subagent over inlining these when the task is well-scoped.
- Subagents cannot talk to the user. **You** own every user-facing confirmation checkpoint:
  take a subagent's returned report, surface it, get confirmation, then update
  `workflow-state.md` and `recap.md` yourself — per `workflow-manager`'s field-update contract
  (see its Lifecycle Hooks section), not a separate set of rules.
- `requirements-agent` and `design-author` stay inline for interviewing the user, but delegate
  their bounded sub-tasks (`spec-reviewer` for draft assessment; `research-consolidator` for
  research) to subagents rather than doing that work in the main thread.

## Implementation Handoff (Phase 2+3 revised)

Once Design is approved and implementation is requested, this skill's job is to hand off to
`agent-tdd` for implementation — a single, one-directional handoff, not an orchestrated
multi-stage loop. `Track: Standard` sends a **Design Spec**; `Track: Fast` sends a single
**Slice Spec** instead, with `Review handoff mode: skip`. Both are one-directional handoffs with
no orchestrated multi-stage loop; only the spec shape and `agent-tdd` mode differ. See
`references/implementation-handoff.md` for the full contract: Design Spec construction (file
list extraction, the `agent-nelly` subtract-then-query step, the recap summarization rule),
Slice Spec construction, the availability check before spawning, the harness-`Agent`-spawn-bug
fallback, the test-author pause/resume steps, and the Handoff Facts write-back.

## Code-Reviewer Checkpoint Tracking (High-Risk Slices)

After agent-tdd spawns and begins Red-Green-Refactor, it marks each slice with a Risk Tier
(`standard` or `high-risk`). On each `agent-tdd` `SubagentStop`, the `high_risk_reviewer` hook
tracks high-risk phases (and standard phases touching a high-risk file path) and surfaces a
passive reminder — no automatic invocation or auto-resume. See
`references/code-reviewer-checkpoint.md` for the full contract, the tracking config shape, and
`INTEROP.md`'s "Auto Code-Reviewer Invocation" section for the historical correction this
supersedes.

## Requirements Gate

Ready to advance only when: all required fields are present, expressed in EARS format, and no
unresolved ambiguity remains. Minimum content: problem statement, user outcome, constraints,
non-goals, edge cases, success criteria, dependencies.

If any of the above are weak, vague, or missing: refuse to advance, interview the user to fill
the weakest areas first, prioritizing the most ambiguous or highest-risk gaps. If ambiguity
remains after interviewing: stop, return the partial draft, return an explicit gaps list.

## Existing Ticket Or PRD Handling

When the user provides a ticket, PRD, or existing spec, `requirements-agent`'s review mode
handles it: review first, rewrite only the weak sections into EARS format, present the changed
draft, pause for confirmation, and only then treat it as the canonical requirements artifact.
Never treat incoming material as automatically sufficient for phase advancement.

## Phase Gating

Phase gating, auto-advance rules, pause conditions, and state repair are governed entirely by
`workflow-manager` — see its `SKILL.md`.

## Native Plan Mode

`workflow-manager` owns entering native plan mode (`EnterPlanMode`) at `before-design` and
exiting it (`ExitPlanMode`) at `after-tasks` once the `Tasks` checklist passes — see its "Native
Plan Mode Gate" section for the full contract. This stays here in the orchestrator rather than
delegated to `agent-ux:ux-agent` because it is a user-facing approval checkpoint (`agent-ux:ux-agent`
never talks to the user).
Requesting approval this way is in addition to the phase gates above, not instead of them —
`ExitPlanMode` is only ever called once the Tasks checklist has already passed.

## Task Tracker Sync

`tasks.md` is a repo-persisted planning artifact, distinct from the harness's own task tracker.
Call `TaskCreate`/`TaskUpdate`/`TaskList` directly from this skill at every phase transition
(self-loaded via `ToolSearch` first) — see "Visible Progress" above.

## Artifact Convention

Per-feature artifacts are plugin-generated state, not source — they live under the project's
central SDD memory directory (`~/.claude/sdd-memory/<project-slug>/`), not the repo:

```text
<sdd-memory-dir>/
  spec/
    <YYYY-MM-DD-feature-slug>/
      workflow-state.md
      workflow-state.json
      requirements/requirements.md
      design/design.md
      tasks/tasks.md
      recap/recap.md
```

`workflow-manager` owns scaffolding this structure and keeping it stable across phases. Use the
canonical templates in `references/artifact-templates.md`; keep the same section order unless
the user explicitly asks to change it.

## Writing Style

Structured sections with checklists, concise prose plus bullet lists, for `requirements.md`,
`design.md`, and `recap.md`. For `tasks.md`, optimize for agent handoff: minimal narration,
explicit ordered execution steps, concrete validation steps. When slicing tasks, populate each
task's `Depends On` field with the real bare `task-id`s of other tasks in the same `tasks.md` it
requires first (`[]` when none) — never leave it as unexamined boilerplate, and never fold a
genuinely narrative dependency into it (that stays in `Prerequisites`).
