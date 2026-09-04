---
name: slice-spec
description: Assemble a Slice Spec for agent-TDD (and, for high-risk slices, test-author) from the task at hand, and emit it as a correctly formatted spawn prompt block. Use this before spawning either agent, or whenever a caller needs to check that a Slice Spec is complete and valid against the contract in INTEROP.md and references/slice-spec.schema.json.
---

# Assembling a Slice Spec

`agent-TDD` and `test-author` take no file of their own — every field of the Slice Spec must be
passed inline in the spawn prompt, correctly named, every time. This skill turns "I need to
implement X" into a validated Slice Spec block ready to paste into the spawn prompt, so the fields
don't have to be re-derived and re-typed by hand for every slice. The full narrative contract this
mirrors lives in [`INTEROP.md`](../../INTEROP.md); the machine-checkable version lives in
[`references/slice-spec.schema.json`](../../references/slice-spec.schema.json).

## When to use this

- Before spawning `agent-TDD` for any slice — standard or high-risk.
- Before spawning `test-author`, to derive the subset of fields it needs.
- When re-checking an already-drafted Slice Spec for a missing required field or an invalid
  enum value before burning a spawn on it.

## What to gather

Six fields, two required:

1. **Task description** (required) — the behavior to implement, in plain language. Ask "what
   should change, in observable terms?" if this isn't already stated.
2. **Acceptance criteria / Test Intent** (required) — the observable behavior a test must pin
   down. If this can't be stated concretely yet, stop here and say so rather than inventing
   criteria — neither agent will proceed without it either.
3. **Risk Tier** (optional, default `standard`) — set `high-risk` only when the slice traces to a
   named risk in the caller's own design/risk documentation, or is a high-risk migration (e.g.
   money handling, auth, data migrations touching production data). Most slices stay `standard`.
4. **Data Contracts And Interfaces** (optional) — type signatures, module boundaries, or API
   shapes already known. Skip this field entirely rather than guessing — a stale or invented
   value here is worse than omitting it, since `agent-TDD` will trust what's given and only
   raises a Research Gap Flag when it actively contradicts the real code (see
   [`references/examples/research-gap-flag-slice.md`](../../references/examples/research-gap-flag-slice.md)).
5. **Pre-Slice Brief** (optional) — prior project context already gathered (e.g. from a memory
   subagent). Purely additive.
6. **Review handoff mode** (optional, default pause) — leave unset unless there is deliberately no
   reviewer available this session; only then set it to `skip` explicitly (see
   [`references/examples/review-skip-slice.md`](../../references/examples/review-skip-slice.md)).
   Never set `skip` as a shortcut to avoid review — that defeats the property the pause exists to
   protect.

## Validating before spawning

Check the assembled spec against
[`references/slice-spec.schema.json`](../../references/slice-spec.schema.json):

- `taskDescription` and `acceptanceCriteria` are both non-empty strings — required.
- `riskTier`, if set, is exactly `standard` or `high-risk`.
- `reviewHandoffMode`, if set, is exactly `pause` or `skip`.
- No other field names — the schema sets `additionalProperties: false`, so a typo'd field name
  (e.g. `riskTeir`) would silently be ignored by a human reader but should be caught here instead.

## Output format

Emit the spec as a spawn-prompt-ready block, matching the field names and phrasing used in
`agent-TDD.md`'s own Slice Spec section and the worked examples under `references/examples/`:

```
- **Task description**: <plain-language behavior to implement>
- **Acceptance criteria / Test Intent**: <observable behavior a test must pin down>
- **Risk Tier**: `standard` | `high-risk` (<why, if high-risk>)
- **Data Contracts And Interfaces**: <known signatures/boundaries, or "(none — agent-TDD will explore the codebase itself)">
- **Pre-Slice Brief**: <prior context, or "(none)">
- **Review handoff mode**: unset (default pause) | `skip` (<why>)
```

For a `high-risk` slice, additionally note that `test-author` must be spawned first with only the
Task description, Acceptance criteria, and Data Contracts And Interfaces fields — not Risk Tier,
Pre-Slice Brief, or Review handoff mode, which are `agent-TDD`-only concerns — and that its
returned test file(s) and failure confirmation get folded into `agent-TDD`'s own spawn prompt
afterward, per the two-part invocation in `INTEROP.md`.

## Guardrails

- Do not invent Acceptance criteria or Data Contracts And Interfaces to fill a gap — surface the
  gap instead, the same way `agent-TDD` itself would refuse to guess.
- Do not default `Risk Tier` to `high-risk` "to be safe" — it has a real token cost (an extra
  agent hop via `test-author`) and should trace to an actual documented risk.
- Do not set `Review handoff mode: skip` unless the caller has explicitly decided no reviewer is
  available this session — never as a way to move faster.
- This skill only assembles and validates the spec — it does not spawn `agent-TDD` or
  `test-author` itself.
