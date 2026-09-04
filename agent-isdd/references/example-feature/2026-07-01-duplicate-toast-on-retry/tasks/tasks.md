# Tasks: Duplicate Toast On Retry

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

## Phase 1: Reproduce With Failing Test

### Objective

Capture the duplicate-toast bug with a deterministic failing test.

### Prerequisites

- Approved requirements and design artifacts.

### Ordered Steps

1. Add integration coverage for fail-then-success retry flow.
2. Assert that only one success toast should be emitted.
3. Confirm the test fails for the current duplicate-toast behavior.

### Test Intent

- Add or update:
  - retry flow integration test
- Expected failing behavior:
  - success toast emitted twice after successful retry

### Validation Target

- Command:
  - `pnpm test -- duplicate-toast`
- Evidence:
  - failing test reproduces the duplicate-toast defect

### Unlocks

- Enables:
  - minimal fix in Phase 2

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Phase 2: Minimal Notification Fix

### Objective

Restrict success-toast dispatch to the final successful retry path only.

### Prerequisites

- Phase 1 is green-red with the intended failing test.

### Ordered Steps

1. Implement the smallest guard or state reset needed to prevent duplicate success emission.
2. Re-run the retry-flow test to green.
3. Add regression coverage for first-attempt success and repeated failed retries.

### Test Intent

- Add or update:
  - first-attempt success regression test
  - repeated failed-retry notification regression test
- Expected failing behavior:
  - minimal fix prevents duplicate success toast while preserving other toast behavior

### Validation Target

- Command:
  - `pnpm test -- duplicate-toast`
- Evidence:
  - retry bug and notification regression tests pass

### Unlocks

- Enables:
  - bugfix implementation handoff completion

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Task Readiness Checklist

- [x] At least one concrete implementation phase exists
- [x] Each phase has explicit objective, steps, test intent, and validation target
- [x] Slices are safe for TDD
- [x] No unresolved blocker requires confirmation before implementation
- [x] State can be marked `Ready For Implementation`
