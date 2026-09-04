# Design: Session Timeout Warning Banner

## Status

- Phase: Design
- State: Approved
- Last Updated: 2026-07-01

## Design Summary

Add a session-timeout banner controller in the auth-aware frontend shell that derives countdown state from the existing expiry timestamp, renders a warning banner at the two-minute threshold, and delegates session extension to the existing refresh endpoint.

## Scope Mapping To Requirements

- Requirement: Show a warning at two minutes remaining.
  - Design Response: A countdown selector computes remaining time and toggles banner visibility at the threshold.
- Requirement: Allow extension without reload.
  - Design Response: Banner action dispatches the existing refresh-session command and updates auth expiry state on success.
- Requirement: Log user out at zero.
  - Design Response: Countdown controller dispatches the existing logout action once remaining time is exhausted.

## Architecture Or Code Touchpoints

- `auth/session-store`: expose reactive remaining-time selector.
- `shell/session-timeout-banner`: new presentational banner component.
- `shell/session-timeout-controller`: new behavior/controller to coordinate visibility, refresh, and logout.

## Data Contracts And Interfaces

- Interface: `SessionTimeoutState`
  - Inputs: `expiryTimestamp`, `refreshStatus`, `isAuthenticated`
  - Outputs: `remainingMs`, `showWarning`, `isRefreshing`
  - Invariants: warning appears only when authenticated and `0 < remainingMs <= 120000`

- Interface: `extendSession()`
  - Inputs: none
  - Outputs: refresh request promise
  - Invariants: duplicate requests are suppressed while pending

## States, Flows, And Edge-Case Handling

- Primary flow:
  - Auth state exposes expiry timestamp.
  - Controller derives remaining time on an interval.
  - Banner appears at two minutes remaining.
  - User extends session.
  - Refresh succeeds and expiry timestamp updates.

- Edge case:
  - Expiry timestamp missing.
  - Controller does not show banner and logs diagnostic state.

- Edge case:
  - Refresh fails.
  - Banner remains visible with retry action enabled.

- Edge case:
  - Multiple tabs.
  - Each tab reacts to its local auth-state updates; no new cross-tab protocol is introduced in this slice.

## Validation Strategy

- Unit:
  - Countdown selector threshold logic.
  - Controller behavior for refresh pending, success, and failure.
- Integration:
  - Banner visibility and action wiring through shell + auth store.
- Manual:
  - Simulate near-expiry session and verify banner, retry, and logout timing.

## Risks And Tradeoffs

- Risk: Interval-driven countdown may create flaky timing tests.
  - Mitigation: use fake timers in unit coverage.
- Risk: Multi-tab drift remains possible.
  - Mitigation: keep this out of scope and document it explicitly.

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
