# Design Spec Mode (full contract)

Moved out of `INTEROP.md` to keep it under its line cap; `INTEROP.md`'s "Design Spec Mode" section is the index.

## One implementation of this mode (the modular alternative was retired)

**Retired 2026-09-16.** A second, modular implementation (`skills/design-spec/SKILL.md`, five
separate subagents) emitted its own incompatible marker vocabulary that `agent-isdd` never
recognized and no caller used, so it was removed rather than kept as a dead alternative.

`agent-TDD` itself performs Research Validation, Task Slicing, all three Ralph Loops, Risk Tier
Assignment and the Readiness Check (see `agents/agent-TDD.md`'s "Design Spec workflow"): one
spawn with a Design Spec does the whole pipeline through implementation. `agent-isdd`'s
`spec-driven-development` skill spawns `agent-tdd:agent-TDD` directly, and this is the only
source of the `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` and `<!--AGENT-TDD-PHASE:...-->` markers.

## Design Spec Input Format

Pass a **Design Spec** inline in the spawn prompt (exact field names required):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requirements_md | string | yes | Full approved requirements.md with user stories and acceptance criteria |
| design_md | string | yes | Full approved design.md with file touchpoints, interfaces, research basis section |
| research_cache | object | yes | Research findings: design_findings, task_findings, file_summaries (keyed by path), git_hashes |
| recap_md | string | yes | Summary, known risks, blockers, Goal alignment notes (summarized, not full history) |
| Parallel | on \| off | no | Default off (serial). On: slice into waves and stop at `slicing_complete`; see Parallel slice delivery |
| nelly_brief_cache | object | no | Pre-fetched cached context from agent-nelly (if available) |

## Research Validation Phase

Agent-tdd validates:
- Are design.md's file touchpoints present in research_cache?
- Are interfaces and constraints documented?
- Any obvious gaps (a file touched but not researched)?

**Decision:**
- ✓ **Research thorough** → proceed to Task Slicing.
- ✗ **Research thin** → escalate with specific files/areas needing targeted research.
- ✗ **Design contradicts research** → escalate with the specific contradiction.

Agent-tdd does **not** attempt re-research itself — it identifies gaps precisely and escalates to
the caller (agent-isdd owns the research-consolidation loop for targeted re-research).

## Task Slicing & Ralph Loops

Agent-tdd produces **tasks.md** (see `references/tasks-schema.json`) with:
- Phased, TDD-sized slices (one behavior per slice, ≤ 3 files per slice ideally).
- Risk Tiers (standard or high-risk).
- Depends On graph (topological order, acyclic).
- Test Intent + Validation Target per slice.
- Ordered Steps (concrete, grounded in research).

Agent-tdd validates via three Ralph Loops (at most 3 re-slicing rounds in total, per `agents/agent-TDD.md`):
1. **Slice Size Validation** — all slices ≤ 3 files, testable.
2. **Dependency Correctness** — acyclic, no hidden dependencies.
3. **Research-to-Implementation Traceability** — steps match cache, constraints respected.

## Readiness Check & Escalation

Before proceeding to per-slice implementation, `agent-TDD` itself emits a **Readiness Check**
verdict as part of its own instructions (see `agents/agent-TDD.md`'s "Design Spec workflow" step 5 (Readiness)
— corrected 2026-09-16; this used to name a separate `readiness-check` agent, a leftover
reference to the retired modular pipeline described above):
- ✓ **Ready For Implementation** — tasks.md is final. If no slice is `high-risk`, proceed
  directly to Red-Green-Refactor per slice. If one or more slices are `high-risk`, stop instead
  and hand back the report — see "Test-Author Gate" below; this is a distinct reason to return,
  not the `Paused` verdict below (nothing about the plan is wrong).
- ✗ **Paused** — escalate with specific reason (research gap, design contradiction, slicing
  blocker, etc.). Caller (agent-isdd) pauses; user re-enters and addresses the reason.

**Marker Emission:** When verdict = `paused`, `agent-TDD` emits:
```
<!--AGENT-TDD-PLAN-FLAG:reason="<specific blocker reason>"-->
```
The caller's SubagentStop hook (e.g., `agent-isdd`'s `subagent_report.py`) captures this marker and translates it into its own escalation mechanism (e.g., `<!--SDD-ROLLBACK-REQUEST:...-->`), triggering the appropriate rewind phase.

**Escalation paths:**
- Research gap: "File `src/api.ts` not in cache; needs interface review."
- Design contradiction: "Design assumes `User.role` but schema has `User.permissions`."
- Slicing blocked: "Tasks 3 and 4 cannot be split without breaking acyclic dependency."
- High-risk unsplittable: "Slice is 5 files + high-risk; confirm acceptable or refactor design."

For comprehensive escalation documentation including Mid-Slice Research Request, Plan Validity Flag, and
detailed resume mechanisms, see [`references/escalation-paths.md`](references/escalation-paths.md).

## Test-Author Gate (added 2026-09-16)

Every slice's Risk Tier is already known by Readiness Check (step 4, Risk tiers, in `agents/agent-TDD.md`'s
"Design Spec workflow", runs before this) — so a high-risk slice's need for `test-author` is never actually discovered
mid-pipeline, it's known upfront. When Readiness Check passes with one or more `high-risk`
slices in `tasks.md`, `agent-TDD` stops at the `slicing_complete` handoff (see *Design Spec
Handoff Report* below — its **High-Risk Slices** field names them) instead of proceeding to
implementation, and awaits resume — the exact same "stop, hand back a report, await
caller-driven resume via `SendMessage`" shape as *The mandatory review pause* above, not a new
mechanism. The caller spawns `test-author` once per named slice, bundles the results, and
resumes the same `agent-TDD` instance with them. Zero high-risk slices: no pause, proceed
straight through exactly as before this gate existed.

This replaces an earlier, abandoned approach (a caller-side marker,
`AGENT-TDD-TEST-AUTHOR-NEEDED`, briefly added and then removed the same day, once it became
clear no marker was needed — the existing `slicing_complete` marker plus `tasks.md` already on
disk are sufficient for the caller to detect the condition without `agent-TDD` needing to say
anything new).

## Test-Budget Pre-flight (caller-side, long-running projects)

`agent-TDD` runs the whole Design Spec without returning, so the per-slice checkpoint that Slice
Spec Mode gets from `slice-spec` doesn't exist here. The caller instead runs the
[`test-budget`](skills/test-budget/SKILL.md) skill once, before implementation starts, on each
existing test file the work will grow: the files named in `tasks.md`'s Validation Targets when a
`slicing_complete` pause happens (the Test-Author Gate above), otherwise the test files the
design names, before the first spawn. A `consolidate first` or `promote to e2e` verdict is
resolved by the caller with the user's OK, outside `agent-TDD`'s Red/Green/Refactor; an e2e
promotion is passed in as that slice's Test Intent. Skip it for new test files and when the
project's suite is small.

## Per-Slice Implementation (after Readiness and the Test-Author Gate)

Once Readiness Check passes and (if applicable) the Test-Author Gate above has been satisfied,
agent-tdd iterates through tasks.md:
- For each slice: Plan → Red → Green → (mandatory review pause) → Refactor → Validate.
- High-risk slices: use the test supplied via the Test-Author Gate above as Red.
- Standard slices: agent-tdd writes Red itself.
- **No return to caller** until all slices complete (except escalations). The Test-Author Gate
  above is not an exception to this — it happens *before* per-slice implementation begins, not
  during it.

## Design Spec Handoff Report

**After Research Validation + Task Slicing (before per-slice implementation):**

Emit phase marker: `<!--AGENT-TDD-PHASE:slicing_complete-->`

Provide:
- Research Validation summary (findings, gaps if any).
- Task Slicing summary (count, distribution).
- Ralph Loops status (all passed / which loop, iteration N of max).
- Risk Tier distribution (high-risk count vs. standard).
- **High-Risk Slices** — the exact slice names/ids that are `high-risk`, or "none". What the
  Test-Author Gate above actually acts on; the distribution count alone isn't enough.
- Readiness Verdict (ready for implementation / paused with reason).
- tasks.md file path.
- Handoff Facts (constraints, test surfaces, migration risks, etc.).

**Per-slice reports (during implementation):**

Standard Slice Spec mode reports (green_pause / refactor_complete).

**Final report (all slices complete):**

Emit phase marker: `<!--AGENT-TDD-PHASE:all_slices_complete-->`

Provide:
- Slicing Summary (total slices, distribution, risk tiers).
- Implementation Summary (files changed, test coverage, refactors).
- Validation Summary (test suites run, coverage metrics, unvalidated areas).
- Risks and Follow-ups (tech debt, testing gaps).
- Handoff Facts (final discoveries worth persisting).

## One-Directional Handoff

This is a **one-directional handoff** — agent-isdd does not resume or monitor agent-tdd past the
initial spawn, with two scoped exceptions: (a) the Test-Author Gate above, which agent-isdd's
`spec-driven-development` skill does resume for, and (b) Model Escalation, where `agent-TDD`
emits `<!--AGENT-TDD-MODEL-ESCALATE:reason=...; from_model=...; to_model=...-->` (see
`agents/agent-TDD.md`) and agent-isdd's `hooks/subagent_report.py` handles it — see
[`references/escalation-paths.md`](references/escalation-paths.md) "Model Insufficiency (Model
Escalation)". Task slicing happens inside
agent-tdd (not handed back to agent-isdd). Escalations back to agent-isdd (research gap, design
contradiction, slicing blocker) pause with explicit reason; agent-isdd's
`before-continue` hook (run on `/isdd-continue`) surfaces pending rollbacks/model escalations when
the user re-enters after addressing the escalation.

## Direct Mode (harness `Agent`-spawn failure fallback, added 2026-09-16)

Everything above this section assumes the caller can actually spawn `agent-TDD` via the `Agent`
tool. When that assumption fails — the `Agent` tool call itself is rejected at the harness level
(a `PreToolUse` schema-validation error on the call, not an error from the spawned agent),
recurring rather than a one-off flake (the caller must check this) — spawning is not available at all, and no
retry, prompt change, or call-site change fixes it. See `agent-isdd/INTEROP.md`'s "Fallback —
Direct Implementation" section for the exact three-condition Detection check.

[`skills/design-spec-direct/SKILL.md`](skills/design-spec-direct/SKILL.md) reproduces this mode's
Research Validation → Task Slicing → Ralph Loops → Risk Tier Assignment (`plan` sub-mode,
unchanged from the pipeline above, just returning to the caller instead of continuing into
implementation) plus **Slice Spec Mode's** existing per-slice contract (`test-author`, `slice`,
`refactor` sub-modes) invoked once per slice via the `Skill` tool instead of `Agent`. It
deliberately does *not* reproduce this section's "No return to caller until all slices complete"
property — a `Skill` call has no subagent isolation to make that property meaningful, so the
caller checkpoints every slice instead (Red/Green → review → decide → refactor or pause).

This is a fallback path, invoked only when the Detection conditions in `agent-isdd/INTEROP.md`
are confirmed, not a second supported way to run Design Spec Mode day-to-day. See that skill
file for the full mode contract, the caller-owned loop it expects, and what isolation guarantees
are genuinely lost (not just relocated) versus a real `agent-TDD`/`test-author` spawn.
