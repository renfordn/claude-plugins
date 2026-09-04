---
description: Force-continue the active SDD workflow from its current phase
---

This command does not implement the continue protocol itself. Delegate entirely to the
`spec-driven-development` skill's Continue Protocol (which reads the active feature's
`workflow-state.md` under the project's central SDD memory dir, then resolves state via
`workflow-manager`) — do not re-derive the auto-advance rules, breadcrumb/checklist sync, or
pause conditions here; that contract owns this logic, same as `/isdd`'s continue branch.

Force this to run now even if the caller thinks it already resumed — that's the one thing
specific to this command over plain `/isdd` with no arguments.
