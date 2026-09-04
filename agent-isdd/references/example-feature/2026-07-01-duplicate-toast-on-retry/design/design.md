# Design: Duplicate Toast On Retry

## Status

- Phase: Design
- State: Approved
- Last Updated: 2026-07-01

## Design Summary

Tighten the retryable save flow so toast emission is coupled only to the currently resolved successful attempt, using a single notification path that clears stale pending notification state before dispatch.

## Scope Mapping To Requirements

- Requirement: Emit one success toast after successful retry.
  - Design Response: Centralize success-toast dispatch in the final resolved success branch only.
- Requirement: Preserve existing error behavior.
  - Design Response: Leave error toast path unchanged and only adjust success emission guards.

## Architecture Or Code Touchpoints

- `save-flow/retry-handler`: ensure only active attempt can trigger success notification.
- `ui/toast-dispatch`: reuse existing helper with no API change.

## Data Contracts And Interfaces

- Interface: `handleRetryableSave()`
  - Inputs: save payload and retry context
  - Outputs: success or failure resolution
  - Invariants: success-toast dispatch occurs at most once per completed success path

## States, Flows, And Edge-Case Handling

- Primary flow:
  - initial save fails
  - user retries
  - retry succeeds
  - single success toast emitted

- Edge case:
  - multiple retries before success
  - only the successful attempt emits the success toast

- Edge case:
  - stale queued notification state
  - cleared or ignored before success dispatch

## Validation Strategy

- Unit:
  - retry handler success-toast emission guard
- Integration:
  - retry flow with fail-then-success fixture
- Manual:
  - verify single success toast after retry in UI flow

## Risks And Tradeoffs

- Risk: Fix may suppress legitimate success toasts in non-retry saves.
  - Mitigation: add regression coverage for first-attempt success.

## Open Questions

- [x] No blocking design questions remain for this slice.

## Phase Decision

- [x] Design supports current requirements
- [x] Design is testable
- [x] Design avoids unresolved contradictions
- [x] Ready to move to Tasks

## Phase Completion

- [x] Requirement coverage is explicit
- [x] Architecture or code touchpoints are named
- [x] Interfaces or contracts are described
- [x] Validation strategy is credible
- [x] Phase Decision is fully satisfied
- [x] State can be marked `Approved`
