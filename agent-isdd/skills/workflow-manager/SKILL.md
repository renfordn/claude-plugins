---
name: workflow-manager
description: "[Internal — use /isdd instead] Resolves workflow state, decides start/continue, repairs stale state, scaffolds artifacts, controls phase transitions."
---

# Workflow Manager

## Purpose

Use this skill internally whenever the SDD workflow needs to: start a new feature workflow
(including scaffolding its folder structure), continue an existing one, infer the active phase,
decide whether to auto-advance or pause, repair stale or contradictory workflow artifacts, or
hand off to implementation.

Not the main user-facing prompt — it exists to make the top-level `spec-driven-development`
workflow reliable. Also folds in the former `artifact-scaffolder` skill: folder/file scaffolding
is deterministic bookkeeping, the same category of work as state resolution, not creative
authoring, so there's no reason to route to a second skill for it.

## Inputs (Decision Order)

1. `agent-nelly:agent-nelly`'s stored Intent (via the Availability Check gate — see "Goal
   Field Contract" below)
2. `workflow-state.md`
3. `workflow-state.json`
4. unresolved blockers or confirmation checkpoints
5. phase files (`Status` sections)
6. `recap.md`

When available, agent-nelly's Intent outranks all workflow artifacts: cross-project facts and the
project's Intent constrain how every lower-priority input is interpreted, but it never itself
encodes phase/stage state — that always comes from `workflow-state.md`/`workflow-state.json`.
When unavailable (per the Availability Check), skip this input entirely and start resolution from
`workflow-state.md`.

**Missing state:** If none of these inputs exist (no feature folder, no workflow-state.md,
no prior artifacts), this is a fresh-start condition — determine the action as `start` and
route to `before-requirements` (see "Action Rules" and "Start Protocol").

### Goal Field Contract

- Source of truth for this feature's `Goal`: `workflow-state.md`'s own `Goal` field, one line per
  feature — sdd owns and writes it directly.
- Seeded from, and alignment-checked against, `agent-nelly:agent-nelly`'s stored `Intent`
  — one line per *project*, not per-feature . Intent is
  coarser-grained: it captures what the project is for, Goal what this specific feature is for —
  expected to be consistent with, not identical to, the project's Intent.
- On `start`, if the Availability Check (below) found `agent-nelly:agent-nelly` available,
  call it (`Agent` tool, `subagent_type: agent-nelly:agent-nelly`) to read the stored
  Intent. If more specific than "not yet captured," seed the new `workflow-state.md`'s `Goal`
  field from it; otherwise ask the user (a feature's Goal isn't always identical to its problem
  statement). If unavailable, always ask the user — there's no Intent to seed from.
- On every `before-continue`, perform an Intent-alignment check **inline** — do not spawn
  `agent-nelly:agent-nelly` for this. **[Phase 1.1]** The check compares Intent Hash
  from `workflow-state.md` against session context:
  1. Get Intent Hash from `workflow-state.md` (stored at start)
  2. Get current Intent Hash from session context (from `Intent: <text>` line surfaced at session start by `nelly_session_start.py`, or from `intent/intent.md` if session is new)
  3. If hashes match: `Intent Alignment Status = aligned`, no pause
  4. If hashes differ: `Intent Alignment Status = drift`, pause with reason "Intent has changed; review and confirm direction"
  5. If no Intent available: skip check (graceful degradation)

  If a clear divergence is detected, it is pause-worthy (see `pause` in Action Rules), not
  something to note and continue past.
- `workflow-state.md`'s `Goal` field is authoritative for this feature once seeded — the
  project's Intent is a coarser alignment signal, not a value to repair `workflow-state.md`
  against on every disagreement.
- **[Phase 1.2] Brief cache management:** Read `references/goal-and-intent-contract.md` on workflow start and on
  `before-continue` for the `nelly_brief_cache` validity rules (Intent Hash match, 24h age, drift clears it) and which nelly
  calls sit outside the in-session brief-reuse pool.

### Track Field Contract

`Track: Fast | Standard` is set once at Start by `spec-driven-development`'s Fast Track
classification and never set or classified by this skill itself — only scaffolded and persisted.
`Track: Fast` means no `tasks/tasks.md` is ever produced and the Implementation Handoff sends a
Slice Spec instead of a Design Spec. See `references/track-and-availability-details.md` for the
full contract, including the mid-flight escape hatch back to `Standard`.

### Availability Check

- At `before-requirements` (workflow start) and `before-continue` (workflow resume), check the
  session's agent-types listing — the `<system-reminder>` block enumerating "Available agent
  types for the Agent tool" — for the string `agent-nelly:agent-nelly`.
- Cache the boolean in `workflow-state.json`'s `agent_nelly_available` field so later steps in
  the same hook (and later hooks) don't need to re-inspect the listing.
- If unavailable, surface one plain notice to the user and continue without the Intent-alignment
  check — graceful degradation, never a blocking condition.

See `references/track-and-availability-details.md` for the self-healing rule that corrects a
stale cached `true` when a spawn attempt reveals `agent-nelly:agent-nelly` no longer actually
resolves.

### `workflow-state.md` Vs `workflow-state.json` — Write Responsibilities

`workflow-state.md` is the model-written file for all phase state; `workflow-state.json` splits
into mirrored fields (written only by `hooks/post_write_check.py`) and JSON-only fields (written
directly by the model or their owning hook). See `references/state-write-responsibilities.md`
for the full field-by-field breakdown.

## Scaffolding (folded from the former `artifact-scaffolder` skill)

Per-feature artifacts are plugin-generated state, not source — they live under the project's
central SDD memory directory (`${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/`), never inside the repo.
Resolve (and create, if missing) a feature's folder with
`CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --spec-path <YYYY-MM-DD-feature-slug>`
rather than hand-building the path — this also rejects unsafe slugs. Reads/writes under the
memory directory are auto-approved by `hooks/memory_permission.py`.

Read `references/scaffolding.md` when you `start` a feature or create/update its folder: directory tree and scaffold
rules (templates, section order, `workflow-state.json`, `Track`-conditional `tasks.md`).

## Phase Completion Evaluation

For every invocation, determine: active feature folder, requested action (`start`, `continue`,
`pause`, `handoff`, `complete`), authoritative current phase, workflow status, pause reason if
any, next action — see "Action Rules" below for how each is chosen.

Evaluate `Requirements`/`Design`/`Tasks` completion against the explicit pass/fail checklists in
`${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md`, not broad narrative judgment (see "Phase Pass/Fail Rules"
below for the per-phase criteria). A phase passes only when every required item is satisfied,
fails when any required item is unchecked, contradicted, or blocked, and is `blocked` when
completion depends on user confirmation, missing information, or unresolved contradictions.

## Lifecycle Hooks

Ownership note: this skill defines the field-update contract below — which fields change and to
what values, at each hook. It does not claim to be the sole actor performing the write: whichever
thread is currently executing (the top-level `spec-driven-development` orchestrator mid-workflow,
or `workflow-manager` itself when invoked standalone, e.g. via `/isdd-status`) performs the actual
file write, using this contract. `spec-driven-development`'s own references to updating
`workflow-state.md`/`recap.md` mean "per this contract," not a separate, competing set of rules.

Model enforcement through workflow lifecycle hooks, not plugin manifest hooks. Each hook must
allow, update state and continue, or pause with a concrete reason, and writes `Last Hook Run`,
`Last Hook Outcome`, `Last Hook Decision`, `Hook Notes` — table entries below state only what's
additional to that baseline.

**Verification Step (every `after-*` hook, and `before-continue`'s own decision)**: before
reporting the hook's decision as final, confirm `recap.md` actually changed and a `hook_history`
entry exists for it — if `post_write_check.py` already repaired drift for this write (see its
`hook_history` entry), trust that as evidence rather than re-deriving it; otherwise check
directly. Only the hook itself can judge whether `recap.md`'s content is meaningful, not just
present. If the check fails for a claimed state-changing decision, pause rather than advance.

**Nelly write-back (every `after-*` hook, after its Verification Step, only when advancing or handing off)**: if
`agent_nelly_available` is `true`, send a `new facts` batch of project-level discoveries — only facts that would benefit a
future conversation independently of this feature's own artifacts; ephemeral workflow state never qualifies — or an `error lesson`
for a specific approach tried and rejected this phase (criterion: `INTEROP.md`'s "→ agent-nelly" section). A failed call is a one-line
`recap.md` note, never blocking. Read `references/hook-write-back-notes.md` for per-hook "Facts worth persisting" (also at `after-requirements`).

**Plan Board sync (every hook that changes the phase, status, pause reason or next action in
`workflow-state.md`: phase transition, pause, resume, rewind, handoff, completion; after the Nelly
write-back where that write-back applies, otherwise after the Verification Step; only when this
project's memory dir has a `PLAN-BOARD.md` with an `https://` URL)**: rebuild this feature's
record and write it to the board so the living page stays current. Run
`CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board.py" doc <workflow-state.md> --project <git top-level folder name> --out <temp file>`
(it prints the record's `id`). With `url` = the URL in `PLAN-BOARD.md`, `ArtifactData get` that `id`
in collection `plans` to see whether the record exists, then `ArtifactData set` with `file_path` =
the temp file and, when the record already exists, `if_version` = the `version` the `get` returned
(a `set` on an existing record is refused without it). Then run the same command with `doc`
replaced by `mark-synced` and no `--out`. A failed sync is noted in one line in `recap.md` and
never blocks the workflow; `SessionStart` lists any feature still out of date. The post-write hook
also emits this reminder after any write to the feature's state files (workflow-state, requirements,
design, tasks, recap, direct-mode-state.json) when the record changed; follow it the same way. `/isdd-board-sync` repairs
drift in bulk. Setup, the record fields and how to turn it off are in `references/plan-board.md`.

| Hook | Evaluates / does | Notes |
|---|---|---|
| `before-continue` | Attempt to resolve the active feature folder and read `workflow-state.md`. If no existing workflow state is found, route to `start` (via `before-requirements`). If state exists: check for pending rollback request first (see `references/rewind-and-rollback.md`'s "Rollback Request Intake" — takes priority over everything else here), **[Phase 1.1]** perform the inline Intent-alignment check (Goal Field Contract; no nelly spawn; compare Intent Hash from session context against workflow-state.md's stored hash for drift), **[Phase 1.2]** check cached nelly brief validity (Intent Hash match + timestamp < 24h; if invalid, clear cache), detect/repair stale or contradictory artifacts (see `references/state-repair.md`), decide the next action. | No nelly write-back at this hook — read-only w.r.t. phase decisions. **[Phase 1.1]** Update `Intent Alignment Status` to `aligned` or `drift` based on hash check. **[Phase 1.2]** Clear `nelly_brief_cache` if Intent drift detected or timestamp stale. |
| `before-requirements` | Ensure artifacts exist (scaffold if not), initialize/repair `workflow-state.md` incl. its `Goal` field (seeded via `agent-nelly:agent-nelly` if available), decide `requirements-agent`'s entry mode (author vs. review), confirm no invalid earlier phase is skipped. | — |
| `after-requirements` | Evaluate the `Requirements` checklist, decide advance-to-Design vs. pause. | Facts worth persisting: interface assumptions confirmed/denied during the interview, constraint conflicts found, non-goals that turned out load-bearing. |
| `before-design` | Confirm Requirements approved, no blocking gap remains, no confirmation checkpoint open, enter native plan mode (see "Native Plan Mode Gate"). | — |
| `after-design` | Evaluate the `Design` checklist, decide advance-to-Tasks vs. pause. | Read `references/hook-write-back-notes.md` at `after-design` for the "Facts worth persisting" rules (persist only design-gate discoveries; file summaries were already persisted). |
| `after-tasks` | Decide handoff / pause-for-implementation-request / pause-for-blocker on the single trigger "Design is approved and implementation was requested"; if handing off, exit native plan mode before setting `Current Phase: Implementation`. No `Tasks` checklist is evaluated here (full text: `references/hook-write-back-notes.md`). | See `references/hook-write-back-notes.md` (`after-tasks` "Facts worth persisting"): the gate hooks involved and what to persist after handoff. |

## Recap-and-Drop

Once a phase's completion checklist passes (`after-requirements`, `after-design`, `after-tasks`),
summarize the phase into `recap.md`; for the rest of the session, subsequent prompts reference
that summary by default rather than re-quoting the full prior-phase artifact body. The full
artifact always stays on disk under the feature's `spec/` folder and remains re-readable on
demand — this rule governs default prompt construction only, never access. `recap.md`'s
`Open Items` section still carries every unresolved question/debt/risk/security/improvement flag
forward in full; summarizing never means silently dropping an open item.

## Action Rules

| Action | Choose when | On choosing |
|---|---|---|
| `start` | No matching feature folder exists, the user explicitly asks to start a new workflow, or an existing one shouldn't be reused safely. | Derive the slug, scaffold the structure (including `intent/` directory), capture the Goal via `agent-nelly:agent-nelly` (if available, per the Availability Check) or by asking the user, create `intent/intent.md` with Goal + Success Signals + Intent Hash, initialize `workflow-state.md` (with Intent Hash + Intent Alignment Status) and `recap.md`, route into `requirements-agent`. |
| `continue` | A matching feature folder exists, status is `In Progress`, active phase not complete. | Read `workflow-state.md`, validate against phase artifacts, repair if stale, evaluate completion checklists, continue from the earliest incomplete or blocked phase. Read `references/action-rules-detail.md` when `Current Phase: Tasks` (rollback-landing state): it is a re-implementation handoff, never a return to Requirements or Design authoring; the reference also holds the Tasks row of Phase Pass/Fail Rules. |
| `pause` | A blocker exists, user confirmation is required, active feature resolution is ambiguous, a phase gate fails, any completion checklist fails, or (when available) `agent-nelly:agent-nelly` raises an unresolved Intent-alignment flag. | Keep `Current Phase` unchanged; set `Workflow Status` precisely, `Pause Reason`, and a concrete `Next Action`. |
| `handoff` | **Corrected 2026-09-24**: Design is approved and implementation was requested, with no unresolved blockers or confirmation checkpoints remaining. Per Phase 2+3 there is no separate agent-isdd-evaluated `Tasks` checklist to pass first — this is the same trigger `spec-driven-development`'s Implementation Handoff section spawns on; `tasks.md` doesn't exist yet at this point, since `agent-tdd` produces it (and gates its own Readiness Check) inside the same spawn — see `INTEROP.md`'s "→ agent-tdd" section. | Set `Current Phase: Implementation`, `Current Owner: User`, `Workflow Status: In Progress`; let `spec-driven-development`'s "Implementation Handoff" step build the Design Spec (`Track: Standard`) or Slice Spec (`Track: Fast`) and spawn `agent-tdd:agent-TDD` — a single, one-directional handoff (see `INTEROP.md`). Once that spawn returns, set `Workflow Status: Complete` and resync every stale pre-handoff field (`references/action-rules-detail.md`, handoff resync list). |
| `complete` | Planning finished without an implementation request, or implementation is complete with no further phase work. | Set `Workflow Status: Complete`, `Pause Reason: None`, `Next Action: None`. |

## Native Plan Mode Gate

Read `references/native-plan-mode.md` before `EnterPlanMode` at `before-design`, while drafting under plan mode, and before
`ExitPlanMode`. Summary: Design is drafted in context and the plan file; artifacts are written only after plan approval; `ExitPlanMode` only at handoff (Design approved and implementation requested). Never block phase progress on
plan-mode availability; a declined `EnterPlanMode` is a pause.

## Phase Pass/Fail Rules

| Phase | Pass when | Fail when |
|---|---|---|
| Requirements | `Approval Checkpoint` fully satisfied, required EARS fields present, `Open Gaps` has no unresolved blocking item, `Phase Completion` fully satisfied, `State: Approved`. | Any checkpoint item incomplete, EARS requirements missing or materially weak, or unresolved ambiguity remains. |
| Design | `Phase Decision` fully satisfied, requirement coverage explicit, interfaces/touchpoints grounded in research (design-author's Research First rule), validation strategy present, `Phase Completion` fully satisfied, `State: Approved`. | Any phase decision item incomplete, design contradicts approved requirements, or validation strategy weak or absent. |
| Tasks | Not evaluated by `agent-isdd` (`agent-tdd` slices tasks inside the handoff). Read `references/action-rules-detail.md` (Tasks row). | N/A on agent-isdd's side. |

## State Repair Rules

Treat `workflow-state.md` as stale when a later phase file or the stored pause reason/next action
disagrees with the newest internally consistent artifacts — see `references/state-repair.md` for
the full staleness heuristics and repair procedure.

## Rewind Contract, Rollback Request Intake, Mid-Phase Change Classification

`commands/isdd-rewind.md` delegates all rewind state-mutation logic here. A rewind request names
a target phase (`Requirements`, `Design`, or `Tasks`) at or before the current phase; a rollback
request (from `agent-tdd`/`code-reviewer`, or human-relayed) reopens a `Complete` workflow at a
target phase; a mid-phase idea gets classified as either an earlier-phase invalidation (rewind)
or a current-phase refinement (no phase change) before reacting. See
`references/rewind-and-rollback.md` for the full contract, including loop prevention and the
distinct `recap.md` logging conventions for a rollback vs. a routine rewind.

## Task Tracker Sync

The breadcrumb and chapter marks are rendered by the calling skill (see
`spec-driven-development`'s Visible Progress section). Call `TaskCreate`/`TaskUpdate`/`TaskList`
directly, self-loaded via `ToolSearch` first.
`hooks/post_write_check.py` fires a reminder on every `workflow-state.md`/`tasks.md` write as a
backstop — on that reminder, sync the checklist directly.

## Guardrails

- Do not restart a workflow when continuation is safer.
- Do not continue into a later phase when an earlier phase is invalidated.
- Do not hand off unless Design is approved, implementation was requested, and no blocker or
  confirmation is open.
- Do not leave `workflow-state.md` stale after a routing decision — this includes every
  sub-section, not just the top-level `Workflow Status`. A recurring failure mode: `handoff`
  completes and `Workflow Status` gets set to `Complete`, but the `### Tasks` phase-state block,
  `Notes`, and `Next Action` are left at their pre-handoff wording (e.g. `Status: Ready For
  Implementation` and "N slices to be defined" surviving after all N slices actually shipped).
  Treat the whole file as needing resync on every completion, not just its headline field.
- Do not skip the Goal-field capture on `start` (requires nelly when available).
- Do not skip the inline Intent-alignment check on `before-continue` — it runs regardless of
  nelly availability (no nelly spawn needed; see Goal Field Contract).
- Do not scaffold a second, divergent folder structure — always the one canonical layout above.
