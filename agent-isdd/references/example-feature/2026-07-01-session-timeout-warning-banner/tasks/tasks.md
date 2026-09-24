# Tasks: Session Timeout Warning Banner

## Slice 1: Show the warning banner only inside the two-minute remaining-time window

**Risk Tier:** standard
**Depends On:** none
**Files:** auth/session-store, shell/session-timeout-banner, shell/session-timeout-controller

### Test Intent
A remaining-time selector derives the warning window from the expiry timestamp, and the banner renders only while `0 < remainingMs <= 120000`.

### Validation Target
`pnpm test -- session-timeout` — selector and banner visibility tests pass.

### Ordered Steps
1. Add unit coverage for remaining-time threshold logic in the auth/session store behavior.
2. Implement remaining-time selector and warning-window derivation.
3. Add controller/component integration coverage for showing and hiding the banner.

---

## Slice 2: Extend the session from the warning banner with correct pending and failure states

**Risk Tier:** standard
**Depends On:** Slice 1
**Files:** shell/session-timeout-controller

### Test Intent
The banner's extend action dispatches the existing refresh-session command exactly once while a request is pending, and surfaces retry on failure.

### Validation Target
`pnpm test -- session-timeout` — refresh-state tests pass and duplicate requests are suppressed.

### Ordered Steps
1. Add tests for extend-session pending, success, and failure states.
2. Wire the banner action to the existing refresh-session endpoint through the controller.
3. Update the banner state for pending and retry paths.

---

## Slice 3: Log the user out when remaining time reaches zero without a successful refresh

**Risk Tier:** standard
**Depends On:** Slice 2
**Files:** shell/session-timeout-controller

### Test Intent
The controller dispatches the existing logout action once remaining time reaches zero, and the banner is removed after logout.

### Validation Target
`pnpm test -- session-timeout` — logout timing and cleanup tests pass.

### Ordered Steps
1. Add tests for zero-time logout behavior.
2. Dispatch the existing logout action from the controller when countdown reaches zero.
3. Verify banner cleanup after logout.
