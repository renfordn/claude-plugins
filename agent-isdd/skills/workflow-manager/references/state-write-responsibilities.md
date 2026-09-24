# `workflow-state.md` Vs `workflow-state.json` — Write Responsibilities

`workflow-state.md` is the model-written file for all phase state. `workflow-state.json` has two
tiers of fields with different owners:

- **Mirrored fields** (`current_phase`, `phase_state`, `pause_reason`,
  `implementation_requested`): written exclusively by `hooks/post_write_check.py` after every
  `workflow-state.md` write — never by the model directly. `workflow-state.md` is always
  authoritative when they disagree.
- **JSON-only fields** (`agent_nelly_available`, `hook_history`, `rollback_pending`,
  `recap_path`, `blocked_fields`, …): written directly by the model or by whichever hook owns
  them (e.g. `subagent_report.py` for `rollback_pending`). The mirror hook never touches these.

On `start`, create both files from the canonical templates; after that, only `workflow-state.md`
needs updating for phase-state changes — the hook handles the rest.

`hooks/post_write_check.py` also mirrors the same four fields into a lightweight
`.sdd-state.json` at the project root on every `workflow-state.md` write, so other tools can
cheaply check current phase without parsing markdown or resolving
`${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/`. Plain field mirror, no `hook_history` of its own; the
memory-dir `workflow-state.json` stays the authoritative, audited copy. Entirely hook-owned —
nothing here needs to write it directly.
