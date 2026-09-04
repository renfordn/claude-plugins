# Tasks: Session Timeout Warning Banner

## Phase Status

- Current Phase: Tasks
- State: Ready For Implementation
- Last Updated: 2026-07-01

## Execution Rules

- Preserve approved requirements and design intent.
- Keep slices to one behavior change and/or one file or module touched if possible.
- Tests first where implementation follows.
- Refactor only after green.
- Pause on ambiguity, conflicting constraints, weak testability, high-risk migration, or oversized tasks.

## Phase 1: Countdown Visibility

### Objective

Expose remaining-session-time behavior and show the banner only inside the warning window.

### Prerequisites

- Approved requirements and design artifacts.

### Ordered Steps

1. Add unit coverage for remaining-time threshold logic in the auth/session store behavior.
2. Implement remaining-time selector and warning-window derivation.
3. Add controller/component integration coverage for showing and hiding the banner.

### Test Intent

- Add or update:
  - selector threshold unit tests
  - shell banner visibility integration test
- Expected failing behavior:
  - warning window is not derived and banner never renders

### Validation Target

- Command:
  - `pnpm test -- session-timeout`
- Evidence:
  - selector and banner visibility tests pass

### Unlocks

- Enables:
  - refresh interaction behavior in Phase 2

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Phase 2: Extend Session Interaction

### Objective

Allow the user to extend the session from the warning banner with correct pending and failure behavior.

### Prerequisites

- Phase 1 is green.

### Ordered Steps

1. Add tests for extend-session pending, success, and failure states.
2. Wire the banner action to the existing refresh-session endpoint through the controller.
3. Update the banner state for pending and retry paths.

### Test Intent

- Add or update:
  - controller unit tests for refresh states
  - integration test for retry visibility
- Expected failing behavior:
  - extend action dispatch is missing and duplicate requests are possible

### Validation Target

- Command:
  - `pnpm test -- session-timeout`
- Evidence:
  - refresh-state tests pass and duplicate requests are suppressed

### Unlocks

- Enables:
  - expiry logout behavior in Phase 3

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Phase 3: Expiry Logout

### Objective

Log the user out when remaining time reaches zero and the session was not refreshed successfully.

### Prerequisites

- Phase 2 is green.

### Ordered Steps

1. Add tests for zero-time logout behavior.
2. Dispatch the existing logout action from the controller when countdown reaches zero.
3. Verify banner cleanup after logout.

### Test Intent

- Add or update:
  - logout-on-expiry controller unit test
  - integration test for banner removal on logout
- Expected failing behavior:
  - user remains in warning state after expiry

### Validation Target

- Command:
  - `pnpm test -- session-timeout`
- Evidence:
  - logout timing and cleanup tests pass

### Unlocks

- Enables:
  - implementation handoff completion for the feature

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Task Readiness Checklist

- [x] At least one concrete implementation phase exists
- [x] Each phase has explicit objective, steps, test intent, and validation target
- [x] Slices are safe for TDD
- [x] No unresolved blocker requires confirmation before implementation
- [x] State can be marked `Ready For Implementation`
