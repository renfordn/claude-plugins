# Escalation Paths: Two-Way Handoff in Design Spec Mode

## Overview

While the Design Spec handoff is described as **one-directional** (agent-isdd doesn't monitor or resume agent-tdd automatically), agent-tdd has **explicit escalation paths** that create a **two-way communication model**. When agent-tdd encounters blockers, it pauses and escalates back to agent-isdd with specific reasons.

Agent-isdd resumes via its `before-continue` hook when the user addresses the escalation.

---

## Escalation Phases

### Phase 1: Research Validation
Agent-tdd validates research completeness. It **escalates and pauses** in these cases:

#### 1.1 Research Too Thin
**Trigger**: Design file-touchpoints not in research cache (e.g., `src/api.ts` mentioned in design but not in research/cache.md)

**Agent-tdd Action**:
- Identify specific files/areas missing
- Pause with reason: "Research gap: File `src/auth/token.ts` not in cache; needs interface review"
- Do NOT attempt to research
- Wait for agent-isdd to resume with targeted research

**Agent-isdd Action**:
- Acknowledge the research gap
- Run targeted research-consolidator for the specific gap
- Update research/cache.md with missing information
- Resume agent-tdd with updated Design Spec
- agent-tdd continues to Task Slicing phase

#### 1.2 Design Contradicts Research
**Trigger**: Design assumes something that contradicts research cache (e.g., design says `User.role` but schema has `User.permissions`)

**Agent-tdd Action**:
- Surface the specific contradiction with evidence
- Pause with reason: "Design contradiction: Design assumes `User.role` field but research shows User type has `permissions` instead"
- This is a design problem, not a research problem
- Wait for agent-isdd to resume

**Agent-isdd Action**:
- Design-author must fix the design.md
- Update design.md to match research findings
- Resume agent-tdd with corrected Design Spec
- agent-tdd re-validates and continues

#### 1.3 Constraint Mismatch
**Trigger**: Design specifies a constraint that research shows isn't feasible

**Example**: Design says "all tokens expire after 24 hours" but research shows "token library only supports 1-hour max"

**Agent-tdd Action**:
- Identify the constraint vs. research mismatch
- Pause with specific reason
- Wait for agent-isdd/designer to decide on constraint change

---

### Phase 2: Task Slicing
Agent-tdd slices tasks and applies Ralph Loops. It **escalates and pauses** in these cases:

#### 2.1 Design Requires Product Decision to Slice
**Trigger**: Multiple valid slicing strategies that conflict with design constraints

**Example**: "Payment integration (Slice 3) and auth refactor (Slice 4) both touch `User.permissions`. Cannot split without breaking dependency constraint. Requires product decision: (a) change design to isolate changes, (b) accept non-minimal slice, (c) reorder requirements."

**Agent-tdd Action**:
- Identify that slicing is blocked by design decisions
- Explain the constraint: "Acyclic dependency requirement cannot be met with current design"
- Present concrete options with tradeoffs
- Pause and escalate to agent-isdd
- Wait for design/product decision

**Agent-isdd Action**:
- Design-author makes decision (e.g., refactor Slice 3 scope)
- Update design.md with decision
- Resume agent-tdd
- agent-tdd resumes slicing with new constraints

#### 2.2 High-Risk Slice Cannot Be Split
**Trigger**: A slice is both high-risk AND oversized (>3 files), and cannot be split without breaking acyclic dependencies

**Example**: "Migration slice is 5 files + high-risk (schema migration). Cannot split further without breaking dependency order. Decision required: (a) accept oversized high-risk slice, (b) change design scope, (c) defer part of migration."

**Agent-tdd Action**:
- Surface the issue: slice count, risk level, why split isn't possible
- Present the blocker clearly
- Escalate to agent-isdd for product/design decision
- Do NOT proceed with oversized high-risk slice

**Agent-isdd Action**:
- Designer/product owner decides on mitigation
- Either: accept risk, shrink scope, or redesign
- Update Design Spec and requirements if needed
- Resume agent-tdd
- agent-tdd continues with updated information

---

### Phase 3: Per-Slice Implementation (Red/Green)
Agent-tdd implements slices one by one. It **escalates and pauses** when it discovers:

#### 3.1 Code Doesn't Match Design Assumptions (Mid-Slice Research Request)
**Trigger**: During Red or Green, actual codebase structure differs from design assumptions

**Example**: Design specifies "auth middleware in `src/auth/middleware.ts`" but actual code shows middleware in `src/middlewares/auth.js` with different interface

**Agent-tdd Action**:
- Stop implementing the slice
- Emit a **Research Gap Flag** in the handoff report
- Clearly describe what was assumed vs. what was found
- Stop at the mandatory review pause (after Green) even if it hasn't been reached
- Include the flag describing the gap

**Example handoff marker**:
```
<!--AGENT-TDD-RESEARCH-GAP:
Expected: auth middleware in `src/auth/middleware.ts` exporting function authMiddleware()
Found: middleware in `src/middlewares/auth.js` exporting class AuthMiddleware
Impact: Slice 3 implementation blocked until gap is clarified
-->
```

**Agent-isdd Action**:
- Receive the Research Gap Flag
- Provide additional context or spawn a research pass
- Clarify the actual code structure
- Resume agent-tdd with clarification
- agent-tdd updates assumptions and continues with implementation

#### 3.2 Acceptance Criteria Conflict (Plan Validity Flag)
**Trigger**: During Red/Green/Review, task itself is wrong (not just assumptions)

**Example**: Acceptance criteria says "users can be logged in multiple devices simultaneously" but acceptance criteria for another slice (out of scope) says "only one device per user"

**Agent-tdd Action**:
- Stop implementation
- Emit a **Plan Validity Flag** in the handoff report
- Surface the specific conflict with evidence
- This means the task needs re-planning, not just more information

**Example handoff marker**:
```
<!--AGENT-TDD-PLAN-FLAG:reason="Slice 3 acceptance criteria conflicts with Slice 1: Slice 1 enforces 'single device per user', Slice 3 requires 'multi-device support'. Task itself needs re-planning"-->
```

**Agent-isdd Action**:
- Receive the Plan Validity Flag
- Default target: Requirements phase (most conservative)
- Re-plan the affected tasks with reconciled requirements
- Optionally: remove the conflicting requirement, adjust both slices
- Return to agent-tdd with updated Design Spec
- agent-tdd re-validates and re-slices if needed

#### 3.3 Test Cannot Pass (Blocker)
**Trigger**: Red test created, but Green implementation cannot satisfy it within slice bounds

**Example**: Slice requires "login in < 500ms" but database queries on large datasets violate constraint

**Agent-tdd Action**:
- Identify the blocker (database schema missing index, constraint unachievable, etc.)
- This is different from a Research Gap (not an assumption) or Plan Validity (task is valid)
- Surface as explicit blocker in handoff
- Pause implementation
- Escalate: "Slice 3 blocker: login performance constraint unachievable with current schema. Requires database optimization (out of slice scope) or constraint negotiation"

**Agent-isdd Action**:
- Acknowledge blocker
- Either: adjust design (relax constraint, add prerequisites), or
- Trigger out-of-band work (database optimization)
- Resume agent-tdd
- agent-tdd continues

---

## Escalation Summary Table

| Phase | Escalation Type | Root Cause | Agent-TDD Action | Agent-ISDD Action | Resume? |
|-------|-----------------|-----------|------------------|-------------------|---------|
| Research Validation | Research Gap | File/interface not in cache | Identify gap, pause | Run targeted research | Yes |
| Research Validation | Design Contradiction | Design assumes non-existent field | Surface contradiction | Design-author fixes design.md | Yes |
| Task Slicing | Product Decision | Slicing blocked by design | Present options, pause | Design/product decides | Yes |
| Task Slicing | Risk/Size Conflict | High-risk AND oversized | Surface issue, pause | Designer decides mitigation | Yes |
| Per-Slice Red/Green | Research Gap | Code structure different from design | Stop, emit flag | Provide clarification | Yes |
| Per-Slice Red/Green | Plan Validity | Task requirements conflict | Stop, emit flag | Replan requirements | Yes |
| Per-Slice Red/Green | Blocker | Cannot satisfy test | Surface blocker, pause | Adjust design or prerequisites | Yes |

---

## Resume Mechanism

### How Agent-ISDD Resumes Agent-TDD

Agent-isdd's `before-continue` hook detects escalations:
1. **Research Gap Flag** — identified by marker in handoff report
2. **Plan Validity Flag** — identified by marker in handoff report
3. **Explicit blocker reason** — identified by blocker description in handoff report

Agent-isdd pauses the workflow and requires user input to address the escalation.

User addresses the issue (additional research, design fix, requirement reconciliation).

Agent-isdd resumes via `SendMessage` to the same agent-tdd instance, passing:
- Updated Design Spec (if design changed)
- Updated requirements (if requirements changed)
- Clarification or context (if information gap)
- Explicit instruction: "Continue with Phase X" or "Re-validate and proceed"

Agent-tdd resumes in its current context with updated information and continues.

---

## Key Properties of Two-Way Escalation

### 1. **Explicit Pause Points**
Agent-tdd never silently works around blockers. It surfaces them explicitly.

### 2. **Specific Escalation Reasons**
Each escalation includes:
- What was expected
- What was found
- Why it matters
- What needs to change

### 3. **Design Authority Preserved**
Agent-tdd never modifies design.md or requirements.md. Only agent-isdd (or the user it surfaces to) can change them.

### 4. **Research Authority Preserved**
Agent-tdd never invokes research-consolidator or research tools. Only agent-isdd owns research.

### 5. **Task Authority Preserved**
Agent-tdd never changes task definitions. It identifies conflicts and escalates for task re-planning.

### 6. **Non-Blocking Handoff**
While escalations happen, they don't break the contract:
- Design Spec is immutable during per-slice implementation
- Escalations only arise when assumptions were incomplete or conflicting
- Agent-isdd addresses escalations and resumes with updated info

---

## Examples of Escalation Flows

### Example 1: Research Gap During Task Slicing
```
Agent-ISDD sends Design Spec to agent-TDD
  ↓
Agent-TDD validates research → Research valid ✓
  ↓
Agent-TDD begins task slicing
  ↓
Agent-TDD identifies: "Slice 2 requires async error handling, but research/cache.md 
doesn't document async patterns in the codebase"
  ↓
Agent-TDD PAUSES with Research Gap Flag:
"File: src/api/client.ts, Gap: async error handling patterns not documented in cache"
  ↓
Agent-ISDD receives escalation
  ↓
User reviews escalation → "Yes, missing async patterns research"
  ↓
Agent-ISDD runs targeted research-consolidator for async error handling
  ↓
Agent-ISDD updates research/cache.md
  ↓
Agent-ISDD resumes agent-TDD: "Continue task slicing with updated cache"
  ↓
Agent-TDD resumes, validates async patterns are now in cache ✓
  ↓
Agent-TDD completes task slicing with confidence
```

### Example 2: Plan Validity During Implementation
```
Agent-TDD implementing Slice 3 (Login handler)
  ↓
Agent-TDD writes Red test for "valid credentials return token"
  ↓
During Green, discovers acceptance criteria says "login expires after 24 hours"
  ↓
Agent-TDD checks Slice 1 (Token generation): "tokens never expire in Phase 1"
  ↓
Agent-TDD identifies CONFLICT: Slice 1 and Slice 3 have incompatible requirements
  ↓
Agent-TDD PAUSES with Plan Validity Flag:
"Slice 1 requirement: tokens never expire in Phase 1
 Slice 3 requirement: tokens expire after 24 hours
 These are contradictory. Task needs replanning."
  ↓
Agent-ISDD receives escalation
  ↓
User reviews: "Oh, this is a requirements conflict"
  ↓
Agent-ISDD's design-author resolves: "Phase 1 adds token generation, expiration is Phase 2"
  ↓
Agent-ISDD updates design.md and requirements.md
  ↓
Agent-ISDD resumes agent-TDD: "Proceed with Phase 1 scope (no expiration)"
  ↓
Agent-TDD resumes, adjusts Slice 3 acceptance criteria, continues
```

---

## Guarantees

### Agent-TDD Guarantees to Escalate When:
- ✅ Research incomplete or contradictory
- ✅ Task definitions conflict
- ✅ Code structure doesn't match design assumptions
- ✅ Test requirements unachievable within slice scope
- ✅ Dependencies unresolvable without design change

### Agent-TDD Does NOT Silently:
- ✗ Modify design.md
- ✗ Change requirements.md
- ✗ Work around blockers
- ✗ Guess missing research
- ✗ Create code that contradicts assumptions

---

## Conclusion

The Design Spec handoff is **one-directional in monitoring** (agent-isdd doesn't auto-monitor), but **two-way in escalation** (agent-tdd can pause and escalate, agent-isdd can resume with updates).

This design preserves:
- **Authority boundaries**: Design, requirements, research stay with agent-isdd
- **Transparency**: All blockers are explicit, never silent
- **Clarity**: Escalations include specific reasons and evidence
- **Completeness**: Agent-tdd never guesses; it escalates and waits for clarity

The two-way escalation ensures that unexpected changes, missing information, and blockers are surfaced and addressed rather than worked around.
