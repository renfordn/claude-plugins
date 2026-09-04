# Artifact Templates

Use these templates as the default structure for per-feature artifacts. These are plugin-
generated state, not source — they live under the project's central SDD memory directory
(`~/.claude/sdd-memory/<project-slug>/`, resolved via `hooks/sdd_memory.py`), never inside the
repo itself.

For a filled example, see `references/example-feature/`.

Feature root:

```text
<sdd-memory-dir>/spec/<YYYY-MM-DD-feature-slug>/
```

## `intent/intent.md`

```md
# Intent: <feature title>

## Project Intent

<From `agent-nelly:nelly-orchestrator` stored Intent, or "not yet captured">

## Feature Goal

<One line: derived from project Intent, describes what this feature achieves for the user>

## Success Signals

- <Observable signal 1: how you'll know this succeeded>
- <Observable signal 2: measurable outcome>

## Anti-Patterns

- <What would indicate failure or misalignment>

## Intent Anchor

- ID: <SHA256 hash of this file's content — used for drift detection>
- Generated: <YYYY-MM-DDTHH:MM:SSZ>

```

Used by `workflow-manager` at start to seed feature `Goal` field and track alignment throughout Requirements → Design → Implementation. All downstream specs reference this anchor; Intent drift is detected by hash mismatch.

## `workflow-state.md`

```md
# Workflow State: <feature title>

## Feature

- Title: <feature title>
- Slug: <YYYY-MM-DD-feature-slug>
- Goal: <one line — the user's actual objective for this feature, seeded from `agent-nelly:nelly-orchestrator`'s stored Intent at start if available, otherwise from the user; not the same as the problem statement>
- Intent Hash: <anchor ID from intent.md, used for drift detection>
- Intent Alignment Status: <aligned | drift | unreviewed>

## Current State

- Current Phase: <Requirements | Design | Implementation | Complete>
- Previous Phase: <None | Requirements | Design | Implementation>
- Workflow Status: <In Progress | Blocked | Awaiting Confirmation | Awaiting Implementation Request | Complete>
- Pause Reason: <None | blocker | confirmation required | waiting for implementation request>
- Next Action: <next concrete workflow step>

## Hook Status

- Last Hook Run: <before-continue | before-requirements | after-requirements | before-design | after-design | after-tasks | None>
- Last Hook Outcome: <Passed | Paused | Repaired State | Handed Off | Completed | None>
- Last Hook Decision: <continue | pause | handoff | complete | None>
- Hook Notes: <short reason or summary>

## Ownership

- Current Owner: <User | Spec Driven Development>
- Implementation Requested: <Yes | No>

## Last Updated

- Date: <YYYY-MM-DD>
```

## Workflow Manager Interpretation Notes

Use `workflow-state.md` as a compact machine-readable summary for the workflow.

- `Current Phase` is the primary continuation pointer, and is what the top-level breadcrumb (rendered by `agent-ux:ux-agent`, see `INTEROP.md`'s "→ agent-ux (UX rendering)" section) reads directly — no separate progress field exists or should be invented.
- `Goal` is seeded once via `agent-nelly:nelly-orchestrator` (if available) when the feature starts and rarely rewritten; `agent-nelly:nelly-orchestrator` uses it for the goal-alignment check in every brief it returns.
- `Workflow Status` determines whether the next action is to continue, pause, hand off, or complete.
- `Pause Reason` must align with any unresolved blocker or confirmation checkpoint in the phase artifacts.
- `Next Action` should describe the smallest next workflow step, not a broad goal.
- `Last Hook Run` and `Last Hook Outcome` show which lifecycle checkpoint most recently controlled progression.
- `Last Hook Decision` should align with the current workflow status and next action.

## `requirements/requirements.md`

```md
# Requirements: <feature title>

## Status

- Phase: Requirements
- State: Draft | Blocked | Approved
- Last Updated: <YYYY-MM-DD>

## Source Inputs

- Origin: <idea | ticket | PRD | bug report | migration | pasted code>
- References:
  - <link or identifier>

## Problem Statement

<Concise prose describing the current problem.>

## User Outcome

- <Outcome 1>
- <Outcome 2>

## Constraints

- [ ] <Constraint 1>
- [ ] <Constraint 2>

## Non-Goals

- [ ] <Non-goal 1>
- [ ] <Non-goal 2>

## Dependencies

- [ ] <Dependency 1>
- [ ] <Dependency 2>

## Edge Cases

- [ ] <Edge case 1>
- [ ] <Edge case 2>

## Success Criteria

- [ ] <Observable success criterion 1>
- [ ] <Observable success criterion 2>

## Non-Functional Constraints

- Throughput: <concrete value/range, or `N/A: <one-line reason>`>
- Data Volume: <concrete value/range, or `N/A: <one-line reason>`>
- Concurrency: <concrete value/range, or `N/A: <one-line reason>`>
- Latency Budget: <concrete value/range, or `N/A: <one-line reason>`>

## EARS Requirements

- `Ubiquitous`: When <trigger>, the <system> shall <response>.
- `Event-driven`: When <event>, the <system> shall <response>.
- `State-driven`: While <state>, the <system> shall <response>.
- `Optional-feature`: Where <feature is present>, the <system> shall <response>.
- `Unwanted-behavior`: If <undesired condition>, then the <system> shall <response>.

## Open Gaps

- [ ] <Missing detail or ambiguity>

## Approval Checkpoint

- [ ] Problem statement is clear
- [ ] User outcome is clear
- [ ] Constraints are clear
- [ ] Non-goals are clear
- [ ] Dependencies are clear
- [ ] Edge cases are clear
- [ ] Success criteria are clear
- [ ] Non-Functional Constraints are populated (value or explicit N/A)
- [ ] EARS requirements are present
- [ ] No unresolved ambiguity remains

## Phase Completion

- [ ] All required requirement sections are populated
- [ ] Open Gaps contains no blocking unresolved item
- [ ] State can be marked `Approved`
```

Each `Approval Checkpoint` / `Phase Completion` line above is also the exact
item set the calling skill mirrors into the harness's `TaskCreate` checklist
on entry to this phase — the markdown checklist is the single source of
truth; the task list is only a rendering of it. This is driven directly by
the calling skill (not `agent-ux:ux-agent` — see `INTEROP.md`'s "→ agent-ux (UX rendering)"
section).

## `design/design.md`

```md
# Design: <feature title>

## Status

- Phase: Design
- State: Draft | Blocked | Approved
- Last Updated: <YYYY-MM-DD>

## Design Summary

<Short prose summary of the selected design.>

## Research Basis

- Wide-pass candidates: <files/modules `planning-agent` flagged as touched-area candidates>
- Deep-pass findings: <load-bearing files `planning-agent` actually read, and what each one constrains>
- Memory brief used: <one-line reference to the `agent-nelly:nelly-orchestrator` brief this design was seeded with, if available>

## Scope Mapping To Requirements

- Requirement: <requirement or criterion>
  - Design Response: <how the design satisfies it>

## Architecture Or Code Touchpoints

- <Module or boundary 1>: <change summary>
- <Module or boundary 2>: <change summary>

## Data Contracts And Interfaces

- Interface: <name>
  - Inputs: <...>
  - Outputs: <...>
  - Invariants: <...>

## States, Flows, And Edge-Case Handling

- Primary flow:
  - <step>
- Edge case:
  - <handling>

## Validation Strategy

- Unit:
  - <target>
- Integration:
  - <target>
- Manual:
  - <target>

## Risks And Tradeoffs

- Risk: <risk>
  - Mitigation: <mitigation>

## Improvement Opportunities & Blast Radius

### Blast Radius

<Prose: touched area(s), who/what is affected, ripple effects of this design.>

### Security Findings (blocking)

- [ ] Finding: <text> / Pause Reason: <text> / Resolution: <pending | resolved and how>

### Refactor & Reduction Opportunities (non-blocking)

- [ ] <opportunity>

### Best-Practice Notes (non-blocking)

- [ ] <note>

## Open Questions

- [ ] <question>

## Phase Decision

- [ ] Design supports current requirements
- [ ] Design is testable
- [ ] Design avoids unresolved contradictions
- [ ] No unresolved Security Finding remains
- [ ] Ready to move to Tasks

## Phase Completion

- [ ] Requirement coverage is explicit
- [ ] Architecture or code touchpoints are named
- [ ] Interfaces or contracts are described
- [ ] Validation strategy is credible
- [ ] State can be marked `Approved`
```

## `tasks/tasks.md`

```md
# Tasks: <feature title>

## Phase Status

- Current Phase: Tasks
- State: Draft | Blocked | Ready For Implementation | In Progress | Complete
- Last Updated: <YYYY-MM-DD>

## Execution Rules

- Preserve approved requirements and design intent.
- Keep slices to one behavior change and/or one file or module touched if possible.
- Tests first where implementation follows.
- Refactor only after green.
- Pause on ambiguity, conflicting constraints, weak testability, high-risk migration, or oversized tasks.
- Tag each task's Risk Tier (`standard` or `high-risk`) per design.md's Risks And Tradeoffs section.

## Phase 1: <phase name>

### Objective

<Single behavior-focused objective.>

### Risk Tier

- `standard` | `high-risk` — set `high-risk` only when design.md's Risks And Tradeoffs section
  names a risk touching this task's files/module, or this task is itself a high-risk migration.
  Default `standard`. Drives whether `spec-driven-development`'s Implementation Handoff spawns
  `agent-tdd:test-author` before `agent-tdd:agent-TDD` (see `INTEROP.md` at the repo root).

### Prerequisites

- <dependency or prior decision>

### Depends On

- <task-id, ...> — bare task ids only, no embedded prose; empty list `[]` when this task has no
  task-level dependency. References other task ids in this same `tasks.md`. A genuinely
  narrative dependency (a product/architecture decision, not another task) stays in
  `Prerequisites` instead — the two fields are not merged.

### Ordered Steps

1. <smallest safe task>
2. <next task>
3. <validation step>

### Test Intent

- Add or update:
  - <test target>
- Expected failing behavior:
  - <red condition>

### Validation Target

- Command:
  - `<exact command if known>`
- Evidence:
  - <expected pass condition>

### Unlocks

- Enables:
  - <next phase or task>

### Blockers Or Escalation

- [ ] <blocker or confirmation point>

## Phase 2: <phase name>

Repeat the same structure for each phase.

## Task Readiness Checklist

- [ ] At least one concrete implementation phase exists
- [ ] Each phase has explicit objective, Risk Tier, steps, test intent, and validation target
- [ ] Slices are safe for TDD
- [ ] No unresolved blocker requires confirmation before implementation
- [ ] State can be marked `Ready For Implementation`
```

## `recap/recap.md`

```md
# Recap: <feature title>

## Recap

<Short rolling summary of where the feature stands.>

## Current Phase

- <Requirements | Design | Implementation>

## Workflow Status

- Auto-Advance: <Yes | No>
- Pause Reason: <None | blocker | confirmation required | waiting for implementation request>

## Completed Phases

- [ ] Requirements
- [ ] Design
- [ ] Implementation (includes task slicing + Red-Green-Refactor, owned by agent-tdd)

## Open Items

- [ ] Question: <text>
- [ ] Debt: <text>
- [ ] Risk: <text>
- [ ] Security: <text>
- [ ] Improvement: <text>

## Decisions Made

- <decision>

## Assumptions

- <assumption>

## Goal Alignment Notes

- <any `agent-nelly:nelly-orchestrator` goal-alignment flag raised during this feature, and how it was resolved>
- **[Phase 1.1]** Intent drift detected: <hash comparison: old hash vs. new hash; why it changed; how it was addressed>
- Alignment Status: aligned | drift | unreviewed

## Next Task

- <next concrete action>

## What Completed Work Enabled

- <completed task or phase>: <what it unlocked>
```
