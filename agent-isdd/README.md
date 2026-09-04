# agent-isdd

An intent spec-driven development workflow for Claude Code and Claude Desktop. It owns the
**Planning** side: EARS-based **Requirements** and research-backed **Design**. Task slicing
and implementation are owned by separate sibling plugins:

- **[agent-tdd](https://github.com/renfordn/agent-tdd)** — task slicing (validate research,
  slice into TDD-sized phases, assign Risk Tiers), then strict Red-Green-Refactor TDD execution.
- **[code-reviewer](https://github.com/renfordn/code-reviewer)** — the mandatory review gate,
  invoked by whichever caller drives implementation.
- **[agent-nelly](https://github.com/renfordn/agent-nelly)** — goal-aware memory, briefs,
  cross-feature file-level caching, and cross-project promotion.

`agent-isdd` never drives task slicing, never drives the TDD loop, never invokes the review
gate, and never owns a memory subsystem beyond its own per-feature `spec/` artifacts. It produces
a **Design Spec** at the Design → Implementation boundary and stops.

## Why this plugin exists

`agent-isdd` is the successor to the `sdd` plugin, which originally bundled requirements,
design, tasks, TDD implementation, code review, and memory into a single, oversized plugin.
Implementation, review, and memory were extracted first (`agent-tdd`, `code-reviewer`,
`agent-nelly`); this plugin is the last piece — the planning-only remainder of `sdd`, trimmed of
everything the siblings now own. See `CHANGELOG.md` for the full port/trim/drop breakdown.

## Workflow

Phase-gated, always in order: `Requirements` → `Design` → `Implementation` (task slicing +
Red-Green-Refactor, owned by agent-tdd). Each phase has a hard completion checklist (EARS format,
no unresolved ambiguity, explicit interfaces/touchpoints, research validated) before handoff.
State lives in `~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/`.

**Intent:** Explicit, durable artifact (markdown). Captured at start, hash-validated on resume.
Drives Requirements, grounds Design, referenced by task slices.

**Research:** Unified pass during Design via `research-consolidator` (one pass, dual output for
Design + Tasks). Cached in `research/cache.md`. Agent-tdd reuses cache, skips re-research unless
invalid. Cross-feature file caching via agent-nelly for 70-80% cache hit rate on related features.

## Commands

- `/isdd` — start or continue the workflow for a feature.
- `/isdd-status` — show current phase, status, blockers, next action (read-only).
- `/isdd-continue` — force-continue from the current phase.
- `/isdd-rewind` — rewind to an earlier phase (Requirements | Design).
- `/isdd-init` — first-run onboarding for a new project.
- `/isdd-memory` — view or migrate this project's central memory (redirects to `agent-nelly`).

## Handoff contract

At the end of Design, once Design is approved and implementation is requested, `agent-isdd`
builds a **Design Spec** from `requirements.md`, `design.md`, `research/cache.md`, and
pre-fetched file summaries, then spawns `agent-tdd` for research validation, task slicing,
and implementation. This is a one-directional handoff — `agent-isdd` does not resume or drive
`agent-tdd` past the initial spawn. See `INTEROP.md` for the exact Design Spec contract and
agent-tdd's new responsibilities (research validation, slicing, Ralph Loops).
