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

1. `agent-nelly:nelly-orchestrator`'s stored Intent (via the Availability Check gate — see "Goal
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
- Seeded from, and alignment-checked against, `agent-nelly:nelly-orchestrator`'s stored `Intent`
  — one line per *project*, not per-feature (see design.md's "Intent → Goal Mapping"). Intent is
  coarser-grained: it captures what the project is for, Goal what this specific feature is for —
  expected to be consistent with, not identical to, the project's Intent.
- On `start`, if the Availability Check (below) found `agent-nelly:nelly-orchestrator` available,
  call it (`Agent` tool, `subagent_type: agent-nelly:nelly-orchestrator`) to read the stored
  Intent. If more specific than "not yet captured," seed the new `workflow-state.md`'s `Goal`
  field from it; otherwise ask the user (a feature's Goal isn't always identical to its problem
  statement). If unavailable, always ask the user — there's no Intent to seed from.
- On every `before-continue`, perform an Intent-alignment check **inline** — do not spawn
  `agent-nelly:nelly-orchestrator` for this. **[Phase 1.1]** The check compares Intent Hash
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

### Availability Check

- At `before-requirements` (workflow start) and `before-continue` (workflow resume), check the
  session's agent-types listing — the `<system-reminder>` block enumerating "Available agent
  types for the Agent tool" — for the string `agent-nelly:nelly-orchestrator`.
- Cache the boolean in `workflow-state.json`'s `agent_nelly_available` field so later steps in
  the same hook (and later hooks) don't need to re-inspect the listing.
- If unavailable, surface one plain notice to the user and continue without the Intent-alignment
  check — graceful degradation, never a blocking condition.

### `workflow-state.md` Vs `workflow-state.json` — Write Responsibilities

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
`~/.claude/sdd-memory/<project-slug>/`. Plain field mirror, no `hook_history` of its own; the
memory-dir `workflow-state.json` stays the authoritative, audited copy. Entirely hook-owned —
nothing here needs to write it directly.

## Scaffolding (folded from the former `artifact-scaffolder` skill)

Per-feature artifacts are plugin-generated state, not source — they live under the project's
central SDD memory directory (`~/.claude/sdd-memory/<project-slug>/`), never inside the repo.
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
      tasks/tasks.md
      recap/recap.md
```

Rules: one feature folder per feature, named with local start date plus slug; use the exact
template bodies from `references/artifact-templates.md` and
`references/workflow-state.template.json`; preserve section order so later agents can rely on
stable parsing; `workflow-state.json` is scaffolded together with `workflow-state.md` every time
the latter is created or updated (field schema in `references/workflow-state.template.json`).

## Phase Completion Evaluation

For every invocation, determine: active feature folder, requested action (`start`, `continue`,
`pause`, `handoff`, `complete`), authoritative current phase, workflow status, pause reason if
any, next action — see "Action Rules" below for how each is chosen.

Evaluate `Requirements`/`Design`/`Tasks` completion against the explicit pass/fail checklists in
`references/artifact-templates.md`, not broad narrative judgment (see "Phase Pass/Fail Rules"
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
handing off)**: if `agent_nelly_available` is `true`, call `agent-nelly:nelly-orchestrator` with a
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
| `before-continue` | Attempt to resolve the active feature folder and read `workflow-state.md`. If no existing workflow state is found, route to `start` (via `before-requirements`). If state exists: check for pending rollback request first (see "Rollback Request Intake" — takes priority over everything else here), **[Phase 1.1]** perform the inline Intent-alignment check (Goal Field Contract; no nelly spawn; compare Intent Hash from session context against workflow-state.md's stored hash for drift), **[Phase 1.2]** check cached nelly brief validity (Intent Hash match + timestamp < 24h; if invalid, clear cache), detect/repair stale or contradictory artifacts, decide the next action. | No nelly write-back at this hook — read-only w.r.t. phase decisions. **[Phase 1.1]** Update `Intent Alignment Status` to `aligned` or `drift` based on hash check. **[Phase 1.2]** Clear `nelly_brief_cache` if Intent drift detected or timestamp stale. |
| `before-requirements` | Ensure artifacts exist (scaffold if not), initialize/repair `workflow-state.md` incl. its `Goal` field (seeded via `agent-nelly:nelly-orchestrator` if available), decide `requirements-agent`'s entry mode (author vs. review), confirm no invalid earlier phase is skipped. | — |
| `after-requirements` | Evaluate the `Requirements` checklist, decide advance-to-Design vs. pause. | Facts worth persisting: interface assumptions confirmed/denied during the interview, constraint conflicts found, non-goals that turned out load-bearing. |
| `before-design` | Confirm Requirements approved, no blocking gap remains, no confirmation checkpoint open, enter native plan mode (see "Native Plan Mode Gate"). | — |
| `after-design` | Evaluate the `Design` checklist, decide advance-to-Tasks vs. pause. | `design-author` persists `planning-agent`'s "Nelly summaries to write" (coverage gaps, unexpected interfaces, file-level findings) right after research completion. At this hook, do not re-persist those summaries (avoid duplication). Instead, persist only design-gate discoveries: tradeoff decisions made during authoring, scope choices between equivalent approaches, risk-classification calls (e.g. a risk promoted from feature-specific to project-wide), or constraints surfaced during checklist evaluation rather than research phase. |
| `after-tasks` | Evaluate the `Tasks` checklist, decide handoff / pause-for-implementation-request / pause-for-blocker. If the checklist passes and the decision is handoff, exit native plan mode (see "Native Plan Mode Gate") before setting `Current Phase: Implementation`. | When the decision is `handoff`, `hooks/slice_spec_gate.py` hard-denies the `agent-tdd` spawn itself if the Slice Spec is missing a required field — no need to re-verify completeness by hand. `tdd-planner` persists its own "Nelly summaries to write" right after research completion. At this hook, do not re-persist those summaries (avoid duplication). Instead, persist only task-slicing discoveries: risk flags raised during task validation, especially `paused` reasons signaling project-wide constraints or missing capabilities (most likely to recur), and slicing approaches abandoned and resliced (as `error lesson` rather than fact). |

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
| `start` | No matching feature folder exists, the user explicitly asks to start a new workflow, or an existing one shouldn't be reused safely. | Derive the slug, scaffold the structure (including `intent/` directory), capture the Goal via `agent-nelly:nelly-orchestrator` (if available, per the Availability Check) or by asking the user, create `intent/intent.md` with Goal + Success Signals + Intent Hash, initialize `workflow-state.md` (with Intent Hash + Intent Alignment Status) and `recap.md`, route into `requirements-agent`. |
| `continue` | A matching feature folder exists, status is `In Progress`, active phase not complete. | Read `workflow-state.md`, validate against phase artifacts, repair if stale, evaluate completion checklists, continue from the earliest incomplete or blocked phase. |
| `pause` | A blocker exists, user confirmation is required, active feature resolution is ambiguous, a phase gate fails, any completion checklist fails, or (when available) `agent-nelly:nelly-orchestrator` raises an unresolved Intent-alignment flag. | Keep `Current Phase` unchanged; set `Workflow Status` precisely, `Pause Reason`, and a concrete `Next Action`. |
| `handoff` | `Tasks` are ready, implementation was requested, no unresolved blockers or confirmation checkpoints remain, and the `Tasks` checklist passes. | Set `Current Phase: Implementation`, `Current Owner: User`, `Workflow Status: In Progress`; let `spec-driven-development`'s "Implementation Handoff" step build the Slice Spec and spawn `agent-tdd:agent-TDD` — a single, one-directional handoff (see `INTEROP.md`). Once that spawn returns its report, set `Workflow Status: Complete`; track no further implementation-stage state here. |
| `complete` | Planning finished without an implementation request, or implementation is complete with no further phase work. | Set `Workflow Status: Complete`, `Pause Reason: None`, `Next Action: None`. |

## Native Plan Mode Gate

The Design and Tasks phases *are* the implementation plan — codebase research, architecture, task
breakdown — culminating in the moment code is about to be written. That maps directly onto the
harness's own plan mode, so this workflow rides it instead of only gating through conversational
confirmation:

- On `before-design`, call `EnterPlanMode` before routing into `design-author`. Skip the call (no
  error, no pause) if plan mode is already active — never enter twice.
- Stay in plan mode through `Design` and `Tasks` — both only ever touch markdown (`design.md`,
  `tasks.md`), exactly what plan mode expects; no separate discipline needed.
- Before calling `ExitPlanMode` on `after-tasks`, write the finalized `design.md` + `tasks.md`
  content (or a faithful summary) to the plan file the harness specified when plan mode was
  entered, so the native approval screen reflects the actual plan rather than an empty or stale
  file — in addition to, not a replacement for, the repo-persisted files, which stay the durable
  artifacts.
- Only call `ExitPlanMode` once the `Tasks` checklist passes — the same gate the `handoff` action
  already requires, not a separate or looser one.
- If `EnterPlanMode`/`ExitPlanMode` aren't available, or a call fails for a reason unrelated to
  the checklist (host declines, tool not present), fall back silently to the existing
  conversational Design Gate / Task Readiness confirmation already required elsewhere — never
  block phase progress on plan-mode availability.
- A user-declined `EnterPlanMode` is a pause condition like any other missing confirmation (see
  `pause` in Action Rules), not a reason to proceed without it.

## Phase Pass/Fail Rules

| Phase | Pass when | Fail when |
|---|---|---|
| Requirements | `Approval Checkpoint` fully satisfied, required EARS fields present, `Open Gaps` has no unresolved blocking item, `Phase Completion` fully satisfied, `State: Approved`. | Any checkpoint item incomplete, EARS requirements missing or materially weak, or unresolved ambiguity remains. |
| Design | `Phase Decision` fully satisfied, requirement coverage explicit, interfaces/touchpoints grounded in research (design-author's Research First rule), validation strategy present, `Phase Completion` fully satisfied, `State: Approved`. | Any phase decision item incomplete, design contradicts approved requirements, or validation strategy weak or absent. |
| Tasks | `Task Readiness Checklist` fully satisfied, at least one concrete implementation phase exists, tasks sliced safely for TDD, confirmation blockers resolved, `State: Ready For Implementation` or `Complete`. | Slices oversized, validation targets missing, test intent missing, or required confirmation remains open. |

## State Repair Rules

Treat `workflow-state.md` as stale when: a later phase file has a newer `Last Updated` with an
approved state, the recorded current phase is earlier than the newest approved phase, the stored
pause reason doesn't match the actual blocker, or the stored next action doesn't match the
earliest incomplete phase. When repairing: prefer the newest internally consistent artifacts,
update `workflow-state.md`, note the repair in `recap.md`, never silently discard unresolved
contradictions, keep phase pass/fail status aligned with the repaired state.

A `workflow-state.json` missing the `agent_nelly_available` field (an in-flight feature whose
file predates it) is not a staleness/error condition — treat it as "not yet checked" and let the
next `before-continue` hook populate it via the Availability Check.

## Rewind Contract

`commands/isdd-rewind.md` delegates all rewind state-mutation logic to this contract.

A rewind request names a target phase (`Requirements`, `Design`, or `Tasks`) earlier than or
equal to the current `Current Phase`. On a valid rewind:

- Set `Current Phase` (both files) backward to the target phase.
- Set `Workflow Status`/`phase_state` for re-entry (typically `In Progress`); clear
  `Pause Reason`/`pause_reason` only if the pause was specific to the phase being left.
- Do not clear, reset, or overwrite the `Status`/blocked fields of any later phase — rewinding
  only moves the *current* pointer, never retroactively resolves later-phase state.
- Log the rewind (from, to, actor, timestamp) in `recap.md` and as a `hook_history` entry.
- If the target is later than `Current Phase` or doesn't exist, refuse and pause with a concrete
  reason.

## Rollback Request Intake

Part of `before-continue` (see above) — checked first, before anything else in that hook.

A rollback request reaches agent-isdd two ways, per `INTEROP.md`'s "← agent-tdd / code-reviewer
(rollback request)" section: automatically, via `rollback_pending` in `workflow-state.json`
(written by `hooks/subagent_report.py` when it recognizes the marker on `agent-tdd`'s initial
spawn report), or via human-relay, when the marker text appears directly in the user's message
re-entering agent-isdd.

On either form:

- Determine the target phase from the request. If it doesn't clearly map to what changed, default
  to the more conservative (earlier) phase rather than guessing narrowly.
- Invoke the existing Rewind Contract at that target phase — the only mutation path; don't
  duplicate its state-mutation logic here.
- Clear `rollback_pending` (via `sdd_state.clear_rollback_pending`) once the rewind is applied.
- Log the event in `recap.md` distinctly from a routine rewind — e.g. "Rollback
  (mid-implementation): <from> → <to>, reason: <reason>" rather than the Rewind Contract's plain
  "Rewind: <from> → <to>" phrasing — so a later reader can tell a rollback (triggered by an
  implementation-side finding) apart from a routine user-initiated rewind.
- Applies even when `Workflow Status` is `Complete` — `before-continue` is the standard re-entry
  point regardless of prior status, so a rollback request reopens the workflow at the target phase
  rather than requiring manual state repair.
- **Loop prevention**: if the same target phase is requested twice in a row, pause and surface the
  repetition to the user rather than rewinding again automatically.

## Mid-Phase Change Classification

When the user raises a new idea or a differing task while Design or Tasks is the active phase,
classify the change before reacting, reusing the Rewind Contract for its only mutation path:

- Does satisfying the change require editing an **already-approved earlier phase's own
  artifact** — a `requirements.md` EARS/constraint/non-goal for a Design-phase idea, or a
  `design.md` Architecture/Data-Contracts-And-Interfaces section for a Tasks-phase idea? →
  **earlier-phase invalidation** → invoke the Rewind Contract to that phase.
- Does it only require editing the **current phase's own artifact**, staying inside what that
  phase already owns? → **current-phase refinement** → redo the current phase in place; no
  `Current Phase` change.
- If ambiguous, ask exactly one narrow question: "Does this change *what* we're building (would
  require editing `requirements.md`) or *how* we're building it (stays inside
  `design.md`/`tasks.md`)?"
- Always record the classification, its reasoning, and the branch taken in `recap.md`, so a later
  reader can see why a mid-phase change did or didn't trigger a rewind.

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
- Do not leave `workflow-state.md` stale after a routing decision.
- Do not skip the Goal-field capture on `start` (requires nelly when available).
- Do not skip the inline Intent-alignment check on `before-continue` — it runs regardless of
  nelly availability (no nelly spawn needed; see Goal Field Contract).
- Do not scaffold a second, divergent folder structure — always the one canonical layout above.
