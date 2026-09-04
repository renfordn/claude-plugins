---
description: Start or continue the spec-driven development workflow for a feature
argument-hint: [feature description, or leave blank to continue]
---

Use the `spec-driven-development` skill to start or continue the SDD workflow.

Feature context from the user (may be blank): $ARGUMENTS

This command does not implement the workflow itself. Delegate entirely to the
`spec-driven-development` skill's Start/Continue Protocols (which resolve state via
`workflow-manager` first) — do not re-derive the phase gates, auto-advance rules, breadcrumb/
checklist sync, or pause conditions here; those contracts own that logic.

The one thing specific to this command: whether to start or continue.

- If the user described a new feature above, or no `spec/<date-slug>/workflow-state.md` exists
  under the project's central SDD memory dir, **start** a new workflow (via `requirements-agent`,
  interviewing immediately when the input is vague) and capture its `Goal` via
  `agent-nelly:nelly-orchestrator` (when available, per the Availability Check).
- Otherwise **continue** from the earliest blocked or incomplete phase, reading
  `workflow-state.md` as the source of truth.
