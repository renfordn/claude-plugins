---
name: design-spec
description: Orchestrates the Design Spec handoff from agent-isdd — validates research, generates TDD-sized tasks with Ralph Loops, then hands to Red-Green-Refactor.
---

# Design Spec Orchestrator

## Purpose

This skill receives a **Design Spec** from agent-isdd (at the Design → Implementation boundary) and orchestrates the transformation from approved design to implementation-ready tasks.md. It owns three phases before Red-Green-Refactor:

1. **Research Validation** — ensure research completeness, escalate if gaps or contradictions
2. **Task Slicing** — generate phased, TDD-sized, dependency-ordered tasks
3. **Ralph Loops** — autonomous validation of slice safety (size, dependencies, traceability)

After Ralph Loops pass, the workflow proceeds to Red-Green-Refactor (existing `agent-TDD` behavior). This skill never drives implementation itself.

## Contract & Input

**Design Spec** includes:
- `requirements_md` — full approved requirements.md
- `design_md` — full approved design.md with Research Basis section
- `research_cache` — cached research findings (design_findings, task_findings, file_summaries)
- `recap_md` — summary of requirements, design, risks, Goal alignment notes

See `references/design-spec.schema.json` for strict JSON schema.

## Entry Points

Support these intents:
- **"Implement this design"** — user requesting implementation after Design approved
- **Programmatic:** Caller passes Design Spec JSON + explicit "proceed to implementation" signal

## Availability Check

Before proceeding, check if agent-tdd is available in this session. Scan the `<system-reminder>` block for `agent-tdd:agent-TDD` or `agent-tdd:research-validator`. If absent, pause with actionable message: "agent-tdd is not installed — install it before requesting implementation."

## Workflow (Token-Efficient Design)

**North Star:** Reduce token usage 30-60% vs. per-agent orchestration. Key strategies: one-pass parsing, early escalation on gaps, cached outputs on resume, hard iteration limits.

```
Design Spec Received
    ↓
Step 1: Parse Design Spec Once → cache (2-3K tokens, reuse on resume)
  Extract: touchpoints, behaviors, risks, file_summaries
  Store: workflow-state.json → design_spec_cache
    ↓
Step 2: Research Validation → fast gap detection (3-5K tokens, early bailout)
  If gaps > 1 or contradictions: ESCALATE immediately (skip Steps 3-6)
  Else: PASS → continue
    ↓
Step 3: Task Slicing (5-8K tokens, reuse cached inputs)
  Generate tasks.md using cached touchpoints + behaviors
  Store: workflow-state.json → task_slicer_output
    ↓
Step 4: Ralph Loops (4-6K per iteration, max 3 iterations/loop)
  Loop 1: Slice Size (≤3 files, testable, ≤2 deps)
  Loop 2: Dependency Correctness (acyclic)
  Loop 3: Research Traceability (grounded)
  If max iterations: ESCALATE immediately (don't retry)
  Store: workflow-state.json → ralph_loops_results
    ↓
Step 5: Risk Assignment (2-3K tokens, deterministic)
  Assign Risk Tier per phase (cached design_risks, no re-read)
    ↓
Step 6: Readiness Check (2-3K tokens, checklist only)
  10-item deterministic checklist (no prose)
  ├─ ✓ ready → proceed to Red-Green-Refactor
  └─ ✗ paused → ESCALATE (failed items only)
    ↓
Step 7: Red-Green-Refactor (existing agent-TDD)
  For each slice in dependency order:
    if risk_tier == high-risk: spawn test-author first
    spawn agent-TDD (implements)

**Token Budget:** 18-28K initial, 10-15K on resume (cache reuse)
**Savings:** 8-26K per feature vs. old approach
```

See `ORCHESTRATION.md` for detailed token-efficiency analysis, caching strategy, and resume flow.

## Escalation Paths

When escalating back to agent-isdd, pause with a specific reason marker:

```html
<!--AGENT-TDD-RESEARCH-VALIDATION-FAILED:reason="File src/models/User.ts not in cache; needs deep-read on model constraints"-->
<!--AGENT-TDD-DESIGN-CONTRADICTION:reason="Design assumes UserService is singleton; research found it's instantiated per request"-->
<!--AGENT-TDD-SLICING-REQUIRES-DECISION:reason="High-risk database migration cannot be split further without losing safety; confirm acceptable risk"-->
<!--AGENT-TDD-PLAN-VALIDITY-FLAGGED:reason="Ralph Loops iteration limit exceeded on Dependency Correctness; likely circular dependency in design"-->
```

Agent-isdd's `before-continue` hook will detect these markers and pause, asking the user to fix the issue (re-research gaps, clarify design, make a product decision, etc.), then resume this workflow.

## Visible Progress

Emit a progress line before each major phase:

```
**Agent-TDD** Research Validation [▶] → Task Slicing [·] → Ralph Loops [·] → Implementation [·]
```

Update markers: `✓` complete, `▶` in progress, `✗` blocked, `·` pending.

## Handoff Report Format

After readiness-check, before proceeding to Red-Green-Refactor:

```
**Handoff Report**
- Verdict: ready | paused (with specific reason)
- Research validation: passed | gaps filled | contradiction (see escalation marker above)
- Tasks generated: N phases, M total slices
- Ralph Loops: all passed (3/3 loops, max 2 iterations per loop)
- Risk Tiers: X high-risk, (N-X) standard
- Slicing confidence: high | medium (if research felt incomplete)
- Next: Proceed to Red-Green-Refactor per slice
```

## Handoff to Red-Green-Refactor

Once readiness-check passes:

1. For each slice in tasks.md (in order of Depends On):
   - If `Risk Tier: high-risk`:
     - Spawn `agent-tdd:test-author` to write Red test only
     - Confirm Red test fails for intended reason
   - Spawn `agent-tdd:agent-TDD` to implement that slice (Red-Green-Refactor)

2. After all slices implement:
   - Return final handoff to caller

## State Management

This skill does not own persistent state beyond the session. It reads Design Spec, produces tasks.md, then hands off. Any escalations back to agent-isdd include enough context for agent-isdd to resume.

## Guardrails

- **Do not** re-research entire codebase (use only research_cache unless gaps escalated)
- **Do not** skip Ralph Loops (they catch slice safety errors early)
- **Do not** proceed past readiness-check if blockers remain
- **Do not** assume design.md touchpoints are in order (validate via research_cache)
- **Do not** merge slices without verifying dependency impact

## Dependencies

- **Input:** Design Spec from agent-isdd (requires agent-isdd 0.1.14+)
- **Optional re-research:** research-consolidator (called by research-validator on gaps)
- **Output:** tasks.md + Red-Green-Refactor handoff
- **Optional review:** code-reviewer (user-selected, between Green and Refactor)
