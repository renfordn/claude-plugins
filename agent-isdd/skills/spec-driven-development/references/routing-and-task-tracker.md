# Internal routing and task tracker sync

Read by `spec-driven-development` for the Internal Routing Rule and Task Tracker Sync (`TaskCreate`) sections whose stubs name this file.

## Internal Routing Rule

Use focused skills internally rather than asking the user to switch prompts:
- `workflow-manager` — orchestration, phase detection, state repair, transitions, scaffolding.
- `requirements-agent` — requirements from scratch or from an existing draft/ticket/PRD.
- `design-author` — design, informed by `research-consolidator` and `agent-nelly:agent-nelly`
  (when available).

Only expose these skill names when the user explicitly asks which one is being used, wants to
invoke one directly, or a pause message needs to explain which capability produced the output.

## Task Tracker Sync

`TaskCreate` checklist rules: `references/ux-conventions.md` (plugin root), "Phase tick list".
State-field ownership: `workflow-manager/references/state-write-responsibilities.md`.
