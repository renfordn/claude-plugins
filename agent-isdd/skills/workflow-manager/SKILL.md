---
name: workflow-manager
description: "[Internal — use /isdd instead] Resolves workflow state, decides start/continue, repairs stale state, scaffolds artifacts, and controls phase transitions through Requirements/Design/Tasks/handoff."
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
  — one line per *project*, not per-feature (see design.md's "Intent → Goal Mapping"). Intent is
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
- **[Phase 1.2] Brief cache management:** On workflow start, fetch fresh nelly brief and cache
  it in `workflow-state.json` → `nelly_brief_cache` with structure: `{brief_text, fetched_at,
  intent_hash, valid}`. On workflow resume (`before-continue`), check cache validity:
  - If Intent Hash matches && timestamp < 24h old: reuse cached brief (no fetch)
  - If Intent Hash differs || timestamp stale: clear cache, fetch fresh brief, update cache
  - If Intent drift detected: clear cache immediately
- Both nelly calls above (`start`-time Goal-seeding, and the inline `before-continue` check,
  which spawns no subagent at all) are outside the in-session brief-reuse dedup pool described in
  `spec-driven-development`'s Goal-Aware Memory section — neither is ever satisfied by reusing a
  cached brief (persistent cache is OK; in-session context cache is different).

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
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --spec-path <YYYY-MM-DD-feature-slug>`
rather than hand-building the path — this also rejects unsafe slugs. Reads/writes under the
memory directory are auto-approved by `hooks/memory_permission.py`.

On `start`, create the per-feature structure; on later phases, update files in place:

```text
<sdd-memory-dir>/
  spec/
    <YYYY-MM-DD-feature-slug>/
      workflow-state.md
      workflow-state.json
      requirements/requirements.md
      design/design.md
      tasks/tasks.md       # Track: Standard only -- never written for Track: Fast
      recap/recap.md
```

Rules: one feature folder per feature, named with local start date plus slug; use the exact
template bodies from `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md` (search for
`references/artifact-templates.md` if that path does not resolve) and
`${CLAUDE_PLUGIN_ROOT}/references/workflow-state.template.json`; preserve section order so later
agents can rely on stable parsing; `workflow-state.json` is scaffolded together with
`workflow-state.md` every time the latter is created or updated (field schema in
`${CLAUDE_PLUGIN_ROOT}/references/workflow-state.template.json`).
The `tasks/` folder itself can still be created up front alongside the others (cheap, keeps
scaffolding uniform); only `tasks.md` inside it is conditional on `Track`.

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

**Nelly write-back (every `after-*` hook, after its Verification Step, only when advancing or
handing off)**: if `agent_nelly_available` is `true`, call `agent-nelly:agent-nelly` with a
`new facts` batch of project-level discoveries from this phase — only facts that would benefit a
future conversation independently of this feature's own artifacts; ephemeral workflow state never
qualifies. If a discovery instead describes a specific approach tried and rejected this phase (not
just a fact about the current state), call `error lesson` instead of folding it into `new facts` —
see `INTEROP.md`'s "→ agent-nelly" section for the full fact-vs-error-lesson criterion. If the
call fails, append a one-line note to `recap.md` and continue — never a blocking condition. The
table's "Facts worth persisting" column states what's specific to each hook and what an earlier
write-back already covers (do not duplicate).

| Hook | Evaluates / does | Notes |
|---|---|---|
| `before-continue` | Attempt to resolve the active feature folder and read `workflow-state.md`. If no existing workflow state is found, route to `start` (via `before-requirements`). If state exists: check for pending rollback request first (see `references/rewind-and-rollback.md`'s "Rollback Request Intake" — takes priority over everything else here), **[Phase 1.1]** perform the inline Intent-alignment check (Goal Field Contract; no nelly spawn; compare Intent Hash from session context against workflow-state.md's stored hash for drift), **[Phase 1.2]** check cached nelly brief validity (Intent Hash match + timestamp < 24h; if invalid, clear cache), detect/repair stale or contradictory artifacts (see `references/state-repair.md`), decide the next action. | No nelly write-back at this hook — read-only w.r.t. phase decisions. **[Phase 1.1]** Update `Intent Alignment Status` to `aligned` or `drift` based on hash check. **[Phase 1.2]** Clear `nelly_brief_cache` if Intent drift detected or timestamp stale. |
| `before-requirements` | Ensure artifacts exist (scaffold if not), initialize/repair `workflow-state.md` incl. its `Goal` field (seeded via `agent-nelly:agent-nelly` if available), decide `requirements-agent`'s entry mode (author vs. review), confirm no invalid earlier phase is skipped. | — |
| `after-requirements` | Evaluate the `Requirements` checklist, decide advance-to-Design vs. pause. | Facts worth persisting: interface assumptions confirmed/denied during the interview, constraint conflicts found, non-goals that turned out load-bearing. |
| `before-design` | Confirm Requirements approved, no blocking gap remains, no confirmation checkpoint open, enter native plan mode (see "Native Plan Mode Gate"). | — |
| `after-design` | Evaluate the `Design` checklist, decide advance-to-Tasks vs. pause. | `design-author` persists `research-consolidator`'s "File Summaries" (coverage gaps, unexpected interfaces, file-level findings) right after research completion — this is the only research pass in the Phase 2+3 architecture; `research-consolidator` produces design_findings, task_findings, and file_summaries together in one call. At this hook, do not re-persist those summaries (avoid duplication). Instead, persist only design-gate discoveries: tradeoff decisions made during authoring, scope choices between equivalent approaches, risk-classification calls (e.g. a risk promoted from feature-specific to project-wide), or constraints surfaced during checklist evaluation rather than research phase. |
| `after-tasks` | **Corrected 2026-09-24**: there is no agent-isdd-evaluated `Tasks` checklist to run here — per Phase 2+3, task slicing happens entirely inside `agent-tdd` during the Design Spec handoff, and `tasks.md` does not exist until `agent-tdd` writes it (see `agent-tdd/agents/agent-TDD.md`'s "Phase 5: Readiness Check" and `agent-tdd/INTEROP.md`'s "Readiness Check & Escalation"). This hook's real trigger is simply "Design is approved and implementation was requested" — the same condition `spec-driven-development`'s Implementation Handoff section already spawns on. Decide handoff / pause-for-implementation-request / pause-for-blocker on that basis. If handing off, exit native plan mode (see "Native Plan Mode Gate") before setting `Current Phase: Implementation` and spawning `agent-tdd:agent-TDD`. | **Corrected 2026-09-16**: this row used to claim `hooks/slice_spec_gate.py` hard-denies an incomplete `agent-tdd` spawn at handoff — stale from before the Phase 2+3 Design Spec handoff replaced the old Slice Spec path. `slice_spec_gate.py` validates the Slice Spec schema, not a Design Spec, so it was never the completeness gate for this path — it was removed from `hooks.json` for the Design Spec handoff and, separately, re-enabled 2026-09-17 scoped to `Track: Fast`'s single-slice Slice Spec handoff (see `tests/test_hooks_json.py`'s `test_slice_spec_gate_reenabled_for_fast_track` — it no-ops for `Track: Standard`). **Corrected 2026-09-24**: the row's original claim that `slice_spec_gate.py` "is not registered in `hooks.json`" is now itself stale — it is registered again as of the 2026-09-17 re-enable. The actual Design Spec completeness gate is `hooks/design_spec_gate.py` (see `INTEROP.md`'s "Design Spec completeness gate" section), which hard-denies the spawn unless `requirements.md`/`design.md` are both `State: Approved`. File summaries were already persisted at `after-design` (task-slicing reuses `research-consolidator`'s cached `task_findings`, per `agent-tdd`'s own `INTEROP.md`, rather than re-researching) — nothing to re-persist here. Instead, persist only task-slicing discoveries surfaced back by `agent-tdd`'s escalations or its Design Spec Handoff Report: risk flags raised during task validation, especially `paused` reasons signaling project-wide constraints or missing capabilities (most likely to recur), and slicing approaches abandoned and resliced (as `error lesson` rather than fact). |

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
| `continue` | A matching feature folder exists, status is `In Progress`, active phase not complete. | Read `workflow-state.md`, validate against phase artifacts, repair if stale, evaluate completion checklists, continue from the earliest incomplete or blocked phase. **`Current Phase: Tasks` special case (added 2026-09-24)**: there is no Tasks-phase artifact or checklist to evaluate here (see the `Tasks` row of "Phase Pass/Fail Rules" below) — `Current Phase: Tasks` only ever arises as a rollback-landing state, whether reached via `/isdd-rewind Tasks` directly or an automatic/human-relayed rollback request (see `INTEROP.md`'s "← agent-tdd / code-reviewer (rollback request)" and `MIGRATION_GUIDE.md`'s "Can I rewind to Tasks phase?"). Treat it as "ready for (re-)implementation handoff": re-invoke `spec-driven-development`'s Implementation Handoff step directly, rebuilding the Design Spec from the still-approved `requirements.md`/`design.md` (plus fresh research on request) and re-spawning `agent-tdd:agent-TDD` — never re-enter Requirements or Design authoring for this case alone. |
| `pause` | A blocker exists, user confirmation is required, active feature resolution is ambiguous, a phase gate fails, any completion checklist fails, or (when available) `agent-nelly:agent-nelly` raises an unresolved Intent-alignment flag. | Keep `Current Phase` unchanged; set `Workflow Status` precisely, `Pause Reason`, and a concrete `Next Action`. |
| `handoff` | **Corrected 2026-09-24**: Design is approved and implementation was requested, with no unresolved blockers or confirmation checkpoints remaining. Per Phase 2+3 there is no separate agent-isdd-evaluated `Tasks` checklist to pass first — this is the same trigger `spec-driven-development`'s Implementation Handoff section spawns on; `tasks.md` doesn't exist yet at this point, since `agent-tdd` produces it (and gates its own Readiness Check) inside the same spawn — see `INTEROP.md`'s "→ agent-tdd" section. | Set `Current Phase: Implementation`, `Current Owner: User`, `Workflow Status: In Progress`; let `spec-driven-development`'s "Implementation Handoff" step build the Design Spec (`Track: Standard`) or Slice Spec (`Track: Fast`) and spawn `agent-tdd:agent-TDD` — a single, one-directional handoff (see `INTEROP.md`). Once that spawn returns its report, set `Workflow Status: Complete` **and, in the same write, resync every field that still reflects the pre-handoff state**: `### Tasks`'s `Status` (to `Complete`), `Current Owner` (to `Completed` or the completing agent), `Final Handoff` (today's date), `Next Action` (to `None`, or a concrete post-completion action like a pending release — never left at its pre-handoff value), and the `Notes` section (replace stale pre-implementation notes — e.g. "N slices to be defined" — with the actual outcome: slice count, test results, from the spawn's report/`recap.md`). Do not leave any field describing an in-progress or not-yet-started state once the spawn has returned success; track no further implementation-stage state beyond this sync. |
| `complete` | Planning finished without an implementation request, or implementation is complete with no further phase work. | Set `Workflow Status: Complete`, `Pause Reason: None`, `Next Action: None`. |

## Native Plan Mode Gate

The Design and Tasks phases *are* the implementation plan — codebase research, architecture, task
breakdown — culminating in the moment code is about to be written. That maps directly onto the
harness's own plan mode, so this workflow rides it instead of only gating through conversational
confirmation:

- On `before-design`, call `EnterPlanMode` before routing into `design-author`. Skip the call (no
  error, no pause) if plan mode is already active — never enter twice.
- **Corrected 2026-09-24 [plan/design gap]**: while native plan mode is active, the harness
  itself restricts file edits to the single plan file it designated when `EnterPlanMode` was
  called — a `Write`/`Edit` to `design.md`, `workflow-state.md`, `research/cache.md`, or any
  agent-nelly memory file is refused outright, not merely discouraged. So Design does *not* write
  markdown "on agent-isdd's side" while plan mode holds, despite what an earlier version of this
  section claimed (observed in practice: the model catching itself mid-edit and self-correcting).
  `design-author` instead drafts its full normal output — design summary, Research Basis,
  touchpoints, data contracts, edge cases, validation strategy, risks/tradeoffs, Improvement
  Opportunities, Phase Completion checklist, the `research/cache.md` payload, and the
  `file_summaries` payload destined for agent-nelly — in context, and writes/updates only the
  plan file with that running draft (using `artifact-templates.md`'s structure as its content).
  The plan file *is* the working design document for the duration of plan mode, not a mirror of
  one written elsewhere. `after-design`'s checklist evaluation runs against this in-context/
  plan-file draft exactly as it would against a written `design.md` — nothing about the Design
  Gate itself changes, only where the content physically lives until approval.
- **Corrected 2026-09-24 [plan/design gap]**: once the user approves the plan (`ExitPlanMode`
  returns approved), persist the finalized draft to the real artifacts in one step before moving
  on: write `design.md` from the approved content, create `research/cache.md`, persist
  `file_summaries` to agent-nelly (`new facts` batch), and write `workflow-state.md` (`Design`
  phase `State: Approved`, plus any design-gate discoveries queued during authoring — see
  `after-design`'s "Facts worth persisting" above). `tasks.md` does not exist at this point — per
  Phase 2+3, `agent-tdd` produces it (and runs its own Readiness Check) inside the same spawn that
  also implements, not as a prior agent-isdd-owned phase (see `INTEROP.md`'s "→ agent-tdd"
  section) — so nothing Tasks-shaped is written here either. If Design fails its gate or hits a
  blocker before the user approves the plan, report it through the plan file's content and the
  conversation, the same as any other plan-mode revision — never through the state files, since
  those still cannot be written until the plan is approved (or plan mode was never entered — see
  the availability fallback below).
- Only call `ExitPlanMode` once Design is approved and implementation has been requested — the
  same gate the `handoff` action already requires, not a separate or looser one.
- If `EnterPlanMode`/`ExitPlanMode` aren't available, or a call fails for a reason unrelated to
  the checklist (host declines, tool not present), fall back silently to the existing
  conversational Design Gate / Task Readiness confirmation already required elsewhere — and, in
  that fallback only, `design-author` writes `design.md`/`research/cache.md`/`workflow-state.md`
  as it goes, the same as any other phase, since no plan-mode file restriction is in effect there.
  Never block phase progress on plan-mode availability.
- A user-declined `EnterPlanMode` is a pause condition like any other missing confirmation (see
  `pause` in Action Rules), not a reason to proceed without it.

## Phase Pass/Fail Rules

| Phase | Pass when | Fail when |
|---|---|---|
| Requirements | `Approval Checkpoint` fully satisfied, required EARS fields present, `Open Gaps` has no unresolved blocking item, `Phase Completion` fully satisfied, `State: Approved`. | Any checkpoint item incomplete, EARS requirements missing or materially weak, or unresolved ambiguity remains. |
| Design | `Phase Decision` fully satisfied, requirement coverage explicit, interfaces/touchpoints grounded in research (design-author's Research First rule), validation strategy present, `Phase Completion` fully satisfied, `State: Approved`. | Any phase decision item incomplete, design contradicts approved requirements, or validation strategy weak or absent. |
| Tasks | **Corrected 2026-09-24**: not evaluated by `agent-isdd` — per Phase 2+3, task slicing and its Readiness Check happen entirely inside `agent-tdd` during the Design Spec handoff, using `agent-tdd`'s own slice-based schema (`agent-tdd/references/tasks-schema.json`), not a phase-based one. `agent-isdd` never writes or gates a pre-handoff `tasks.md`; what this row used to describe is `agent-tdd`'s own "Phase 5: Readiness Check" (see `agent-tdd/agents/agent-TDD.md`) returning `Ready For Implementation` via its `slicing_complete` marker. Applies to `Track: Standard` only — `Track: Fast` never produces a `tasks.md` at all (see "Track Field Contract" above). | N/A on agent-isdd's side — see `agent-tdd/INTEROP.md`'s "Readiness Check & Escalation" for `agent-tdd`'s actual fail/escalation conditions (research gap, design contradiction, slicing blocked, high-risk unsplittable). |

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

The breadcrumb is rendered inline by the calling skill for status responses, and by
`agent-ux:ux-agent` as part of a `phase_transition` envelope (see `spec-driven-development`'s
Visible Progress section); the `TaskCreate`/`TaskUpdate`/`TaskList` checklist is never
`agent-ux:ux-agent`'s job either way — it cannot reach those from its subagent context. Call
`TaskCreate`/`TaskUpdate`/`TaskList` directly, self-loaded via `ToolSearch` first.
`hooks/post_write_check.py` fires a reminder on every `workflow-state.md`/`tasks.md` write as a
backstop — on that reminder, sync the checklist directly rather than delegating.

## Guardrails

- Do not restart a workflow when continuation is safer.
- Do not continue into a later phase when an earlier phase is invalidated.
- Do not hand off to implementation unless tasks are explicitly ready.
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
