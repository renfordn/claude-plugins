---
description: Show the current SDD workflow phase, status, blockers, and next action (read-only)
---

Report the current spec-driven-development workflow status **without advancing it and without
modifying any files**.

Locate the active feature's `workflow-state.md` under the project's central SDD memory dir's
`spec/<date-slug>/` (resolve the memory dir via `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py"
--path`; use the most recently updated feature folder if several exist). Delegate to
`agent-ux:ux-agent` for the breadcrumb line, then summarize concisely:

- Feature title, slug, and Goal
- Current phase and previous phase
- Workflow status and pause reason
- Next action
- Implementation Requested (yes/no)

If a blocker or confirmation checkpoint is open, state it explicitly and name what would unblock
it. If no workflow-state file exists, say so and suggest `/isdd` to start one.
