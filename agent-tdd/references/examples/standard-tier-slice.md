<!-- TDD-SKIP -->
# Worked example: a `standard`-tier slice, single `agent-TDD` invocation

This is a fully illustrative transcript. The feature ("reject negative quantities when creating
an order line item") does not exist anywhere in this repo — it is a small, concrete stand-in
chosen so the mechanics of the Slice Spec contract (see [`INTEROP.md`](../../INTEROP.md)) are
easy to follow without needing any other file open. Field names below match `agent-TDD`'s own
Slice Spec and Handoff report definitions in [`agent-TDD.md`](../../agents/agent-TDD.md).

## Caller's Slice Spec (spawn prompt to `agent-TDD`)

- **Task description**: `OrderLineItem.create(sku, quantity)` currently accepts any integer
  `quantity`, including zero or negative values, and silently creates a line item with that
  value. Reject non-positive quantities.
- **Acceptance criteria / Test Intent**: Calling `OrderLineItem.create(sku, quantity)` with
  `quantity <= 0` raises `ValueError` with a message naming the offending value; it does not
  create or return a line item. Existing behavior for `quantity >= 1` is unchanged.
- **Risk Tier**: `standard`
- **Data Contracts And Interfaces**: `OrderLineItem.create(sku: str, quantity: int) ->
  OrderLineItem`, defined in `orders/line_item.py`. No existing validation on `quantity`.
- **Pre-Slice Brief**: (none — no prior project memory available for this illustrative scenario)
- **Review handoff mode**: unset (defaults to mandatory pause for caller-driven review)

## agent-TDD invocation 1 — Plan through Green, then pause

### Plan

Smallest safe slice: add one guard clause in `OrderLineItem.create`, backed by one test file
covering the boundary (`0`, a negative value, and confirming `1` still passes). Single file to
reach green (`orders/line_item.py`); test lives in `tests/orders/test_line_item.py` alongside
existing coverage for `create`. Rollback point: current file has no quantity validation at all,
so reverting is a clean one-hunk revert if needed.

### Red

Added to `tests/orders/test_line_item.py`:

```python
def test_create_rejects_zero_quantity():
    with pytest.raises(ValueError, match="quantity"):
        OrderLineItem.create(sku="ABC123", quantity=0)

def test_create_rejects_negative_quantity():
    with pytest.raises(ValueError, match="quantity"):
        OrderLineItem.create(sku="ABC123", quantity=-3)

def test_create_still_accepts_positive_quantity():
    item = OrderLineItem.create(sku="ABC123", quantity=1)
    assert item.quantity == 1
```

Ran: `pytest tests/orders/test_line_item.py -k quantity -v`

Result: `test_create_rejects_zero_quantity` and `test_create_rejects_negative_quantity` FAIL
(no `ValueError` raised — line item is created with `quantity=0`/`-3` as-is).
`test_create_still_accepts_positive_quantity` PASSES already (pre-existing behavior). Confirmed
the two new failures are for the intended reason (missing validation), not a setup error.

### Green

`orders/line_item.py` — added a guard at the top of `create`:

```python
if quantity <= 0:
    raise ValueError(f"quantity must be positive, got {quantity}")
```

Ran: `pytest tests/orders/test_line_item.py -k quantity -v` — all three tests PASS.

### Handoff report (pre-review pause)

```
<!--AGENT-TDD-REPORT-->
1. Plan: add a single guard clause to OrderLineItem.create rejecting quantity <= 0; one
   production file, one test file.
2. Test Changes: tests/orders/test_line_item.py — added
   test_create_rejects_zero_quantity, test_create_rejects_negative_quantity,
   test_create_still_accepts_positive_quantity. Written directly (standard tier, no
   test-author split).
3. Implementation Changes: orders/line_item.py — added `if quantity <= 0: raise
   ValueError(...)` guard at the top of `create`, before any line-item construction.
4. Validation Evidence: `pytest tests/orders/test_line_item.py -k quantity -v` — 3 passed,
   0 failed.
5. Acceptance Criteria: met — non-positive quantity now raises ValueError naming the value;
   quantity >= 1 behavior unchanged (existing test still passes).
6. Risks and Follow-ups: no other callers of OrderLineItem.create were audited for reliance
   on the old permissive behavior; a repo-wide grep found none in this pass, but a broader
   codebase search wasn't run (out of scope for this slice's minimum change).
7. Handoff Facts: none (caller has no memory store configured for this illustrative session).
   Research Gap Flag: none — Data Contracts And Interfaces matched the real code shape.

Pausing here per the mandatory review step. Awaiting caller-driven review of
orders/line_item.py and tests/orders/test_line_item.py before proceeding to Refactor.
```

## Caller's review step

Caller runs `code-reviewer` (or equivalent) scoped to `orders/line_item.py` and
`tests/orders/test_line_item.py`. Reviewer clears with no blocking findings — e.g. "guard clause
is minimal and matches existing error-raising conventions elsewhere in `orders/`; no concerns."

## agent-TDD invocation 1 (resumed) — Refactor through final handoff

Caller resumes the same `agent-TDD` instance: "Review cleared, no blocking findings. Proceed to
Refactor."

### Refactor

No structural refactor needed — the guard clause is already minimal and consistent with sibling
validation in the same file (e.g. an existing `sku` non-empty check uses the same
raise-with-f-string style). No changes made.

### Validate

Re-ran `pytest tests/orders/test_line_item.py -v` (full file, not just `-k quantity`) to confirm
no regression in adjacent `create` tests — all passed.

### Final handoff report

```
<!--AGENT-TDD-REPORT-->
1. Plan: (unchanged from pre-review handoff above.)
2. Test Changes: (unchanged.)
3. Implementation Changes: (unchanged — no refactor was needed; guard clause already matched
   existing file conventions.)
4. Validation Evidence: `pytest tests/orders/test_line_item.py -v` — full file, 11 passed
   (3 new + 8 pre-existing), 0 failed.
5. Acceptance Criteria: met, unchanged from pre-review handoff.
6. Risks and Follow-ups: same as pre-review handoff — no repo-wide caller audit performed;
   recommend as a follow-up slice if other modules construct OrderLineItem directly.
7. Handoff Facts: none.

Slice complete.
```
