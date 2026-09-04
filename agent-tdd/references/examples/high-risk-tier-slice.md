<!-- TDD-SKIP -->
# Worked example: a `high-risk`-tier slice, `test-author` then `agent-TDD`

This is a fully illustrative transcript. The feature ("stop rounding currency to floats when
computing a refund amount") does not exist anywhere in this repo — it is a small, concrete
stand-in chosen so the mechanics of the Slice Spec contract and the two-part invocation (see
[`INTEROP.md`](../../INTEROP.md)) are easy to follow without needing any other file open. Field
names below match `test-author`'s own Handoff report definitions in
[`test-author.md`](../../agents/test-author.md) and `agent-TDD`'s own Slice Spec and Handoff
report definitions in [`agent-TDD.md`](../../agents/agent-TDD.md).

Unlike the [`standard`-tier example](standard-tier-slice.md), this shows **two distinct agent
invocations** — `test-author` runs to completion and returns its report before `agent-TDD` is
spawned at all. They are not the same agent instance and do not share context; the caller is the
only actor that reads both reports and threads output from one into the other.

## Why this slice is high-risk

The caller's own risk documentation flags `payments/refunds.py` as high-risk: it currently
computes refund amounts using `float` arithmetic, and a past incident traced a customer-facing
refund discrepancy to float rounding. The fix — switching `Refund.compute_amount` to use
`decimal.Decimal` internally — touches money-handling code directly, so the caller invokes the
conditional test-author split rather than letting a single agent write and satisfy its own test.

## Caller's Slice Spec (assembled before either invocation)

- **Task description**: `Refund.compute_amount(unit_price, quantity, discount_pct)` computes
  `unit_price * quantity * (1 - discount_pct / 100)` using Python `float` arithmetic, which
  produces off-by-a-cent rounding errors for some inputs (e.g. `unit_price=19.99, quantity=3,
  discount_pct=15` currently returns `50.9745` before display rounding, not the correct
  `50.97`). Rework the computation to use `decimal.Decimal` internally so results are exact to
  the cent before any display rounding.
- **Acceptance criteria / Test Intent**: `Refund.compute_amount(unit_price=19.99, quantity=3,
  discount_pct=15)` returns a value that, rounded to 2 decimal places, equals `Decimal("50.97")`
  exactly — not a float subject to further rounding ambiguity. A second case,
  `compute_amount(unit_price=10.00, quantity=1, discount_pct=0)`, returns exactly `Decimal(
  "10.00")`. The return type is `decimal.Decimal`, not `float`.
- **Risk Tier**: `high-risk` (traced to the caller's risk documentation on
  `payments/refunds.py`, flagged after a prior float-rounding incident)
- **Data Contracts And Interfaces**: `Refund.compute_amount(unit_price: float, quantity: int,
  discount_pct: float) -> float`, defined in `payments/refunds.py`. Existing tests live in
  `tests/payments/test_refunds.py`.
- **Pre-Slice Brief**: (none — no prior project memory available for this illustrative scenario)
- **Review handoff mode**: unset (defaults to mandatory pause for caller-driven review)

## Invocation 1 — `test-author` (separate agent, runs first, then exits)

Caller spawns `test-author`, passing only the Task description, Test Intent, and Data Contracts
And Interfaces above — no implementation approach, no mention of `agent-TDD`.

### What `test-author` does

Reads `payments/refunds.py` only far enough to confirm `compute_amount`'s current signature and
that it returns a `float`. Adds to `tests/payments/test_refunds.py`:

```python
from decimal import Decimal

def test_compute_amount_is_exact_to_the_cent():
    result = Refund.compute_amount(unit_price=19.99, quantity=3, discount_pct=15)
    assert isinstance(result, Decimal)
    assert result.quantize(Decimal("0.01")) == Decimal("50.97")

def test_compute_amount_handles_zero_discount_exactly():
    result = Refund.compute_amount(unit_price=10.00, quantity=1, discount_pct=0)
    assert isinstance(result, Decimal)
    assert result.quantize(Decimal("0.01")) == Decimal("10.00")
```

Runs: `pytest tests/payments/test_refunds.py -k compute_amount_is_exact_to_the_cent -v` and
`pytest tests/payments/test_refunds.py -k compute_amount_handles_zero_discount -v`.

Result: both FAIL — `isinstance(result, Decimal)` is `False` because `compute_amount` currently
returns a `float`. Confirmed this is the intended-reason failure (missing `Decimal` conversion),
not a setup/typo error.

### `test-author`'s handoff report

```
<!--TEST-AUTHOR-REPORT-->
1. Test file(s): tests/payments/test_refunds.py — added
   test_compute_amount_is_exact_to_the_cent and
   test_compute_amount_handles_zero_discount_exactly, asserting both the return type
   (decimal.Decimal) and the exact quantized value for two cases: a discount that
   previously produced float rounding drift, and a zero-discount baseline.
2. Failure confirmation: `pytest tests/payments/test_refunds.py -k compute_amount -v` — both
   new tests FAIL with `AssertionError: isinstance(result, Decimal)` (result is a float),
   confirming the failure is due to missing Decimal conversion, not a setup error.
3. Open questions: none — the Test Intent's two example cases were concrete enough to assert
   directly.
4. Blockers: none — compute_amount already exists and is callable with the given signature;
   no production stub was needed to make the test fail cleanly.
```

`test-author`'s context ends here. It does not proceed to any implementation step.

## Invocation 2 — `agent-TDD` (separate agent, spawned fresh by the caller)

Caller spawns a fresh `agent-TDD` instance, passing the same Slice Spec plus `test-author`'s two
test functions and failure confirmation verbatim, with an explicit instruction not to re-author
that test.

### Plan

Smallest safe slice: convert `compute_amount`'s internals to `decimal.Decimal` and return a
`Decimal`, backed by the two tests already supplied by `test-author`. Single file to reach green
(`payments/refunds.py`); the test file was already updated by `test-author` and is treated as
Red, not re-written. Rollback point: current `compute_amount` body is a single return expression,
so reverting is a clean one-line revert if needed.

### Red

Test already supplied by `test-author` (not re-authored here): `tests/payments/test_refunds.py`,
`test_compute_amount_is_exact_to_the_cent` and
`test_compute_amount_handles_zero_discount_exactly`.

Re-ran `pytest tests/payments/test_refunds.py -k compute_amount -v` to confirm the failure still
reproduces in this fresh context before touching production code: both FAIL as `test-author`
reported (float returned instead of `Decimal`).

### Green

`payments/refunds.py` — reworked `compute_amount` to build the result from `Decimal` inputs
throughout instead of converting only at the end:

```python
from decimal import Decimal

def compute_amount(self, unit_price, quantity, discount_pct):
    price = Decimal(str(unit_price))
    qty = Decimal(quantity)
    discount = Decimal(str(discount_pct)) / Decimal(100)
    return price * qty * (Decimal(1) - discount)
```

Ran: `pytest tests/payments/test_refunds.py -k compute_amount -v` — both tests PASS.

### `agent-TDD`'s handoff report (pre-review pause)

```
<!--AGENT-TDD-REPORT-->
1. Plan: rework Refund.compute_amount to build its result from decimal.Decimal inputs
   throughout, rather than float arithmetic converted at the end; one production file, test
   file supplied by test-author.
2. Test Changes: tests/payments/test_refunds.py — test_compute_amount_is_exact_to_the_cent
   and test_compute_amount_handles_zero_discount_exactly. Supplied by test-author (high-risk
   tier); not re-authored here.
3. Implementation Changes: payments/refunds.py — compute_amount now converts unit_price and
   discount_pct to Decimal via str() (avoiding float-to-Decimal precision artifacts) before
   any arithmetic, and returns a Decimal rather than a float.
4. Validation Evidence: `pytest tests/payments/test_refunds.py -k compute_amount -v` — 2
   passed, 0 failed.
5. Acceptance Criteria: met — both supplied cases return exact Decimal values quantized to
   the expected cent amount; return type is decimal.Decimal, not float.
6. Risks and Follow-ups: callers of compute_amount that assumed a float return (e.g. any code
   doing further float arithmetic on the result) were not audited in this pass — a repo-wide
   grep found two call sites in payments/api.py that only pass the result to Decimal-aware
   formatting, but a broader audit wasn't run (out of scope for this slice's minimum change).
7. Handoff Facts: none (caller has no memory store configured for this illustrative session).
   Research Gap Flag: none — Data Contracts And Interfaces matched the real code shape.

Pausing here per the mandatory review step. Awaiting caller-driven review of
payments/refunds.py and tests/payments/test_refunds.py before proceeding to Refactor.
```

## Caller's review step

Caller runs `code-reviewer` (or equivalent) scoped to `payments/refunds.py` and
`tests/payments/test_refunds.py`. Reviewer clears with no blocking findings — e.g. "Decimal
conversion goes through `str()` correctly, avoiding float-precision leakage into the Decimal
constructor; no concerns."

## `agent-TDD` invocation 2 (resumed) — Refactor through final handoff

Caller resumes the same `agent-TDD` instance (not a new invocation — the review pause happens
within this same agent, per `INTEROP.md`'s review-pause contract): "Review cleared, no blocking
findings. Proceed to Refactor."

### Refactor

No structural refactor needed — the Decimal conversion is already minimal and localized to
`compute_amount`'s body. No changes made.

### Validate

Re-ran `pytest tests/payments/test_refunds.py -v` (full file, not just `-k compute_amount`) to
confirm no regression in adjacent `Refund` tests — all passed.

### Final handoff report

```
<!--AGENT-TDD-REPORT-->
1. Plan: (unchanged from pre-review handoff above.)
2. Test Changes: (unchanged — supplied by test-author, not re-authored.)
3. Implementation Changes: (unchanged — no refactor was needed; Decimal conversion already
   localized and minimal.)
4. Validation Evidence: `pytest tests/payments/test_refunds.py -v` — full file, 9 passed
   (2 new + 7 pre-existing), 0 failed.
5. Acceptance Criteria: met, unchanged from pre-review handoff.
6. Risks and Follow-ups: same as pre-review handoff — no repo-wide caller audit performed;
   recommend as a follow-up slice auditing all call sites of compute_amount for float-return
   assumptions beyond the two already checked in payments/api.py.
7. Handoff Facts: none.

Slice complete.
```
