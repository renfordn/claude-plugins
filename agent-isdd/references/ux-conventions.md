# UX Conventions

The calling skill renders these directly on the main thread — one tool call each, no subagent.
(Folded in from the retired `agent-ux` plugin, whose subagent cost ~2K tokens per event to make
the same single call.)

## Breadcrumb

Inline markdown, once, at the top of a phase-transition or status response — never an Artifact:

```
**SDD** Requirements [✓] → Design [▶] → Tasks [·] → Implementation [·]
```

Markers from `workflow-state.md`: `✓` approved, `▶` in progress, `✗` blocked, `·` pending. Once the
Implementation Handoff is made, Implementation is `✓` — TDD-stage progress lives inside `agent-tdd`.

## Chapter markers (`mark_chapter`)

One per phase transition (Requirements → Design → Tasks → Implementation) or restart/rewind,
titled after the phase entered, summary = feature slug + what's starting. Never per TDD stage,
never on a session's first message — a session has a 3–8 chapter budget.

## Phase tick list (`TaskCreate`/`TaskUpdate`/`TaskList`)

Self-load via `ToolSearch` (`select:TaskCreate,TaskUpdate,TaskList`) once per session. One task
per required checklist item in `references/artifact-templates.md` (the markdown checklist is the
source of truth). Check `TaskList` before creating; mark `in_progress` when work starts and
`completed` when satisfied — never batch to the end of a phase.

## Spec canvas (Artifact)

One Artifact per feature, redeployed to the same file path throughout Requirements. Redeploy only
at a section-confirmation checkpoint (a section confirmed or materially changed), not per message.
Render confirmed sections in full, remaining ones as stubs, plus the open-gaps list. No Artifact
tool → skip silently; the inline markdown recap is the fallback.

## Out-of-scope flags (`spawn_task`/`dismiss_task`)

Only for a concrete issue already confirmed out of scope — never a hunch. The prompt must stand
alone (file paths, enough context to act). Dismiss with the returned id if it goes stale.

## Icons

✅ complete · ▸ current · ○ not started · ⚠ needs attention · 🎯 goal-alignment (agent-nelly only).
One or two per message where they aid scanning, never decoration.
