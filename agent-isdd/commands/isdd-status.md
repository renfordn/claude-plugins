---
description: Show the current SDD workflow phase, status, blockers, and next action (read-only)
---

Report the current spec-driven-development workflow status **without advancing it and without
modifying any files**.

Locate the active feature's `workflow-state.md` under the project's central SDD memory dir's
`spec/<date-slug>/` (resolve the memory dir via `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py"
--path`; use the most recently updated feature folder if several exist). Render the
breadcrumb line inline (see `references/ux-conventions.md`), then summarize concisely:

- Feature title, slug, and Goal
- Track (Fast or Standard — Standard if the field is absent) and, for Fast, that no `tasks.md`
  will be produced
- Current phase and previous phase
- Workflow status and pause reason
- Next action
- Implementation Requested (yes/no)

If a blocker or confirmation checkpoint is open, state it explicitly and name what would unblock
it. If no workflow-state file exists, say so and suggest `/isdd` to start one.
