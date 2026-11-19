# Risk-scaled depth

Read by `spec-driven-development` when setting or raising `Risk` (Start step 6, Design, handoff) or sizing phase depth.

`Risk: low | elevated | high` plus `Risk Reason` live in `workflow-state.md`. `Track` stays the spec-shape signal (Fast = Slice Spec); `Risk` drives depth and review. Hooks enforce the rules (`state_guard`: Fast only when Risk is low, Standard never becomes Fast, Risk can only rise); this file only says how to classify.

## Signals

- **high**: auth/authz, payments, data migration, public or INTEROP interface change, security-sensitive code, concurrency, data deletion.
- **elevated**: multi-module change, shared helpers or contracts other code depends on.
- **low**: none of the above; one small, well-defined change.

Classify by what the change touches. Never use diff size: a "tiny" auth tweak is `high`.

## Depth

Risk sets depth; the only review mechanisms are the ones below.

| Risk | Behaviour |
| --- | --- |
| low | compact path; `Track: Fast` allowed, Slice Spec handoff with `Review handoff mode: skip` (review skipped); on `Track: Fast` design-author also skips plan-reviewer (`fast-track.md`) |
| elevated | full Standard path; no extra review gate (per-phase review by Risk is not implemented) |
| high | full path; every slice needs a reviewed entry or an `AskUserQuestion` Review Fallback before Complete (R3, `complete_guard`) |

Fast at Start: write `Risk: low` (with `Risk Reason`) with or before `Track: Fast`; `state_guard` allows Fast when Risk is low or blank. If a phase finds higher risk than recorded, raise it and tell the user in one line; never lower it (Risk can only rise).
