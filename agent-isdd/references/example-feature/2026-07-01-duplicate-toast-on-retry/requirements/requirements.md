# Requirements: Duplicate Toast On Retry

## Status

- Phase: Requirements
- State: Approved
- Last Updated: 2026-07-01

## Source Inputs

- Origin: bug report
- References:
  - UI-517
  - support report: duplicate success toast after retrying failed save

## Problem Statement

Users sometimes see the same success toast twice after retrying a failed save action, which creates confusion about whether multiple saves were triggered.

## User Outcome

- Users see at most one success toast for a single successful save outcome.
- Retrying after a failed save does not produce duplicate notifications.

## Constraints

- [x] Existing save API behavior must remain unchanged.
- [x] Fix should stay within current notification and retry flow.
- [x] Existing error toast behavior must be preserved.

## Non-Goals

- [x] Do not redesign the notification system.
- [x] Do not change retry UX copy or layout.

## Dependencies

- [x] Existing retryable save action handler.
- [x] Current toast dispatch utility.
- [x] Reproduction fixture or deterministic failing test harness for retry flow.

## Edge Cases

- [x] First attempt fails and retry succeeds.
- [x] User retries multiple times before a success.
- [x] Save resolves after a previously failed attempt left stale local state.

## Success Criteria

- [x] A successful retry emits exactly one success toast.
- [x] Error-to-success transition keeps one error toast and one success toast in correct order.
- [x] Repeating retries without success does not emit success toasts prematurely.

## EARS Requirements

- `Event-driven`: When a save attempt succeeds after one or more retries, the system shall emit exactly one success toast for the successful attempt.
- `Unwanted-behavior`: If a previous failed attempt left queued notification state, then the system shall not emit duplicate success toasts when a retry succeeds.
- `State-driven`: While a retryable save attempt is still pending, the system shall not emit a success toast.
- `Event-driven`: When a retry fails, the system shall preserve existing error notification behavior.

## Open Gaps

- [x] No blocking requirement gaps remain.

## Approval Checkpoint

- [x] Problem statement is clear
- [x] User outcome is clear
- [x] Constraints are clear
- [x] Non-goals are clear
- [x] Dependencies are clear
- [x] Edge cases are clear
- [x] Success criteria are clear
- [x] EARS requirements are present
- [x] No unresolved ambiguity remains

## Phase Completion

- [x] All required requirement sections are populated
- [x] Approval Checkpoint is fully satisfied
- [x] Open Gaps contains no blocking unresolved item
- [x] State can be marked `Approved`
