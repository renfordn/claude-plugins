# UX Conventions

Owned and read by `agents/ux-agent.md` for the breadcrumb, Artifacts, chapter markers, and
out-of-scope flags. This is the single place visual language is defined for the whole plugin —
no skill should invent its own icon set, checklist phrasing, or "is this worth an Artifact"
threshold.

The phase `TaskCreate` checklist is the one exception: it is **not** delegated to `ux-agent`
(deferred tools including `ToolSearch` are not reachable from an isolated subagent context in
this harness — confirmed via live re-test, 2026-07-30). `spec-driven-development`/
`workflow-manager` calls `TaskCreate`/`TaskUpdate`/`TaskList` directly from the main thread for
phase checklists, self-loading them via `ToolSearch` first since they're deferred tools there
too. The conventions below still apply; only the caller changed. TDD-slice checklist tracking
(the `planning`/`red`/`green`/`review`/`refactor`/`commit_check` stages) is out of scope for
this plugin — that lives entirely inside `agent-tdd` after the Implementation Handoff.

Two UI features are deliberately **not** here: native plan mode (`EnterPlanMode`/`ExitPlanMode`,
owned by `workflow-manager`/`spec-driven-development`) and design-phase diagrams (`show_widget`,
owned by `design-author`). Both are called directly by user-facing skills rather than delegated
to `ux-agent`, which never talks to the user and only renders progress state, not one-off
approvals or explanatory visuals.

## Breadcrumb

One line, always plain markdown (never an Artifact — it must be free to render every turn):

```
Requirements ▸ **Design** ▸ Tasks ▸ Implementation
```

- Phases always appear in this fixed order, regardless of which are complete.
- The current phase is the only one in bold.
- Once the Implementation Handoff has been made, render `Implementation` as complete
  (`Requirements ▸ Design ▸ Tasks ▸ **Implementation**`, no stage detail) — this plugin does not
  track TDD-stage progress after the handoff; that visibility lives inside `agent-tdd`.
- Never redraw the breadcrumb mid-explanation — only at the top of a phase-transition or
  status response, and only once per response.

## Phase tick list (`TaskCreate`/`TaskUpdate`) — driven by the calling skill, not `ux-agent`

- One harness task per required checklist item for the phase (see each phase's checklist in
  `references/artifact-templates.md` — the markdown checklist is the source of truth; the task
  list is a rendering of it, never a second definition of what "done" means).
- Mark a task `in_progress` the moment its checklist item starts being worked, `completed` the
  moment it's satisfied — never batch updates to the end of a phase.
- Do not recreate tasks that already exist for the current phase on every turn; check
  `TaskList` first (per its own guidance) and update in place.

## Spec canvas (Artifact)

- One Artifact per feature, redeployed to the same file path across the whole Requirements
  phase — never a new Artifact per section.
- Redeploy only at a **section-confirmation checkpoint**: the user has confirmed or the draft
  has materially changed for one of problem statement, user outcome, constraints, non-goals,
  dependencies, edge cases, success criteria, or the EARS requirements block. A single
  clarifying answer that doesn't change a section's content is not a checkpoint.
- Content: the sections confirmed so far rendered in full, remaining sections shown as
  placeholders/greyed stubs, and the open-gaps list — so the user visibly watches the spec
  fill in rather than reading a diff.
- If the host has no Artifact tool available, skip it silently and rely on the inline markdown
  recap already required by `requirements-agent` — never block on Artifact availability.

## Review dashboard (Artifact)

Rendered via the `review_threshold` event (see `agents/ux-agent.md`) for any caller reporting
review findings — `caller: agent-isdd | agent-tdd | code-reviewer` per `../INTEROP.md`. Not
`doc-consistency-auditor`: that skill's own `SKILL.md` ("Visual Review — deliberate override of
code-reviewer's threshold") explicitly opts out of this dashboard and uses `ReportFindings` only,
always, regardless of finding count — it reuses `code-reviewer`'s Evidence Tier Model and
Decision Model for its findings' shape, but not this rendering path. No caller in this ecosystem
currently sends a live `review_threshold` event to `ux-agent` (`code-reviewer` opens its own
Artifact directly today — see below); this section defines the rendering agent-ux would use if
one did.

- Default to `ReportFindings` alone — cheapest, host-native rendering, no HTML to author.
- Open a redeployable Artifact review dashboard in addition, only when the pass has **more than
  5 findings, or touches more than one file**. Below that threshold, `ReportFindings` alone is
  enough visual structure and opening an Artifact would just add token cost for no benefit.
  **This threshold is not this plugin's own choice** — it's kept identical to `code-reviewer`'s
  own threshold (`code-reviewer/skills/code-reviewer/SKILL.md`'s "Visual Review" section, the
  canonical definition), since `code-reviewer` is the one caller most likely to eventually adopt
  this event. If that value changes, update it here to match.
- When opened: render each finding as its own resolvable card (id, title, tier, decision,
  severity, category, evidence) alongside the relevant diff hunk, with a visible resolved/open
  state. Redeploy the same Artifact in place as findings are resolved through conversation —
  never repost the whole dashboard as new chat content.

## Chapter markers (`mark_chapter`)

- One chapter per **phase transition** (Requirements → Design → Tasks → Implementation) or a
  restart/rewind — never per TDD stage boundary, never on a session's first message.
- Title after the phase being entered; keep the summary to the feature slug plus what's
  starting. Six chapters per slice (one per TDD stage) would blow past a normal session's
  3-8-chapter budget, so slice-internal stage changes stay on the `TaskCreate` checklist only.

## Out-of-scope flags (`spawn_task`/`dismiss_task`)

- Only for a concrete, already-identified issue the calling skill has confirmed is out of scope
  for the current phase — a deferred `doc-consistency-auditor` finding below the review-dashboard
  threshold, dead code or stale docs noticed in passing, a confirmed TODO.
- Never spawned from a vague hunch — that call is the calling skill's to make before delegating;
  `ux-agent` does not infer confidence on its own.
- The `spawn_task` prompt must stand alone (file paths, enough context to act without the
  conversation) — taken from what the caller supplies, never invented.
- If a caller later reports a flagged item is stale, superseded, or already handled, dismiss it
  via `dismiss_task` using the id the caller was given.

## Icon set (for prose/status lines, not the plugin's marketplace icon)

| Meaning | Glyph |
|---|---|
| Complete / passed | ✅ |
| Current / in progress | ▸ |
| Not started | ○ |
| Blocked / needs attention | ⚠ |
| Goal-alignment flag | 🎯 (used only by `agent-nelly:nelly-orchestrator`'s alignment check, nowhere else — keep it a distinctive, rare signal) |

Use these sparingly — one or two per message where they add real scan-ability, never as
decoration.
