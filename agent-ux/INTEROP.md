# Interop: agent-ux

This plugin renders progress UI (breadcrumb, spec-canvas Artifacts, review dashboards, chapter
markers, out-of-scope task chips) on behalf of sibling plugins. It owns no workflow logic and no
phase decisions — a caller tells it what happened via a minimal **event envelope**, and it decides
how that renders. This document is the authoritative field/behavior contract for that envelope,
for `agent-ux`'s own maintainers and every caller's maintainers to cross-check. Mirrors the pattern
established by `agent-isdd`'s own `INTEROP.md` (boundary documentation, field mapping tables,
unavailability handling stated explicitly).

## Contract Version

Unversioned — interim policy. Breaking changes (a field renamed, removed, or its type/shape
changed for an existing `event_type`) require updating all known callers in the same change,
rather than shipping a new major version for callers to migrate independently. Additive changes (a
new optional field, a new `event_type`) don't require this — callers that don't send the new
field/type are unaffected.

Defers, not resolves, `design.md`'s Open Question ("should this be semver'd?"). Revisit once a
second caller (`agent-tdd` or `code-reviewer`) adopts this contract — lockstep updates across
three repos stop being tractable at that point, while `agent-isdd` is still the only caller
today.

## → Every caller (event envelope contract)

`agent-ux:ux-agent` is invoked with a single delegation prompt shaped as this envelope. Every
field below is verbatim from `agent-isdd`'s Design phase Data Contracts And Interfaces section
for this extraction, cross-checked against the recorded examples in
`references/example-envelopes/`.

### Envelope shape

| Field | Type | Required | Meaning |
|---|---|---|---|
| `caller` | `agent-isdd \| code-reviewer \| ...` (any orchestrating plugin's own identity) | always | Selects caller-specific rendering rules, when any are defined (see `caller`-keyed rendering rules below). **Never `agent-tdd`**: `agent-TDD` (the subagent) has no `Agent` tool and can never be the literal actor sending this envelope — per `agent-tdd`'s own `INTEROP.md`, only a main-thread orchestrating skill can. An orchestrator rendering an `agent-tdd` slice's progress supplies its own identity here instead; TDD-internal stages are detected from `phase_state`'s shape, not from `caller` (see below). |
| `event_type` | `breadcrumb_only \| phase_transition \| section_checkpoint \| review_threshold \| out_of_scope_flag` | always | Selects which `delta` shape applies and which action family is in play. |
| `phase_state` | string (compact token, e.g. `Design`, `TDD:green`) | always | Current phase for breadcrumb rendering. Never the full `workflow-state.md` or any other state file — a short token only. |
| `delta` | object (event-specific, see below) | always | Event-specific minimal payload. Never a full artifact body, with exactly one named exception (`section_checkpoint`'s `section_body`, below). |
| `artifact_path` | string (stable path) | when applicable per `event_type` | Caller-owned path for `agent-ux` to redeploy to, or to read further from on its own initiative. Never regenerated or invented by `agent-ux`. |

**Outputs**: the breadcrumb line, always, plus one line per action actually taken (artifact
published/redeployed, chapter marked, task spawned/dismissed, "no artifact action — below
threshold", "no artifact tool available", or a named tool failure). `agent-ux` never addresses the
user directly; its output is for the caller to relay verbatim. (Full dispatch logic per
`event_type`: `agents/ux-agent.md`.)

### Pull-over-push invariant

`delta` never contains a full document body, with exactly one stated exception: the single
confirmed section's body in `section_checkpoint` (`section_body`). Everything else `agent-ux`
might need — remaining section text, finding evidence/diff hunks, full artifact contents — it
reads itself via `artifact_path`, using its own `Read` tool, and only once it has decided an
action is actually warranted (e.g. only after confirming `review_threshold`'s dashboard threshold
from `finding_count`/`files_touched`, never before — this ordering is binding, not stylistic).
Callers construct `artifact_path`; they never push the content it points to.

### Per-`event_type` delta shape

Each row is the exact, complete key set for that `event_type` — no additional keys permitted (see
Envelope misuse). Gating/dispatch behavior per type lives in `agents/ux-agent.md`; this table is
the authoritative field shape.

| `event_type` | `delta` keys (exact set) | `artifact_path` | Notes | Fixture |
|---|---|---|---|---|
| `breadcrumb_only` | `{}` | none | Highest-frequency type; must stay cheapest — no fields beyond `phase_state` anywhere in the envelope. | `references/example-envelopes/breadcrumb-only.md` |
| `phase_transition` | `from_phase, to_phase, feature_slug, one_line_summary` | the just-finalized artifact (e.g. design doc), not the one about to be produced — `agent-ux` never regenerates it | No section bodies, findings, or full document text. | `references/example-envelopes/phase-transition.md` |
| `section_checkpoint` | `section_name, section_body, remaining_section_names, open_gaps` | stable spec-canvas path, same every call within a phase | `section_body` is **the single named exception** to "never a full artifact body" in this whole contract; `remaining_section_names` is names only, no bodies; `open_gaps` is short strings, no nested rationale/evidence. | `references/example-envelopes/section-checkpoint.md` |
| `review_threshold` | `finding_count, files_touched, findings` | findings artifact to redeploy the dashboard from/to | `findings` is `{id, title, tier, severity}` objects — no `evidence`/`diff` field on any finding; `agent-ux` reads `artifact_path` for hunks/evidence only once it has independently confirmed the threshold from `finding_count`/`files_touched`, never before. | `references/example-envelopes/review-threshold.md` |
| `out_of_scope_flag` | `title, file_path, context_summary` | none | Unchanged from pre-extraction shape, already minimal; `spawn_task`'s prompt is built from `context_summary` + `file_path` only. Caller has already judged the issue concrete and out of scope before delegating — `agent-ux` never infers that judgment itself. | `references/example-envelopes/out-of-scope-flag.md` |

### Envelope misuse

If a `delta` exceeds the expected shape for its `event_type` (e.g. a full document body where only
`section_body` for one named section is expected), `agent-ux` truncates and reports the mismatch in
one line rather than rendering the oversized payload — a defined failure mode, not undefined
behavior. `agent-ux` withholds the event type's action entirely for a mismatched envelope (full
refusal, not partial execution on the valid field subset) — the whole payload is unverified once
any field violates the contract.

## Unavailability and fallback contract (generic — reference, don't restate)

Every caller of `agent-ux:ux-agent` is a **soft dependency**: `agent-ux` must never become a hard
blocker on a caller's own workflow. This is the one place this policy is defined; each caller's own
`INTEROP.md` should reference it by name rather than restate it.

- Plugin unreachable/not installed: the caller catches the missing-plugin condition, logs **one
  plain notice for the session** (not one per event), and continues without blocking — mirrors
  `agent-nelly`'s unavailability handling in `agent-isdd`'s own `INTEROP.md`.
- A specific rendering tool `agent-ux` depends on (e.g. `Artifact`) is unavailable at call time:
  `agent-ux` itself says so in one line and stops — never blocks the caller's progress on that
  missing tool. Distinct from the caller-side case above; needs no caller-side handling beyond
  relaying the line.
- Neither fallback path is a hard dependency: no caller should gate its own phase progression on
  `agent-ux` (or any tool it uses) being available.

## `caller`-keyed rendering rules

Rules keyed by the envelope's `caller` field, or by structural properties of `phase_state`, live
here — inside `agent-ux`'s own contract — rather than forking into each caller's own skill logic.
Mitigates callers quietly drifting on what a "checkpoint" means. Each entry below was checked
directly against the named plugin's own repo, not assumed from another plugin's notes about it.

- **TDD-internal stage exclusion** (keyed on `phase_state`, not `caller` — see the envelope-shape
  table's note on why `agent-tdd` can never literally be `caller`): `phase_transition` chapter
  marking does not apply when `phase_state` matches the pattern `TDD:<stage>` — only to
  phase-level transitions apply (Requirements/Design/Tasks/Implementation, see Chapter markers
  below). Whoever sends such an envelope is some orchestrating skill rendering an `agent-tdd`
  slice's progress under its own `caller` identity — this rule fires on the `phase_state` shape
  regardless of which orchestrator that is, which is both more correct (no caller can literally
  be `agent-tdd`) and more general (works for any future orchestrator, not just one named here).
  The stage set behind `TDD:<stage>` is `agent-tdd`'s own six stages, read directly from
  `agent-tdd/agents/agent-TDD.md`'s "Required workflow" section: Plan → Red → Green → Review
  (mandatory pause) → Refactor → Validate. **No live sender today** (verified against
  `agent-tdd`'s own repo, commit `34ff282`): no reference to `agent-ux`, `ux-agent`,
  `mark_chapter`, or `phase_transition` anywhere in it, and `agent-TDD` structurally never will
  reference them itself. `agent-tdd`'s own `INTEROP.md` ("Rendering TDD-stage progress with
  agent-ux") now documents the concrete recipe for an orchestrator that wants to send this
  envelope on its behalf.
- **`code-reviewer`**: real, optional integration — see `code-reviewer`'s own `SKILL.md` "Visual
  Review" section and `INTEROP.md`. When `agent-ux:ux-agent` is available, `code-reviewer`
  delegates its review-dashboard rendering to a `review_threshold` envelope (`caller:
  code-reviewer`) instead of opening its Artifact directly; when unavailable, it falls back to
  its own direct-Artifact behavior unchanged. No caller-specific exclusion applies — it follows
  the same `review_threshold` dispatch as `agent-isdd`, using the same 5-finding/1-file threshold
  `code-reviewer` defines as canonical (see `references/ux-conventions.md`'s "Review dashboard
  (Artifact)" section).
- No other rendering rules are defined.

## Chapter markers (general, not caller-specific)

`agent-ux` marks a chapter only on a phase transition (Requirements → Design, Design → Tasks,
Tasks → Implementation, or a workflow restart/rewind) — never on a TDD stage boundary within a
slice (see caller-keyed rule above), and never on a session's first message. Applies regardless of
`caller`.
