<!-- TDD-SKIP -->
# Agent UX

A standalone rendering-mechanics agent for Claude Code plugins — breadcrumb, spec-canvas
Artifacts, review dashboards, chapter markers, and out-of-scope task chips.

It was extracted from `agent-isdd`'s internal `ux-agent`, the same way `agent-nelly` (memory) and
`agent-tdd` (implementer agents) were already pulled out of that repo. `agent-isdd` is its first
consumer, not its only intended one.

## Scope

This plugin is rendering mechanics only. It never owns workflow logic, phase decisions, or a
caller's `TaskCreate`/`TaskUpdate` checklist — the calling skill decides what happened; this
plugin decides how it looks, and returns a short confirmation for the caller to relay. It never
addresses the user directly.

Sibling plugins consume `agent-ux:ux-agent` via a shared event contract, defined in
[`INTEROP.md`](INTEROP.md) (envelope shape, per-`event_type` delta tables, unavailability
fallback). `agent-isdd` is the one live caller today, verified against its own repo. `INTEROP.md`
also names `agent-tdd` and `code-reviewer` as prospective callers in its `caller` enum, but per
both plugins' own repos, neither currently sends `agent-ux` an event — see `INTEROP.md`'s
"`caller`-keyed rendering rules" section for what's confirmed live versus aspirational.

## Installation

_Installation instructions will be added once the plugin is published to a marketplace._

## Contents

- `agents/ux-agent.md` — the rendering agent (breadcrumb, spec canvas, review dashboard, chapter
  markers, out-of-scope flags).
- `references/ux-conventions.md` — the single place the visual language (icons, thresholds,
  checklist phrasing) is defined for this plugin.
