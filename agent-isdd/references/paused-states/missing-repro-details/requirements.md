# Requirements: Duplicate Toast On Retry

## Status

- Phase: Requirements
- State: Blocked
- Last Updated: 2026-07-01

## Source Inputs

- Origin: bug report
- References:
  - support message: "sometimes I get two success toasts when retrying"

## Problem Statement

Users may see duplicate success toasts after retrying a failed operation, but the exact trigger sequence is not yet precise enough to isolate the defect safely.

## User Outcome

- Users should see a single success toast per successful retry flow.

## Constraints

- [x] Existing retry UX should remain unchanged.

## Non-Goals

- [x] Do not redesign the broader toast framework.

## Dependencies

- [ ] Exact reproduction sequence for the fail-then-success path.
- [ ] Confirmation of expected error-toast behavior before and after retry.

## Edge Cases

- [ ] Whether duplicate toasts happen only after one retry or after multiple retries.

## Success Criteria

- [ ] A failing test can reproduce the bug deterministically.

## EARS Requirements

- `Event-driven`: When a retry succeeds after a prior failure, the system shall emit at most one success toast.

## Open Gaps

- [ ] Missing exact reproduction steps.
- [ ] Missing observed versus expected notification sequence.

## Approval Checkpoint

- [x] Problem statement is clear
- [x] User outcome is clear
- [x] Constraints are clear
- [x] Non-goals are clear
- [ ] Dependencies are clear
- [ ] Edge cases are clear
- [ ] Success criteria are clear
- [x] EARS requirements are present
- [ ] No unresolved ambiguity remains

## Phase Completion

- [ ] All required requirement sections are populated
- [ ] Approval Checkpoint is fully satisfied
- [ ] Open Gaps contains no blocking unresolved item
- [ ] State can be marked `Approved`
