---
name: task-slicer
description: "[Internal — delegated by agent-tdd] Validates and refines task.md output with Standard-level code review for clarity and dependency correctness before implementation phase."
---

# Task Slicer

## Use This Skill When

After task slicing is complete and `tasks.md` has been generated from an approved design, 
before the implementation phase begins. This skill validates task clarity, dependency correctness, 
and validation-step feasibility.

## Task Clarity Validation: Standard Review

After `tasks.md` is generated, invoke `/code-reviewer` at **Standard** review level against 
`tasks.md` to validate task clarity, Depends-On correctness, and step sequencing before 
implementation begins.

**Step: Task Clarity and Dependency Validation**

1. Invoke `/code-reviewer` skill with:
   - **Mode**: `direct-review`
   - **Scope**: `tasks.md` (full task definitions artifact)
   - **`review_level`**: `Standard` (clarity check, dependency validation)

2. Focus areas for Standard review in task context:
   - Task phrasing clarity (is each task's one-sentence behavior clear?)
   - Depends-On correctness (do dependencies form an acyclic graph?)
   - Validation step feasibility (can each task's validation actually be run?)
   - Step sequencing (are ordered steps logically sequenced?)
   - Risk Tier assignment (is high-risk vs. standard tier appropriate?)

3. Gate logic:
   - **Clarity issues**: Suggest task rewording or ask for clarification.
   - **Dependency issues**: Flag for ralph loops validation; may need re-slicing.
   - **Validation step issues**: Ensure each step is achievable and measurable.
   - **No blocking issues**: Proceed to implementation phase.

4. Output: Attach Standard review findings to the handoff so that task-level concerns 
   are visible during implementation planning (ralph loops Dependency Correctness validation 
   may consume these findings).

**Rationale**: This upfront Standard review catches task clarity issues and dependency 
conflicts early, before Red-Green-Refactor cycles. Findings feed into ralph loops' 
Dependency Correctness validation. See `code-reviewer/SKILL.md`'s "Review Levels" section 
for Standard level definition and `design.md` §ISDD Workflow Integration for strategic 
review placement.

## Task Success Criteria

Task Slicer completes successfully when:

- `tasks.md` passes Standard review (or issues are documented as known constraints)
- All task Depends-On relationships form an acyclic graph
- Each task's validation step is feasible and measurable
- Risk Tier assignments are appropriate (high-risk slices are flagged)
- No unresolved dependency contradictions remain

## Handoff to Implementation

Return task findings and any Depends-On/clarity concerns to the caller so that 
agent-tdd can begin implementation with full visibility into task structure 
and known issues.
