---
name: spec-driven-development
description: Orchestrates the spec-driven workflow (EARS requirements, design, tasks) with hard phase gates, a breadcrumb UI, and goal-aware memory.
---

# Spec Driven Development

Single user-facing entrypoint; routes to `workflow-manager`, `requirements-agent`, `design-author` and `research-consolidator` internally. It owns Requirements and Design only; task slicing and implementation belong to `agent-tdd` via the Design Spec handoff (see `INTEROP.md`).

## Input

A feature request, an existing ticket/PRD/draft, or continue/resume/advance of the current feature. Proceed on natural-language intents; never ask the user to name another skill.

## Output

`requirements.md`, `design.md`, `recap.md` and `workflow-state.md` (source of truth for phase and continuation), then an `agent-tdd` handoff. Status responses start with one inline line: `**SDD** Requirements [✓] → Design [▶] → Tasks [·] → Implementation [·]`; at each phase transition call `mark_chapter`, then render the breadcrumb; keep the phase checklist current (`TaskList` before `TaskCreate`, refreshed on each status change). Detail: `references/ux-conventions.md` (plugin root).

## Done when

The handoff to `agent-tdd` is made, `workflow-state.md` and `recap.md` match. Complete is set only after every high-risk slice is reviewed (R3, enforced by `complete_guard`).

## Workflow Contract

`Requirements` → `Design` → `Tasks` → `Implementation`; never skip a phase that is incomplete or blocked. `Implementation` means the handoff was made (Design Spec, or a Slice Spec for `Track: Fast`, see `references/fast-track.md`).

- **Approval is `ExitPlanMode` only.** Requirements auto-advance once they pass the gate; ask with `AskUserQuestion` only for real gaps (Open Gaps, hash re-approval, review fallback, mode choice). The approval hash is frozen at the first agent-TDD spawn; the spec gates deny a missing or mismatched hash.
- **Risk-scaled depth.** `Risk: low | elevated | high` with `Risk Reason`; depth and review scale with it. Fast only at `low`, Standard never becomes Fast, risk only rises. Signals and depth table: `references/risk-depth.md`; `state_guard` enforces it.
- **Phase review levels** are in `references/review-levels.md` (Review Level Guidance per phase: Standard, Deep, Ultra).
- **Fast Track** (`Track: Fast | Standard`, set once at Start): Slice Spec instead of Design Spec, no `tasks.md`; see `references/fast-track.md`.
- **User-led mode.** When `Implementation Mode` is `user`, point the user to the `isdd-coach` skill; `user_led_guard` blocks non-test edits. Change the mode only on the user's say-so.

## Goal-Aware Memory

Before meaningful phase work, when agent-nelly is available (Availability Check in `workflow-manager/SKILL.md`), delegate to `agent-nelly:agent-nelly` for a brief instead of reading `${CLAUDE_PLUGIN_DATA}/sdd-memory/` directly. Surface Intent-alignment concerns first. Reuse/re-fetch rules and write-back: `references/goal-aware-memory.md`.

## Start Protocol

0. **Review follow-ups.** If SessionStart listed open ones and the request is vague or overlaps an item's files, see step 0 in the start-protocol reference.
1. Use `workflow-manager` to derive the title and slug and to scaffold or locate the feature structure (including `intent/`).
2. If `agent-nelly:agent-nelly` is available, seed `Goal` from its stored Intent when more specific than "not yet captured"; otherwise ask the user.
3. Before step 5 read `references/start-protocol.md` (steps 3, 4, 6: `intent/intent.md` + anchor, `Intent Hash`, `Track` classification) and follow its step 3 (create `intent/intent.md`).
4. Record `Intent Hash` and `Intent Alignment Status: unreviewed` (start-protocol reference, step 4).
5. Initialize `workflow-state.md` with `Current Phase: Requirements` and `recap.md` to match.
6. **Fast Track classification** and `Risk` (small, well-defined change? `Track: Fast` needs `Risk: low` written with or before it): start-protocol reference, step 6; classify `Risk` per `references/risk-depth.md`.
7. Route into `requirements-agent` (interview, rewrite, or Fast Track).
8. When Requirements pass the gate, invoke `design-author` in this turn.
9. When Design is approved via `ExitPlanMode`, prepare and invoke `agent-tdd` in this turn (`Parallel: on` for 4+ slices; on `slicing_complete` with waves run `agent-tdd:tdd-parallel`; details in `references/implementation-handoff.md`).
10. After handoff, stop with a clear handoff message. If `workflow-state.md` has `Follow-up: <id>`, mark it `done` with `followups.py set` once implementation is reported complete.

## Continue Protocol

On continue/resume: FIRST run the Rollback Request Check (`rollback_pending` in `workflow-state.json`; if set, surface it and stop), THEN read `references/continue-protocol.md` before acting. The `UserPromptSubmit` hook (`resume_context`) injects what changed since the baseline (branch, head, files).

## Turn Management: Continuation Guarantee

**Critical constraint to prevent mid-workflow stalls:**

After advancing to a new phase, stay in this turn and invoke the next phase skill. Guidance, decisions or explanations at a phase boundary are a prerequisite to invoking the next skill, not a stopping point. The stall Stop hook only backstops one case (Requirements approved, no `design.md`, once per change); it is not a general guarantee.

### When to NOT End Your Turn
- **After Requirements pass the gate**: requirements auto-advance. Immediately invoke `design-author` in this turn.
- **After Design approval**: Immediately invoke `agent-tdd` for implementation handoff in this turn.
- **After delegating to a subagent**: integrate its results and continue to the next phase in this turn; never wait passively.

### Guidance is a Step, Not a Stop
Guidance is an intermediate step. Follow it with the next actionable step in the same turn. If you cannot proceed, say why and ask permission to pause.

### Exception: Explicit Pause Conditions
Stop your turn **only** when:
1. A hard gate blocks you (Open Gaps in Requirements, Design contradicts requirements) → surface the blocker and ask via `AskUserQuestion`
2. The user explicitly asks you to stop or wait
3. The next step needs the user's approval: the `ExitPlanMode` design approval, or an `AskUserQuestion` for a real gap

Otherwise **do not end your turn.** If you ended a turn after guidance without invoking the next skill, invoke it in your very next message; `workflow-state.md` already reflects the phase, so `/isdd-continue` resumes correctly.

## Internal Routing Rule

Read `references/routing-and-task-tracker.md` (Internal Routing Rule) when deciding whether to name `workflow-manager`, `requirements-agent` or `design-author` to the user, and `references/routing-and-task-tracker.md` (Task Tracker Sync: `TaskCreate`/`TaskUpdate`/`TaskList`) at phase transitions: use focused skills internally, never ask the user to switch prompts.

## Subagent Delegation

`spec-reviewer`, `research-consolidator` and `agent-nelly:agent-nelly` are delegated to; read `references/subagent-delegation.md` before delegating. Subagents cannot talk to the user. **You** own every user-facing confirmation: surface the report, get confirmation, then update `workflow-state.md` and `recap.md` yourself.

## Implementation Handoff

Read `references/implementation-handoff.md` when starting the handoff to `agent-tdd`: Standard sends a Design Spec with `Parallel: on` and you lead `agent-tdd:tdd-parallel`; Fast sends one serial Slice Spec (`Review handoff mode: skip`). Ask Implementation Mode first.

**Second trigger: `Current Phase: Tasks` on continue.** A rollback-landing state; treat it like Design-approved: rebuild the spec from the still-approved `requirements.md`/`design.md` and re-spawn `agent-tdd:agent-TDD` (rule in `workflow-manager/SKILL.md`'s `continue` Action Rule).

## Code-Reviewer Checkpoint Tracking

agent-isdd's `SubagentStop` hook on code-reviewer stops (`review_tracking`) is the sole writer of the reviewed map, and a review counts only when the code-reviewer prompt carries `Review scope: slice=N`. `Risk: high` needs every slice reviewed; `complete_guard` blocks Complete otherwise. Fallback: `AskUserQuestion`, recorded as `Accepted via AskUserQuestion: <ids|all>: <reason>`. Contract: `references/code-reviewer-checkpoint.md`.

## Requirements Gate

Read `references/requirements-gate.md` when judging the Requirements Gate (may Requirements advance? EARS format, no unresolved ambiguity) or when the user hands over an existing ticket/PRD/spec; incoming material is never automatically sufficient.

## Phase Gating

Auto-advance, pause conditions and state repair: `workflow-manager`.

## Native Plan Mode

`workflow-manager` owns `EnterPlanMode`/`ExitPlanMode`, a user-facing approval checkpoint: read `../workflow-manager/references/native-plan-mode.md` before either call.

## Artifact Convention

Read `../workflow-manager/references/scaffolding.md` when scaffolding or writing per-feature artifacts; templates are in `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`.

## Writing Style

Read `references/writing-style.md` (Writing Style) when writing `requirements.md`, `design.md`, `recap.md` or `tasks.md`.
