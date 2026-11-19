# Track Field Contract, Availability Check & Goal Field — full details

Read by `workflow-manager` for the full Track, Risk, Availability Check and Goal/Intent-alignment rules its SKILL.md summarises.

## Track Field Contract

- Source of truth: `workflow-state.md`'s `Track` field (`Fast | Standard`), mirrored to
  `workflow-state.json`'s `track`. Absent/unset means `Standard` — no migration needed for
  features started before this field existed.
- Set once, at Start, by `spec-driven-development`'s Fast Track classification (see its own
  SKILL.md) — `workflow-manager` never sets or classifies `Track` itself, only scaffolds and
  persists whatever `spec-driven-development` decided, same division of responsibility as the
  `Goal` field.
- Can flip `Fast` → `Standard` mid-flight via the Fast Track escape hatch (`requirements-agent`
  or `design-author` reporting the change is bigger than assumed); never the reverse — a
  workflow that started `Standard` stays `Standard`.
- `Risk: low | elevated | high` (with `Risk Reason`) is separate from `Track`: Track is the spec
  shape, Risk drives depth and review. Classification: `../../spec-driven-development/references/risk-depth.md`.
  `state_guard` denies `Track: Fast` unless `Risk` is `low` (or blank), so a Fast start writes
  `Risk: low` with `Risk Reason` before or together with `Track: Fast`; Risk can only rise.
- `Track: Fast` means no `tasks/tasks.md` is ever scaffolded or written for this feature (see
  Scaffolding in the main SKILL.md) and the Implementation Handoff sends a Slice Spec, not a
  Design Spec — this changes what `spec-driven-development` does at handoff, not anything
  `workflow-manager` itself evaluates in Phase Pass/Fail Rules (Requirements and Design gates are
  identical either way).

## Availability Check — self-healing on a stale cache

**Self-healing on a stale cache (2026-09-16).** The agent-types listing (checked at
`before-requirements` and `before-continue` — see the main SKILL.md's "Availability Check") is a
point-in-time snapshot captured at session start — it can be stale relative to the actual
installed plugin (a plugin updated or removed after this session began still shows its old
state). A hook cannot backstop this: `agent-nelly:agent-nelly` failing to spawn because the type
doesn't actually resolve is a routing failure that occurs before the model's tool call is even
considered an invocation attempt, so no `PreToolUse`/`PostToolUse`/`PostToolUseFailure` hook ever
fires for it (observed, unverified; the backstop hook `hooks/nelly_spawn_failure.py` was removed
after it never fired). The only place that genuinely sees this failure is the calling skill
itself, in the same turn it attempted the spawn — the tool call returns an "Agent type not found" error directly into
this skill's own context. When that happens for `agent-nelly:agent-nelly` specifically,
immediately correct `agent_nelly_available` to `false` in `workflow-state.json` before
proceeding, rather than leaving the stale cached `true` for a later step to trust and fail
against again.

## Goal Field Contract (full)

- Source of truth for this feature's `Goal`: `workflow-state.md`'s own `Goal` field, one line per
  feature, written directly by the SDD workflow. It is seeded from, and alignment-checked against,
  `agent-nelly:agent-nelly`'s stored `Intent` (one line per project; coarser than Goal, expected
  to be consistent with it, not identical).
- On `start`, when the Availability Check found nelly available, call it (`Agent` tool,
  `subagent_type: agent-nelly:agent-nelly`) to read the stored Intent. If more specific than "not
  yet captured", seed `Goal` from it; otherwise ask the user. If unavailable, always ask the user.
- On every `before-continue`, run the Intent-alignment check inline (no nelly spawn):
  1. Read Intent Hash from `workflow-state.md` (stored at start).
  2. Read the current Intent Hash from session context (the `Intent: <text>` line surfaced at
     session start, or `intent/intent.md` if the session is new).
  3. Hashes match: `Intent Alignment Status = aligned`, no pause.
  4. Hashes differ: `Intent Alignment Status = drift`; pause with reason "Intent has changed;
     review and confirm direction".
  5. No Intent available: skip the check (graceful degradation).
  A clear divergence is pause-worthy, not something to note and continue past.
- `workflow-state.md`'s `Goal` stays authoritative once seeded; Intent is a coarser alignment
  signal, not a value to repair `workflow-state.md` against on every disagreement.
- Brief cache rules (`nelly_brief_cache`): `goal-and-intent-contract.md`.
