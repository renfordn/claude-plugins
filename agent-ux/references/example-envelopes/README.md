# Example Envelopes

This folder contains one recorded example UX Event Envelope per `event_type`, mirroring
`agent-isdd/references/example-feature/`'s pattern of filled specimens used as a reference for
expected shape — plus one additional fixture (`tdd-stage-exclusion.md`) covering a caller-keyed
variant of `phase_transition` whose expected output differs from the general case.

These examples encode the schema from `agent-ux`'s Data Contracts And Interfaces (envelope:
`caller`, `event_type`, `phase_state`, `delta`, `artifact_path`) before `INTEROP.md` exists to
formalize it in prose. Until `INTEROP.md` is written, these files are the only checkable
definition of what a valid `delta` looks like per `event_type` — a reviewer can compare any
caller's constructed envelope against the matching file here by hand.

Use them as a reference for:
- exact envelope field names and nesting per `event_type`
- what `delta` does and does not contain (never a full artifact body, except the single named
  section in `section_checkpoint`)
- the `breadcrumb_only` minimality invariant (no fields beyond `phase_state`)
- realistic values for `caller`, `phase_state`, and `artifact_path`

Files:
- `breadcrumb-only.md` — cheapest, highest-frequency event; `delta` is empty.
- `phase-transition.md` — Design → Tasks transition, chapter-marker-triggering event.
- `tdd-stage-exclusion.md` — `phase_transition` from `caller: agent-tdd` between TDD-internal
  stages (`red` → `green`); chapter marking must be withheld, unlike `phase-transition.md`.
- `section-checkpoint.md` — a single confirmed requirements section, remaining sections named
  only, open gaps listed.
- `review-threshold.md` — dashboard-opening event; findings summarized without evidence/diff
  text, `artifact_path` present for `agent-ux` to pull from only after threshold confirmation.
- `out-of-scope-flag.md` — a single already-identified, already-confirmed out-of-scope issue.

Structure:

```text
example-envelopes/
  breadcrumb-only.md
  phase-transition.md
  tdd-stage-exclusion.md
  section-checkpoint.md
  review-threshold.md
  out-of-scope-flag.md
```
