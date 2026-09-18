---
name: agent-tdd
description: Implement features via research validation, task slicing, and strict Red-Green-Refactor per slice. Orchestrates per-slice reviews at appropriate levels (Quick/Standard/Deep) and post-slices coherence review (Deep/Ultra based on high-risk composition).
---

# Agent-TDD

This agent orchestrates the implementation phase of spec-driven development: research validation, 
task slicing (producing `tasks.md`), and Red-Green-Refactor loops with tiered code review checkpoints.

## Automatic Code-Reviewer Invocation

Agent-TDD invokes `/code-reviewer` at strategic points in the Red-Green-Refactor loop, using 
tiered review levels (Quick/Standard/Deep/Ultra) to balance comprehensiveness with token efficiency.

**Core principle**: review level is determined by phase context (Red/Green/Refactor/Coherence) 
and risk tier (high-risk vs. standard), not by human request. Auto-detection rules simplify 
caller reasoning.

## Review-Level Strategy

### Per-Slice Review Checkpoints

Each slice follows four review checkpoints:

#### 1. Red Phase: Quick Review (Test Clarity)
- **When**: Test has been written, before implementation begins
- **Scope**: New test file
- **Review Level**: `Quick` (minimal checks, test clarity only)
- **Focus**: 
  - Is test intent clear from the code?
  - Is acceptance criteria wording unambiguous?
  - Does the test structure match standard patterns?
- **Invoked by**: `test-author` (if high-risk; otherwise agent-tdd writes test)

#### 2. Green Phase: Standard or Deep Review (Implementation Check)
- **When**: Test passes, implementation is complete
- **Scope**: All files modified for this slice
- **Review Level Mapping**:
  - If `risk_tier == high_risk`: **Deep** review
  - Else: **Standard** review
- **Deep Review Focus** (high-risk slices):
  - Design patterns, potential regressions, edge cases
  - Security-relevant changes, core abstractions
  - Module boundary integrity
- **Standard Review Focus** (normal slices):
  - Implementation correctness, naming clarity
  - Import/export correctness, basic design coherence
  - API contract consistency
- **Invoked by**: agent-tdd

#### 3. Refactor Pause: Quick Review (Refactor Safety Check)
- **When**: Before beginning refactoring, after Green phase passes
- **Scope**: Refactor intent (pseudo-code or comment describing planned changes)
- **Review Level**: `Quick` (sanity check only)
- **Focus**:
  - Refactor intent is sound?
  - Planned changes won't alter test behavior?
- **Invoked by**: agent-tdd (results guide user confirmation decision)

#### 4. Post-All-Slices Coherence Review (Cross-Slice Validation)
- **When**: All slices are Green + Refactored
- **Scope**: All modified files from all slices combined
- **Review Level Determination**:
  ```
  high_risk_count = count(slices with risk_tier == "high_risk")
  total_slices = count(all slices)
  if high_risk_count / total_slices > 0.5 AND multi_agent_available():
    review_level = Ultra
  else:
    review_level = Deep
  ```
- **Focus Areas**:
  - Cross-slice interactions (do changes from slice 3 conflict with slice 1?)
  - Duplicate detection (did slices introduce redundancy?)
  - Module boundaries (are abstractions leaking between slices?)
  - Regression risk (could these changes break existing tests outside slice scope?)
  - (Ultra only) Security implications of combined changes, performance impact
- **Gate Logic**:
  - **Critical findings**: Block implementation completion, suggest re-slicing or escalation
  - **Non-critical findings**: Document as follow-up tasks, allow completion
- **Invoked by**: agent-tdd

### Auto-Detection Logic

Review level is auto-detected when caller doesn't specify it explicitly. Priority order 
(per design.md §Auto-Detection Rules):

1. **Explicit request** (highest priority): If caller specifies `review_level`, use it
2. **Phase context**:
   - Red phase → `Quick`
   - Green phase → `Standard` (or `Deep` if `risk_tier == high_risk`)
   - Refactor pause → `Quick`
   - Coherence phase → `Deep` (or `Ultra` if majority high-risk)
3. **File scope** (if available):
   - Single function → `Quick`
   - Single file → `Standard`
   - Multiple files → `Deep`
   - Entire module → `Ultra`
4. **Prior context** (if reviewing same code multiple times):
   - Escalate by one level (`Quick` → `Standard` → `Deep` → `Ultra`)
5. **Fallback** (lowest priority): `Standard`

### Finding Flow to Ralph Loops

Review findings feed into ralph loops validation:

- **Design-phase Deep review findings** (from design-author) → Traceability validation input
- **Per-slice Standard review findings** → Per-slice correctness validation
- **Coherence review findings** → Cross-slice regression detection
- All findings inform ralph loops' Traceability validation loop to ensure design decisions 
  were respected through implementation

## Success Criteria

Agent-TDD completes successfully when:

- All slices implement Red-Green-Refactor with appropriate review checkpoints
- High-risk slices are reviewed at Deep level; standard slices at Standard level
- Coherence review is run after all slices with correct level (Deep or Ultra based on composition)
- All findings are captured and categorized (critical vs. non-critical)
- Ralph loops validation passes for Traceability and Dependency Correctness

## Cross-References

- **Design rationale**: `design.md` §Agent-TDD Integration, §Review-Level Strategy
- **ISDD integration**: `agent-isdd/INTEROP.md` §Strategic Review Placement
- **Code-reviewer contract**: `code-reviewer/SKILL.md` §Review Levels, §Auto-Detection Rules
- **Ralph loops integration**: `agent-tdd/agents/ralph-loops.md`

See those documents for implementation details, trade-offs, and design rationale.
