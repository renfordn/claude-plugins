# Internal routing and task tracker sync

Read by `spec-driven-development` for the Internal Routing Rule and Task Tracker Sync (`TaskCreate`) sections whose stubs name this file; text is verbatim from SKILL.md.

## Internal Routing Rule

Use focused skills internally rather than asking the user to switch prompts:
- `workflow-manager` — orchestration, phase detection, state repair, transitions, scaffolding.
- `requirements-agent` — requirements from scratch or from an existing draft/ticket/PRD.
- `design-author` — design, informed by `research-consolidator` and `agent-nelly:agent-nelly`
  (when available).

Only expose these skill names when the user explicitly asks which one is being used, wants to
invoke one directly, or a pause message needs to explain which capability produced the output.

## Task Tracker Sync

`tasks.md` is a repo-persisted planning artifact, distinct from the harness's own task tracker.
Call `TaskCreate`/`TaskUpdate`/`TaskList` directly from this skill at every phase transition
(self-loaded via `ToolSearch` first) — see "Visible Progress" above.
