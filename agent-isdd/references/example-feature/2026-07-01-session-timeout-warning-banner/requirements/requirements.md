# Requirements: Session Timeout Warning Banner

## Status

- Phase: Requirements
- State: Approved
- Last Updated: 2026-07-01

## Source Inputs

- Origin: PRD
- References:
  - AUTH-142

## Problem Statement

Users are being logged out without enough warning to save in-progress work, which causes lost edits and avoidable frustration.

## User Outcome

- Users receive a visible warning before session expiry.
- Users can extend their session before they are logged out.

## Constraints

- [x] Warning must appear 2 minutes before expiry.
- [x] Existing session refresh API must be reused.
- [x] Banner behavior must work on desktop and mobile web.

## Non-Goals

- [x] Do not redesign global authentication flows.
- [x] Do not introduce websocket-based session state.

## Dependencies

- [x] Existing session expiry timestamp in auth state.
- [x] Existing refresh-session endpoint.

## Edge Cases

- [x] Session expiry timestamp is missing or stale.
- [x] User has multiple tabs open.
- [x] Refresh request fails.

## Success Criteria

- [x] Warning is shown exactly once per expiry window.
- [x] User can extend the session without page reload.
- [x] User is logged out when the timer reaches zero and refresh did not succeed.

## EARS Requirements

- `Ubiquitous`: When an authenticated session has more than two minutes remaining, the system shall not show the timeout warning banner.
- `Event-driven`: When an authenticated session reaches two minutes remaining, the system shall show a timeout warning banner.
- `Event-driven`: When the user activates the extend-session action from the banner, the system shall call the existing refresh-session API.
- `State-driven`: While the refresh-session request is in progress, the system shall show the banner in a pending state and prevent duplicate refresh actions.
- `Unwanted-behavior`: If the refresh-session request fails, then the system shall keep the warning visible and allow retry until the session expires.
- `Event-driven`: When the session reaches zero remaining time, the system shall log the user out and remove the banner.

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
