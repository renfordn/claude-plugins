---
name: spec-driven-development
description: Orchestrates the spec-driven workflow (EARS requirements, design, tasks) with hard phase gates, a breadcrumb UI, and goal-aware memory.
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
task slicing, the Red-Green-Refactor loop, or the implementation code-review gate itself (only `design-author`'s one Deep design review is requested from this side). See `INTEROP.md` at
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
call `mark_chapter` directly, then render the breadcrumb below. See
`references/ux-conventions.md` (plugin root) for chapter and breadcrumb rules.

**Status responses that are not a phase transition**: render the progress line **inline** —
no chapter mark. Format:

```
**SDD** Requirements [✓] → Design [▶] → Tasks [·] → Implementation [·]
```

Use `workflow-state.md` to determine each phase's status marker: `✓` approved/complete,
`▶` in progress, `✗` blocked, `·` pending. Emit the line before the rest of the response.

Render/refresh the phase `TaskCreate` checklist in the same response: self-load the three
tools via `ToolSearch` (`select:TaskCreate,TaskUpdate,TaskList`) once per session if not already
loaded, call `TaskList` to check for existing items before creating, then `TaskCreate`/
`TaskUpdate` per `references/ux-conventions.md`'s Phase tick list rules.

## Goal-Aware Memory

Before starting or continuing meaningful phase work, when agent-nelly is available (per the
Availability Check defined in `workflow-manager/SKILL.md`), delegate to
`agent-nelly:agent-nelly` for a holistic brief (Intent, Relevant entries, Intent alignment,
Written) instead of reading `${CLAUDE_PLUGIN_DATA}/sdd-memory/` files directly. If it flags an
Intent-alignment concern, surface it to the user before proceeding — don't silently continue
past a stated drift. Reuse an already-fetched brief or subagent finding within the same
continuous stretch of phase work rather than re-fetching. See `references/goal-aware-memory.md`
for the full reuse/re-fetch trigger rules, brief-caching mechanics, and the memory write-back
contract at phase boundaries.

## Start Protocol

0. **Review follow-ups.** If SessionStart listed open ones and the request is vague or overlaps an item's files, see
   step 0 in the start-protocol reference.
1. Use `workflow-manager` to identify or derive the feature title and slug, and to scaffold or
   locate the per-feature artifact structure (including `intent/` directory).
2. If `agent-nelly:agent-nelly` is available, call it to read the project's stored
   Intent and seed the feature's `Goal` field in `workflow-state.md` from it when Intent is more
   specific than "not yet captured". Otherwise ask the user for the Goal directly.
3. Before step 5 read `references/start-protocol.md` (steps 3, 4, 6: `intent/intent.md` + anchor, `Intent Hash`, `Track`
   classification) and follow its step 3 (create `intent/intent.md`).
4. Record `Intent Hash` and `Intent Alignment Status: unreviewed` in `workflow-state.md` (start-protocol reference, step 4).
5. Initialize `workflow-state.md` with `Current Phase: Requirements` and `recap.md` to match.
6. **Fast Track classification** (small, well-defined change? set `Track: Fast` or `Standard`): start-protocol reference, step 6.
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
    transfers to `agent-tdd`.) If `workflow-state.md` has a `Follow-up: <id>`, mark it `done` with
    the same `followups.py set` command once the implementation is reported complete.

## Continue Protocol

On continue/resume: FIRST run the Rollback Request Check (`rollback_pending` in `workflow-state.json`; if set, surface it and stop), THEN read `references/continue-protocol.md` before acting.

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
1. A hard gate blocks you (Requirements ambiguous, Design contradicts requirements) → surface the blocker and pause for user input
2. The user explicitly asks you to stop or wait for confirmation
3. The next phase requires the user's explicit permission (`EnterPlanMode` gate, implementation approval)

If none of these apply, **do not end your turn.**

### Recovery from Stalls
If you realize mid-turn that you provided guidance and ended without invoking the next skill, **do not rely on the user to notice and run /isdd-continue**. Recognize the stall immediately and invoke the next phase skill retroactively in your very next message — the session may have ended, but the workflow state already reflects phase completion, so continuing via `/isdd-continue` will resume correctly.

## Internal Routing Rule

Read `references/routing-and-task-tracker.md` (Internal Routing Rule) when deciding whether to name `workflow-manager`, `requirements-agent` or
`design-author` to the user: use focused skills internally, never ask the user to switch prompts.

## Subagent Delegation

Three capabilities are delegated to subagents: `spec-reviewer` (assess an existing draft), **[Phase 2+3]**
`research-consolidator` (unified research during Design), and the external `agent-nelly:agent-nelly` (goal-aware
brief). Read `references/subagent-delegation.md` when delegating to any of them, for the roles and delegation rules.

Subagents cannot talk to the user. **You** own every user-facing confirmation checkpoint: take a subagent's
returned report, surface it, get confirmation, then update `workflow-state.md` and `recap.md` yourself.

## Implementation Handoff (Phase 2+3 revised)

Read `references/implementation-handoff.md` when starting the Implementation handoff: one one-directional handoff to
`agent-tdd` (`Track: Standard` sends a Design Spec; `Track: Fast` a Slice Spec with `Review handoff mode: skip`);
spec construction, fallbacks and write-back are in that reference.

**Second trigger: `Current Phase: Tasks` on continue.** A rollback-landing state; treat it
identically to the Design-approved trigger above (rebuild the Design Spec or Slice Spec from the
still-approved `requirements.md`/`design.md`, re-spawn `agent-tdd:agent-TDD`). The full rule lives
in `workflow-manager/SKILL.md`'s `continue` Action Rule.

## Code-Reviewer Checkpoint Tracking (High-Risk Slices)

After agent-tdd spawns and begins Red-Green-Refactor, it marks each slice with a Risk Tier
(`standard` or `high-risk`). On each `agent-tdd` `SubagentStop`, the `high_risk_reviewer` hook
tracks high-risk phases (and standard phases touching a high-risk file path) and surfaces a
passive reminder — no automatic invocation or auto-resume. See
`references/code-reviewer-checkpoint.md` for the full contract, the tracking config shape, the
historical correction this supersedes, and the inventory of helpers that only tests use.

## Requirements Gate

Read `references/requirements-gate.md` when judging whether Requirements may advance (the Requirements Gate:
EARS format, no unresolved ambiguity) or when the user hands over an existing ticket/PRD/spec. Never treat incoming
material as automatically sufficient for phase advancement.

## Existing Ticket Or PRD Handling

See the Requirements Gate section above.

## Phase Gating

Phase gating, auto-advance rules, pause conditions, and state repair are governed entirely by
`workflow-manager` — see its `SKILL.md`.

## Native Plan Mode

`workflow-manager` owns entering (`EnterPlanMode` at `before-design`) and exiting (`ExitPlanMode` at handoff) native plan mode; it is a
user-facing approval checkpoint, in addition to the Requirements and Design gates. Read
`../workflow-manager/references/native-plan-mode.md` before either call.

## Task Tracker Sync

Read `references/routing-and-task-tracker.md` (Task Tracker Sync) when calling `TaskCreate`/`TaskUpdate`/`TaskList` at a phase transition
(see also "Visible Progress" above).

## Artifact Convention

Read `../workflow-manager/references/scaffolding.md` when scaffolding or writing per-feature artifacts (layout is `workflow-manager`'s);
templates are in `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`.

## Writing Style

Read `references/writing-style.md` (Writing Style) when writing `requirements.md`, `design.md`, `recap.md` or `tasks.md`.
