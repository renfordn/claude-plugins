# Tasks: Duplicate Toast On Retry

## Slice 1: Reproduce the duplicate success-toast defect with a deterministic failing test

**Risk Tier:** standard
**Depends On:** none
**Files:** save-flow/retry-handler

### Test Intent
A fail-then-success retry flow currently emits the success toast twice; the test asserts exactly one.

### Validation Target
`pnpm test -- duplicate-toast` — failing test reproduces the duplicate-toast defect.

### Ordered Steps
1. Add integration coverage for fail-then-success retry flow.
2. Assert that only one success toast should be emitted.
3. Confirm the test fails for the current duplicate-toast behavior.

---

## Slice 2: Restrict success-toast dispatch to the final successful retry attempt only

**Risk Tier:** standard
**Depends On:** Slice 1
**Files:** save-flow/retry-handler, ui/toast-dispatch

### Test Intent
Only the resolved successful attempt dispatches the success toast; first-attempt success and repeated failed retries keep their existing toast behavior.

### Validation Target
`pnpm test -- duplicate-toast` — retry bug and notification regression tests pass.

### Ordered Steps
1. Implement the smallest guard or state reset needed to prevent duplicate success emission.
2. Re-run the retry-flow test to green.
3. Add regression coverage for first-attempt success and repeated failed retries.
