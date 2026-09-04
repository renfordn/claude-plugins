# Requirements: agent-ux plugin extraction

## Status

- Phase: Requirements
- State: Draft
- Last Updated: 2026-08-12

## Source Inputs

- Origin: idea (in-conversation exploration, not a filed ticket)
- References:
  - `agent-isdd/agents/ux-agent.md` (extraction source)
  - `agent-isdd/references/ux-conventions.md` (extraction source)
  - `agent-isdd/INTEROP.md` (pattern to mirror for the new plugin's own contract)

## Problem Statement

`ux-agent` (breadcrumb, spec-canvas Artifacts, chapter markers, task chips) currently lives only
inside `agent-isdd`. `agent-tdd` and `code-reviewer` have no shared rendering agent, so they either
go without this UX or would each reimplement a variant of it — duplicating prompt-definition
weight across plugins and risking visual/behavioral drift between them.

## User Outcome

- Consistent breadcrumb / spec-canvas / review-dashboard / chapter-marker UX across agent-isdd,
  agent-tdd, and code-reviewer.
- One place to fix rendering bugs or extend UX conventions, instead of three.
- No plugin pays (in tokens or maintenance) for UX capability it doesn't use, and no plugin is
  hard-blocked if `agent-ux` isn't installed.

## Constraints

- [ ] Soft dependency only — every caller keeps functioning, UI-degraded, if `agent-ux` is absent
      or unreachable, mirroring `agent-nelly`'s existing unavailability contract.
- [ ] Per-event token payload must not exceed today's in-process `ux-agent` call for the
      equivalent event — extraction must not be a net token cost.
- [ ] Preserve existing checkpoint-only gating: no artifact/chapter/task-chip action on ordinary,
      non-checkpoint messages.
- [ ] Cheapest capable model for every caller (currently `haiku`) — no caller's rendering needs
      justify a heavier model based on anything known today.
- [ ] Remains rendering-only: never owns workflow logic, phase decisions, or any caller's
      `TaskCreate`/`TaskUpdate` checklist.

## Non-Goals

- [ ] Redesigning the visual language itself (breadcrumb format, artifact layout) — this is an
      extraction/interop spec, not a UX redesign.
- [ ] A live, cross-session UI sync mechanism — each caller still drives its own render calls.
- [ ] Deciding on agent-tdd's or code-reviewer's behalf whether they adopt this — their
      maintainers' buy-in is outside what agent-isdd's repo can resolve alone.

## Dependencies

- [ ] `agent-isdd`'s existing `agents/ux-agent.md` and `references/ux-conventions.md` as the
      extraction source.
- [ ] Audit of `agent-tdd`'s and `code-reviewer`'s current (if any) UI-rendering logic, to confirm
      the shared event contract actually covers their needs before commit.
- [ ] Caller-side `ccd_session` MCP tools (`mark_chapter`, `spawn_task`, `dismiss_task`) and the
      `Artifact` tool — assumed present on the caller's host session, not on `agent-ux` itself.

## Edge Cases

- [ ] Caller's host session lacks `ccd_session` MCP tools or `Artifact` — already handled today
      ("say so in one line and stop"); must carry over unchanged.
- [ ] Two siblings hand off in quick succession in one session (e.g. agent-isdd → agent-tdd) —
      breadcrumb ownership must transfer cleanly, never double-render or conflict.
- [ ] `agent-ux` not installed at all — caller must have a no-op fallback path, not an error, and
      must surface at most one plain notice per session (not one per event).
- [ ] A caller constructs a full-artifact payload instead of a delta (contract misuse) — the
      interface should make this the wrong shape to build; `agent-ux` should refuse/truncate
      cheaply rather than process it in full.

## Success Criteria

- [ ] All three prospective callers can render breadcrumb/chapter/artifact events through one
      shared agent with no duplicated rendering prompt logic in any of them.
- [ ] Per-call token payload for a given event type is measured equal to or smaller than today's
      in-process `agent-isdd` baseline for the equivalent event.
- [ ] Removing `agent-ux` from an environment leaves every caller functional, degraded only in UI
      richness, never in workflow correctness.

## EARS Requirements

- `Ubiquitous`: When any sibling plugin reaches a declared checkpoint (phase transition,
  section-confirmation, review-pass threshold, out-of-scope flag), the calling skill shall be
  able to delegate rendering to `agent-ux:ux-agent` via a shared, versioned event contract.
- `Event-driven`: When `agent-ux` is not installed or unreachable, the calling skill shall
  continue its workflow without blocking and shall surface at most one plain notice per session.
- `Event-driven`: When a caller delegates a rendering event, the payload shall contain only that
  event's minimal delta fields, never the full spec artifact or full diff body.
- `State-driven`: While a review pass has 5 or fewer findings and touches one file, `agent-ux`
  shall take no Artifact action, mirroring the existing threshold.
- `Optional-feature`: Where a caller's host session lacks the `Artifact` tool or `ccd_session` MCP
  tools, `agent-ux` shall report the missing tool in one line and stop, never blocking the caller.
- `Unwanted-behavior`: If a caller passes a full artifact body instead of a delta, `agent-ux`
  shall refuse or truncate it rather than rendering the full payload, and shall say so in one
  line.

## Open Gaps

- [ ] Exact schema of the event envelope per `event_type` — deferred to Design.
- [ ] Whether `agent-tdd`'s TDD-stage boundaries (red/green/refactor) get their own chapter tier,
      or stay excluded as they are today ("never on a TDD stage boundary") — this guardrail was
      written from `agent-isdd`'s vantage point and needs an explicit decision now that
      `agent-tdd` would be a direct caller.
- [x] Whether `agent-tdd`/`code-reviewer` maintainers actually want this extraction versus
      accepting per-plugin duplication — outside this repo's authority to resolve, so it is
      carried forward as a follow-up item for those maintainers, not as a gap blocking this
      plan (see design.md's Open Questions and tasks.md's "Follow-Up For Sibling Plugins").

## Approval Checkpoint

- [ ] Problem statement is clear
- [ ] User outcome is clear
- [ ] Constraints are clear
- [ ] Non-goals are clear
- [ ] Dependencies are clear
- [ ] Edge cases are clear
- [ ] Success criteria are clear
- [ ] EARS requirements are present
- [x] No unresolved ambiguity remains — three items in Open Gaps are explicitly flagged as
      decisions for Design (schema) or for external maintainers (adoption), not left implicit.

## Phase Completion

- [ ] All required requirement sections are populated
- [ ] Open Gaps contains no blocking unresolved item
- [ ] State can be marked `Approved`
