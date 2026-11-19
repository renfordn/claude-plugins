---
name: workflow-manager
user-invocable: false
description: "Invoked by /isdd. Resolves workflow state, decides start/continue, repairs stale state, scaffolds artifacts, controls phase transitions."
---

# Workflow Manager

Internal skill behind the `spec-driven-development` workflow (also reached standalone via `/isdd-status`). It owns state resolution, start/continue/pause/handoff/complete decisions, stale-state repair and artifact scaffolding (folded in from the former `artifact-scaffolder`: deterministic bookkeeping, not authoring).

## Input

In decision order: agent-nelly's stored Intent (when the Availability Check finds it), `workflow-state.md`, `workflow-state.json`, unresolved blockers or confirmation checkpoints, phase files (`Status` sections), `recap.md`. Intent outranks the artifacts as a constraint but never encodes phase state; that always comes from `workflow-state.md`/`workflow-state.json`. No inputs at all (no feature folder, no state) is a fresh start: action `start`, route to `before-requirements`.

- **Goal Field.** `workflow-state.md`'s `Goal` is authoritative for this feature, seeded from nelly's Intent at `start` (else ask the user). Every `before-continue` runs an inline Intent Hash alignment check (no nelly spawn); a drift is a `pause`. Full contract: `references/track-and-availability-details.md`.
  Brief cache rules: read `references/goal-and-intent-contract.md` on workflow start and on `before-continue` (`nelly_brief_cache` validity, 24h age).
- **Availability Check.** At `before-requirements` and `before-continue`, look for `agent-nelly:agent-nelly` in the session's agent-types `<system-reminder>` and cache the result as `agent_nelly_available` in `workflow-state.json`;
  unavailable means one plain notice and no Intent check, never a block. A spawn that fails to resolve flips a stale `true` to `false` (self-healing rule: `references/track-and-availability-details.md`).
- **Track.** `Track: Fast | Standard` is set once at Start by `spec-driven-development`; this skill only scaffolds and persists it. Fast means no `tasks/tasks.md` and a Slice Spec handoff.
- **Risk.** `Risk: low | elevated | high` plus `Risk Reason` live in `workflow-state.md`; this skill persists them and never classifies.
  Signals and depth table: `../spec-driven-development/references/risk-depth.md`. `state_guard` denies Track leaving Standard, Fast unless Risk is low (or blank), and any Risk decrease; Risk only rises (guard rules: `references/state-write-responsibilities.md`, "Write guards").
- **Implementation Mode.** `agent` or `user`, asked via `AskUserQuestion` before the spawn and written from the user's answer; question wording and the `isdd-coach` hand-off: `../spec-driven-development/references/implementation-handoff.md`. Never flip it yourself. `state_guard` does not deny a change but logs it in `hook_history`;
  `user_led_guard` enforces `user`.
- **Write responsibilities.** `workflow-state.md` is model-written; mirrored JSON fields (incl. `track`, `risk`, `risk_reason`, `implementation_mode`)
  are written only by `hooks/post_write_check.py`; `approval_hash`/`approval_pending` only by `hooks/approval.py`; the `reviewed` map only by `hooks/review_tracking.py`.   Field-by-field breakdown and the write guards: `references/state-write-responsibilities.md`.

## Scaffolding

Per-feature artifacts are plugin state, never inside the repo: `${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/`. Resolve (and create, if missing) a feature folder with `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --spec-path <YYYY-MM-DD-feature-slug>` rather than hand-building the path.
It also rejects unsafe slugs, and `hooks/memory_permission.py` auto-approves reads/writes there. 
Read `references/scaffolding.md` when you `start` a feature or create/update its folder (directory tree, templates, section order, `workflow-state.json`, `Track`-conditional `tasks.md`).

## Phase Completion Evaluation

Per invocation determine: active feature folder, action (`start`, `continue`, `pause`, `handoff`, `complete`), authoritative current phase, workflow status, pause reason, next action. Evaluate `Requirements`/`Design` against the pass/fail checklists in `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`: a phase passes only when every required item is satisfied, fails when any is unchecked, contradicted or blocked, and is `blocked` when it needs user confirmation, missing information or a resolved contradiction.

## Lifecycle Hooks

This skill defines the field-update contract per hook; whichever thread is executing (the `spec-driven-development` orchestrator, or this skill standalone) performs the write. Every hook allows, updates state and continues, or pauses with a concrete reason, and writes `Last Hook Run`, `Last Hook Outcome`, `Last Hook Decision`, `Hook Notes`.

**Verification Step (every `after-*` hook, and `before-continue`'s own decision)**: before reporting a decision as final, confirm `recap.md` actually changed and a `hook_history` entry exists for it (trust `post_write_check.py`'s drift-repair entry as evidence; otherwise check directly). If the check fails for a claimed state-changing decision, pause rather than advance.

**Nelly write-back (every `after-*` hook, after its Verification Step, only when advancing or handing off)**: if `agent_nelly_available` is `true`, send a `new facts` batch of project-level discoveries (only facts that would benefit a future conversation independently of this feature's own artifacts; ephemeral workflow state never qualifies) or an `error lesson` for an approach tried and rejected this phase (criterion: `INTEROP.md`'s "→ agent-nelly" section). A failed call is a one-line `recap.md` note, never blocking. Read `references/hook-write-back-notes.md` for per-hook "Facts worth persisting" (also at `after-requirements`).

**Plan Board sync (every hook that changes the phase, status, pause reason or next action in `workflow-state.md`: phase transition, pause, resume, rewind, handoff, completion; after the Nelly write-back where that applies, otherwise after the Verification Step; only when this project's memory dir has a `PLAN-BOARD.md` with an `https://` URL)**: rebuild this feature's record and write it to the board.
1. Run `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board.py" doc <workflow-state.md> --project <label> --out <temp file>`
   (it prints the record's `id`; `<label>` = git top-level folder name, main repo's in a worktree).
2. With `url` = the URL in `PLAN-BOARD.md`, `ArtifactData get` that `id` in collection `plans` to see whether the record exists.
3. `ArtifactData set` with `file_path` = the temp file and, when the record already exists, `if_version` = the `version` the `get` returned (a `set` on an existing record is refused without it).
4. Run the same command with `doc` replaced by `mark-synced` and no `--out`.

A failed sync is noted in one line in `recap.md` and never blocks the workflow; `SessionStart` lists any feature still out of date.
The post-write hook also emits this reminder after any write to the feature's state files (workflow-state, requirements, design, tasks, recap, direct-mode-state.json) when the record changed; follow it the same way.
`/isdd-board-sync` repairs drift in bulk. Setup, record fields and turning it off: `references/plan-board.md`.

| Hook | Evaluates / does | Notes |
|---|---|---|
| `before-continue` | Resolve the active feature folder and read `workflow-state.md`; none found routes to `start` (via `before-requirements`). Otherwise: pending rollback request first (`references/rewind-and-rollback.md`, "Rollback Request Intake", takes priority), the inline Intent-alignment check, `nelly_brief_cache` validity (Intent Hash match + under 24h, else clear), detect/repair stale artifacts (`references/state-repair.md`), decide the next action. | No nelly write-back; read-only w.r.t. phase decisions. Update `Intent Alignment Status` (`aligned`/`drift`); clear `nelly_brief_cache` on drift or staleness. |
| `before-requirements` | Ensure artifacts exist (scaffold if not), initialize/repair `workflow-state.md` incl. `Goal`, decide `requirements-agent`'s entry mode (author vs. review), confirm no earlier phase is skipped. | — |
| `after-requirements` | Evaluate the `Requirements` checklist, decide advance-to-Design vs. pause. | Facts worth persisting: interface assumptions confirmed/denied during the interview, constraint conflicts found, non-goals that turned out load-bearing. Read `references/hook-write-back-notes.md` for the write-back rules. |
| `before-design` | Confirm Requirements approved, no blocking gap, no open confirmation checkpoint; enter native plan mode (Native Plan Mode Gate). | — |
| `after-design` | Evaluate the `Design` checklist, decide advance vs. pause. | Read `references/hook-write-back-notes.md` at `after-design` for "Facts worth persisting" (design-gate discoveries only). |
| `after-tasks` | Decide handoff / pause-for-implementation-request / pause-for-blocker on the single trigger "Design is approved and implementation was requested"; on handoff, exit native plan mode before setting `Current Phase: Implementation`. No `Tasks` checklist is evaluated here. | See `references/hook-write-back-notes.md` (`after-tasks` "Facts worth persisting"): the gate hooks involved and what to persist after handoff. |

## Action Rules

| Action | Choose when | On choosing |
|---|---|---|
| `start` | No matching feature folder exists, the user asks for a new workflow, or an existing one shouldn't be reused safely. | Derive the slug, scaffold (incl. `intent/`), capture `Goal` via nelly (if available) or the user, create `intent/intent.md` (Goal + Success Signals + Intent Hash), initialize `workflow-state.md` (Intent Hash + Intent Alignment Status) and `recap.md`, route into `requirements-agent`. |
| `continue` | A matching folder exists, status `In Progress`, active phase not complete. | Read `workflow-state.md`, validate against phase artifacts, repair if stale, evaluate checklists, continue from the earliest incomplete or blocked phase. Read `references/action-rules-detail.md` when `Current Phase: Tasks` (rollback-landing state): a re-implementation handoff, never a return to Requirements or Design authoring; it also holds the Tasks row of Phase Pass/Fail Rules. |
| `pause` | A blocker, required user confirmation, ambiguous feature resolution, a failed phase gate or checklist, or an unresolved Intent-alignment flag from nelly. | Keep `Current Phase`; set `Workflow Status` precisely, `Pause Reason`, and a concrete `Next Action`. |
| `handoff` | Design is approved and implementation was requested, with no unresolved blocker or confirmation open. `tasks.md` does not exist yet: `agent-tdd` produces it inside the same spawn (`INTEROP.md`, "→ agent-tdd"). | Set `Current Phase: Implementation`, `Current Owner: User`, `Workflow Status: In Progress`; ask `Implementation Mode`; `spec-driven-development`'s Implementation Handoff builds the Design Spec with `Parallel: on` (`Track: Standard`; this thread then leads `agent-tdd:tdd-parallel`) or a serial Slice Spec (`Track: Fast`), see `../spec-driven-development/references/implementation-handoff.md`. `design_spec_gate` gates every agent-TDD spawn (Approval gate below). Set `Complete` only once the lead's `all_slices_complete` returns (serial Fast: set Complete after the Slice Spec report), then resync every stale pre-handoff field (`references/action-rules-detail.md`, handoff resync list). |
| `complete` | Planning finished without an implementation request, or implementation is complete with no further phase work. | Set `Workflow Status: Complete`, `Pause Reason: None`, `Next Action: None`; subject to the Complete guard below. |

### Approval gate

Approval in Design is `ExitPlanMode` only; `hooks/approval.py` then records `Implementation Requested: Yes` and `Approval Pending: yes`. `design_spec_gate` runs on every agent-TDD spawn (Design Spec, Slice Spec, parallel workers): it requires requirements.md and design.md `State: Approved`, `Implementation Requested: Yes`, and a matching `Approval Hash` (sha256 over requirements.md + design.md), and records the hash on the first spawn (pending or legacy features). Recovery commands, run only after the user approves via `AskUserQuestion` (the deny text prints them with resolved paths):

- `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" approve "<spec_dir>"`: plan mode unavailable; sets `Implementation Requested` and `Approval Pending`.
- `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" refreeze "<spec_dir>"`: requirements/design changed after approval (hash mismatch); re-freezes the hash.

### Complete guard (R3)

`complete_guard` denies setting `Complete` while required code-reviewer review evidence is missing. Either spawn `code-reviewer` with `Review scope: slice=N`, or ask the user via `AskUserQuestion` and record `- Review Fallback: Accepted via AskUserQuestion: <slice ids | all>: <reason>`. Exact rules, fallback scope and the `stop_check` backstop: `references/state-write-responsibilities.md`, "Write guards".

## Native Plan Mode Gate

Read `references/native-plan-mode.md` before `EnterPlanMode` at `before-design`, while drafting under plan mode, and before `ExitPlanMode`. Summary: Design is drafted in context and the plan file; artifacts are written only after plan approval; `ExitPlanMode` only at handoff (Design approved and implementation requested). Never block phase progress on plan-mode availability; a declined `EnterPlanMode` is a pause.

## Phase Pass/Fail Rules

| Phase | Pass when | Fail when |
|---|---|---|
| Requirements | `Approval Checkpoint` satisfied, required EARS fields present, no unresolved blocking `Open Gaps`, `Phase Completion` satisfied, `State: Approved`. | Any checkpoint item incomplete, EARS requirements missing or weak, or ambiguity remains. |
| Design | `Phase Decision` satisfied, requirement coverage explicit, interfaces/touchpoints grounded in research, validation strategy present, `Phase Completion` satisfied, `State: Approved`. | Any phase decision item incomplete, design contradicts approved requirements, or validation strategy weak or absent. |
| Tasks | Not evaluated by `agent-isdd` (`agent-tdd` slices tasks inside the handoff). Read `references/action-rules-detail.md` (Tasks row). | N/A on agent-isdd's side. |

## State Repair, Rewind and Rollback

`workflow-state.md` is stale when a later phase file or the stored pause reason/next action disagrees with the newest consistent artifacts: staleness heuristics and repair procedure in `references/state-repair.md`. `commands/isdd-rewind.md` delegates rewind mutation here: a rewind names a target phase at or before the current one; a rollback request (from `agent-tdd`/`code-reviewer`, or human-relayed) reopens a `Complete` workflow; a mid-phase idea is classified as an earlier-phase invalidation (rewind) or a current-phase refinement (no change). Full contract, loop prevention and `recap.md` logging: `references/rewind-and-rollback.md`.

## Output

An updated `workflow-state.md` (all sub-sections), `recap.md` and mirrored `workflow-state.json` that agree with the decided action, plus the action, phase, status, pause reason and next action reported to the caller. After each `after-*` hook, summarize the phase into `recap.md` (recap-and-drop: later prompts cite the summary, the full artifact stays on disk, `Open Items` carry forward in full). 

The calling skill renders the breadcrumb and chapter marks (`references/ux-conventions.md`, plugin root); keep the phase checklist in sync with `TaskCreate`/`TaskUpdate`/`TaskList` (self-loaded via `ToolSearch`), as `hooks/post_write_check.py`'s reminder on every `workflow-state.md`/`tasks.md` write backstops.

## Done when

The decided action is reflected everywhere: `workflow-state.md`, `recap.md` and its `hook_history` entry agree (Verification Step passed), nothing is left stale after the routing decision, and the Plan Board is synced where one exists.

## Guardrails

- Do not restart a workflow when continuation is safer, or continue into a later phase when an earlier one is invalidated.
- Do not hand off unless Design is approved, implementation was requested, and no blocker or confirmation is open.
- Do not leave `workflow-state.md` stale after a routing decision, sub-sections included. A recurring failure: `handoff` completes and `Workflow Status` becomes `Complete`, but the `### Tasks` block, `Notes` and `Next Action` keep pre-handoff wording (e.g. `Status: Ready For Implementation` after all slices shipped). Resync the whole file on every completion.
- Do not set `Complete` around `complete_guard`, lower `Risk`, or change `Track` or `Implementation Mode` without the user's say-so.
- Do not skip the Goal-field capture on `start`, or the inline Intent-alignment check on `before-continue` (it runs regardless of nelly availability).
- Do not scaffold a second, divergent folder structure; always the one canonical layout.
