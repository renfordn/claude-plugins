<!-- TDD-SKIP -->
# Worked example: `Review handoff mode: skip`, no pause between Green and Refactor

This is a fully illustrative transcript. The feature ("trim trailing whitespace from a saved
note's title") does not exist anywhere in this repo — it is a small, concrete stand-in chosen so
the mechanics of the explicit review-skip path (see [`INTEROP.md`](../../INTEROP.md)) are easy to
follow without needing any other file open. Field names below match `agent-TDD`'s own Slice Spec
and Handoff report definitions in [`agent-TDD.md`](../../agents/agent-TDD.md).

Unlike the [`standard`-tier example](standard-tier-slice.md), the caller here has deliberately
decided — not defaulted — that no reviewer is available this session, and sets **Review handoff
mode: skip** explicitly in the Slice Spec. `agent-TDD` runs straight through Plan → Red → Green →
Refactor → Validate in a single pass, with no pause and no second resume message.

## Caller's Slice Spec (spawn prompt to `agent-TDD`)

- **Task description**: `Note.save()` persists the `title` field exactly as typed, including any
  trailing whitespace, which then shows up as an odd-looking gap in list views. Trim trailing
  whitespace from `title` before persisting.
- **Acceptance criteria / Test Intent**: Calling `Note(title="Groceries   ").save()` persists a
  note whose `title` is `"Groceries"` (no trailing whitespace). Leading whitespace and internal
  whitespace are left untouched. A title that is entirely whitespace still saves as an empty
  string, not `None` — existing "empty title allowed" behavior is unchanged.
- **Risk Tier**: `standard`
- **Data Contracts And Interfaces**: `Note.save(self) -> None`, defined in `notes/models.py`; sets
  `self.title` in place before writing to the store. No existing whitespace handling.
- **Pre-Slice Brief**: (none — no prior project memory available for this illustrative scenario)
- **Review handoff mode**: `skip` — caller has no reviewer available this session and is making
  that call explicitly, not letting it default.

## `agent-TDD` invocation — single pass, Plan through final handoff

### Plan

Smallest safe slice: trim trailing whitespace from `title` in `Note.save`, backed by one test file
covering trailing-only, leading-preserved, and whitespace-only cases. Single file to reach green
(`notes/models.py`); test lives in `tests/notes/test_models.py` alongside existing coverage for
`save`. Rollback point: current `save` has no whitespace handling at all, so reverting is a clean
one-hunk revert if needed.

### Red

Added to `tests/notes/test_models.py`:

```python
def test_save_trims_trailing_whitespace_from_title():
    note = Note(title="Groceries   ")
    note.save()
    assert note.title == "Groceries"

def test_save_preserves_leading_and_internal_whitespace():
    note = Note(title="  Grocery list  ")
    note.save()
    assert note.title == "  Grocery list"

def test_save_allows_whitespace_only_title_as_empty_string():
    note = Note(title="   ")
    note.save()
    assert note.title == ""
```

Ran: `pytest tests/notes/test_models.py -k save_trims -v` and the two related `-k` runs above.

Result: `test_save_trims_trailing_whitespace_from_title` and
`test_save_allows_whitespace_only_title_as_empty_string` FAIL (title persisted unchanged, with
trailing/only whitespace intact). `test_save_preserves_leading_and_internal_whitespace` PASSES
already (no leading-trim behavior exists to break). Confirmed the two new failures are for the
intended reason (missing trailing-whitespace trim), not a setup error.

### Green

`notes/models.py` — in `save`, before persisting:

```python
self.title = self.title.rstrip()
```

Ran: `pytest tests/notes/test_models.py -k save -v` — all three tests PASS.

### Review — explicitly skipped

Slice Spec set **Review handoff mode: skip**. Per the mandatory-review-pause rule in
`agent-TDD.md`, this is the one condition under which the pause does not happen: proceeding
directly to Refactor in the same pass, no caller resume needed.

### Refactor

No structural refactor needed — `self.title.rstrip()` is a single expression, already minimal and
consistent with the file's existing style (no other field on `Note` has whitespace handling to
match against). No changes made.

### Validate

Re-ran `pytest tests/notes/test_models.py -v` (full file, not just `-k save`) to confirm no
regression in adjacent `Note` tests — all passed.

### Final handoff report

```
<!--AGENT-TDD-REPORT-->
1. Plan: trim trailing whitespace from Note.title in Note.save via a single rstrip() call;
   one production file, one test file.
2. Test Changes: tests/notes/test_models.py — added test_save_trims_trailing_whitespace_from_title,
   test_save_preserves_leading_and_internal_whitespace,
   test_save_allows_whitespace_only_title_as_empty_string. Written directly (standard tier, no
   test-author split).
3. Implementation Changes: notes/models.py — added `self.title = self.title.rstrip()` in `save`,
   before persisting.
4. Validation Evidence: `pytest tests/notes/test_models.py -v` — full file, 9 passed (3 new + 6
   pre-existing), 0 failed.
5. Acceptance Criteria: met — trailing whitespace trimmed; leading/internal whitespace and the
   whitespace-only-saves-as-empty-string behavior are unchanged.
6. Risks and Follow-ups: Review handoff mode was set to skip for this slice — no caller-driven
   review occurred. Recommend a follow-up review pass over notes/models.py and
   tests/notes/test_models.py whenever a reviewer becomes available this session or a later one.
7. Handoff Facts: none (caller has no memory store configured for this illustrative session).
   Research Gap Flag: none — Data Contracts And Interfaces matched the real code shape.

Slice complete. No review pause occurred — Review handoff mode was explicitly set to skip.
```

## Why this differs from the default path

Compare to the [`standard`-tier example](standard-tier-slice.md), which pauses after Green and
requires the caller to resume the same agent instance once review clears. Here there is exactly
one invocation and one handoff report, because the caller made the "no review this session"
tradeoff explicit up front rather than silently skipping it — `agent-TDD` still records that
tradeoff in **Risks and Follow-ups** so it isn't lost by the time anyone reads the handoff later.
