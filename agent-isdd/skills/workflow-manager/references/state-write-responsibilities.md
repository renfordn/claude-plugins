# `workflow-state.md` Vs `workflow-state.json` — Write Responsibilities

Read by `workflow-manager` when deciding who may write which state field, or which hook guards a write.

`workflow-state.md` is the model-written file for all phase state. `workflow-state.json` has two
tiers of fields with different owners:

- **Mirrored fields** (`current_phase`, `phase_state`, `pause_reason`, `implementation_requested`,
  `track`, `risk`, `risk_reason`, `implementation_mode`): written exclusively by
  `hooks/post_write_check.py` after every `workflow-state.md` write — never by the model directly.
  `workflow-state.md` is always authoritative when they disagree.
- **Hook-owned fields**: `approval_hash` and `approval_pending` are written only by
  `hooks/approval.py` (not mirrored from the markdown); the `reviewed` map (slice id -> true) is
  written only by `hooks/review_tracking.py` (code-reviewer SubagentStop). Never write these by hand.
- **JSON-only fields** (`agent_nelly_available`, `hook_history`, `rollback_pending`,
  `recap_path`, `blocked_fields`, ...): written directly by the model or by whichever hook owns
  them (e.g. `subagent_report.py` for `rollback_pending`). The mirror hook never touches these.
  Every JSON write goes through `sdd_state.update_json` (locked, atomic); never open the file for
  writing directly.

On `start`, create both files from the canonical templates; after that, only `workflow-state.md`
needs updating for phase-state changes — the hook handles the rest. Fields only in `.md`:
`Approval Hash` and `Review Fallback` (`Accepted via AskUserQuestion: <slice ids | all>: <reason>`).

## Write guards (PreToolUse, via `hooks/pre_write_dispatch.py`)

A write to `workflow-state.md` (Write/Edit/MultiEdit) is evaluated on its post-write text:

- `state_guard` denies: `Track` leaving `Standard`; `Track: Fast` while `Risk` is neither blank nor
  `low`; any `Risk` lowered, removed or unrecognised. A change to `Implementation Mode` is not
  denied; it is logged as a `hook_history` entry. Write `Risk: low` with (or before) `Track: Fast`.
- `complete_guard` denies setting `Workflow Status: Complete` (when it was not already Complete) while:
  - a high-risk slice (tasks.md `Risk Tier`) has no `reviewed` entry (recorded only by `review_tracking`,
    at a code-reviewer SubagentStop) and is not named in the Review Fallback; or
  - `Risk: high` and any slice in tasks.md lacks a `reviewed` entry or fallback (with no tasks.md, one
    reviewed entry suffices).
- Review Fallback counts only as `Accepted via AskUserQuestion: <slice ids | all>: <reason>`. Named ids
  waive just those slices; `all` waives everything, and only `all` waives the feature-level `Risk: high` rule.
- Bash writes are not seen by either guard. `hooks/stop_check.py` is the backstop: it blocks the stop
  once per change when a Complete feature has unreviewed high-risk-tier slices (it does not cover the
  feature-level `Risk: high` rule).

## Other hook-owned writes

- `hooks/post_write_check.py` records the `hooks/baseline.py` snapshot (branch, HEAD, dirty files)
  when `Current Phase` first becomes Implementation; `resume_context.py` (UserPromptSubmit) diffs against it.
- `hooks/approval.py` (PostToolUse `ExitPlanMode`) writes `Implementation Requested: Yes` and
  `Approval Pending: yes` on approval during Design; `Approval Hash` (sha256 over requirements.md +
  design.md) is frozen later, by `design_spec_gate` on the first agent-TDD spawn.

`hooks/post_write_check.py` also mirrors the same fields into a lightweight `.sdd-state.json` at
the project root on every `workflow-state.md` write, so other tools can cheaply check current
phase without parsing markdown or resolving `${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/`.
Plain field mirror, no `hook_history` of its own; the memory-dir `workflow-state.json` stays the
authoritative, audited copy. Entirely hook-owned — nothing here needs to write it directly.
