---
name: spec-driven-development
description: Orchestrates the intent spec-driven workflow — EARS requirements through design and tasks — with hard phase gates, a visible breadcrumb/checklist UI, and goal-aware memory. Hands off to separate implementation/review/memory plugins.
---

# Spec Driven Development

## Purpose

Use this skill when the user wants one workflow that can:
- generate or review specs
- enforce a spec-driven process with hard phase gates
- research the codebase and produce a testable design
- hand off to implementation (research validation, task slicing, Red-Green-Refactor)
- keep visible progress (breadcrumb + checklist) and goal-aware memory throughout

This is the only user-facing entrypoint for the workflow unless the user explicitly asks for a
focused skill by name. It routes work across the companion skills internally:
- `workflow-manager`
- `requirements-agent`
- `design-author`
- **[Phase 2+3]** `research-consolidator` (unified research, replaces separate planning-agent calls)

It owns Requirements and Design only. Task slicing and implementation are owned by agent-tdd
(`agent-tdd`), invoked once via a one-directional Design Spec handoff — this skill never drives
task slicing, the Red-Green-Refactor loop, or the code-review gate itself. See `INTEROP.md` at
the repo root for the full handoff contract.

The user should not need to manually prompt each phase skill in order to move through the
workflow.

## Entry Commands

Support these natural-language intents through this single skill: start the workflow, continue
it, resume this feature's workflow, advance to the next phase, continue from the current phase.
Interpret the request and continue automatically — never ask the user to name another skill
first.

## Workflow Contract

Phase-driven, always in this order: `Requirements` → `Design` → `Tasks` → `Implementation`.
`Recap` is maintained throughout as ongoing memory and handoff context. `workflow-state.md` is
the source of truth for current phase and continuation state. `Implementation` here means "the
Slice Spec handoff to `agent-tdd` has been made" — this skill's own responsibility ends there.

Do not skip forward across phases unless the current phase is complete and not blocked.

## Visible Progress (every phase-transition or status response)

Two distinct rendering paths — use the right one based on whether a phase transition is occurring:

**Phase transitions** (Requirements → Design → Tasks → Implementation, or a restart/rewind):
delegate to `agent-ux:ux-agent` (via the `Agent` tool) with a `phase_transition` event envelope
(`caller: agent-isdd`, `event_type: phase_transition`, `phase_state`) so it can mark a session
chapter and update the spec-canvas Artifact. See `INTEROP.md`'s "→ agent-ux (UX rendering)"
section for the envelope contract and the unavailability fallback. Never drive `Artifact`/
`mark_chapter` directly from this skill — those are `agent-ux:ux-agent`'s job.

**Status responses that are not a phase transition** (formerly `breadcrumb_only` delegations):
render a progress line **inline** — no `Agent` tool call. A one-line string does not warrant a
full subagent spawn. Format:

```
**SDD** Requirements [✓] → Design [▶] → Tasks [·] → Implementation [·]
```

Use `workflow-state.md` to determine each phase's status marker: `✓` approved/complete,
`▶` in progress, `✗` blocked, `·` pending. Emit the line before the rest of the response.

The phase `TaskCreate` checklist is different: ux-agent cannot reach `TaskCreate`/`TaskUpdate`/
`TaskList` from its subagent context (see `agent-ux:ux-agent`). Render/refresh the checklist
**directly from this skill instead**, in the same response: self-load the three
tools via `ToolSearch` (`select:TaskCreate,TaskUpdate,TaskList`) once per session if not already
loaded, call `TaskList` to check for existing items before creating, then `TaskCreate`/
`TaskUpdate` per `agent-ux`'s `references/ux-conventions.md`'s Phase tick list conventions (the
convention itself, driven by the calling skill and not `agent-ux:ux-agent`, is unchanged by the
extraction — only where it's documented moved).

## Goal-Aware Memory

Before starting or continuing meaningful phase work, when agent-nelly is available (per the
Availability Check defined in `workflow-manager/SKILL.md`), delegate to
`agent-nelly:nelly-orchestrator` for a holistic brief (nelly's four output sections: Intent,
Relevant entries, Intent alignment, Written) instead of reading `~/.claude/sdd-memory/` files
directly. If it flags an Intent-alignment concern, surface it to the user before proceeding —
don't silently continue past a stated drift.

**[Phase 1.2] Brief caching:** On workflow resume (`before-continue`), check if a cached nelly
brief exists in `workflow-state.json`'s `nelly_brief_cache` field:
- If cached brief is valid (Intent Hash matches + timestamp < 24h old): reuse cached brief, no fetch
- If cached brief is invalid (Intent Hash mismatch OR timestamp stale): fetch fresh brief, update cache
- If no cached brief: fetch fresh brief, cache it

When the next phase is **Design**, include `surface relevant memory: true` in the nelly call so
the brief's `Relevant entries` section is populated. `design-author` passes those entries to
`planning-agent` in place of the former separate pre-sweep nelly call — no second nelly spawn
needed. For other phases, `surface relevant memory` is not required unless you have a specific
reason to request it.

This skill is the single fetch/delegation point, per continuous stretch of phase work, for the
nelly brief **and** for `planning-agent`/`spec-reviewer` findings still valid from earlier in
that same stretch (e.g. a `planning-agent` finding produced during Design). When a brief or
finding has already been fetched this session and is still visible in context, reuse it rather
than re-calling `agent-nelly:nelly-orchestrator`/`planning-agent`/`spec-reviewer` again for the
same content. Re-fetch only when one of these triggers applies — identical rule, same three
triggers, now scoped to a wider set of cached content, not a new or looser rule:

1. No prior brief or finding is visible in context (a new session, or context was compacted
   since the last fetch) **and** no persistent cache exists in `workflow-state.json`. If persistent
   cache exists and is valid, reuse it instead of fetching. Applies identically to a
   `planning-agent`/`spec-reviewer` finding: if it isn't visible in context and no persistent
   cache is valid, it isn't reusable.
2. A rewind (Rewind Contract) or a Mid-Phase Change Classification happened since the cached
   brief/finding was fetched — both live in `workflow-manager`'s `SKILL.md`. A rewind or
   mid-phase change can invalidate a cached codebase finding exactly as it can invalidate a
   brief, since either can change what "the current design/task" even means. **[Phase 1.2]** Also
   invalidates persistent cache; clear `nelly_brief_cache` from `workflow-state.json`.
3. `workflow-manager`'s `before-continue` Intent-alignment check flagged a divergence since the
   cached brief/finding was fetched. When this fires, treat every cached item (brief and any
   `planning-agent`/`spec-reviewer` finding alike) as invalidated, not only the brief — an
   Intent-level divergence is a signal about the whole stretch of work, not brief-specific.
   **[Phase 1.2]** Clear persistent cache on Intent drift.

None of the three triggers assumed brief-specific semantics that fail to hold for a
`planning-agent`/`spec-reviewer` finding — re-verified as part of extending this rule's scope,
per design.md's mitigation for the correctness risk this generalization raises.

When delegating into `workflow-manager` or `design-author`, pass along the
already-fetched brief and any still-valid finding explicitly rather than letting any of them
re-derive or re-fetch on their own; `design-author` checks for a still-valid
cached finding before re-delegating to `research-consolidator`, mirroring how it already checks for a
reusable agent-nelly brief. `workflow-manager`'s own `start`-time Goal-seeding call is a distinct-purpose, always-fresh
call outside this dedup pool — see its Goal Field Contract section; it is never satisfied by
reusing a cached brief. The `before-continue` Intent-alignment check no longer spawns a nelly
subagent — it runs inline against the Intent already in session context (see
`workflow-manager/SKILL.md`'s Goal Field Contract).

**Memory write-back at phase boundaries**: at each `after-*` hook, this skill performs the
nelly write-back call directly, following the contract defined in `workflow-manager`'s Lifecycle
Hooks section (which owns the rule, not the call itself — see its ownership note). The
criterion and graceful-degradation rules are defined in `INTEROP.md`'s "→ agent-nelly" section.

## Start Protocol

1. Use `workflow-manager` to identify or derive the feature title and slug, and to scaffold or
   locate the per-feature artifact structure (including `intent/` directory).
2. If `agent-nelly:nelly-orchestrator` is available, call it to read the project's stored
   Intent and seed the feature's `Goal` field in `workflow-state.md` from it when Intent is more
   specific than "not yet captured". Otherwise ask the user for the Goal directly.
3. **[NEW Phase 1.1]** Create `intent/intent.md` with:
   - Project Intent (from agent-nelly brief, or "not yet captured")
   - Feature Goal (seeded from step 2)
   - Success Signals (brief, 2-3 observable outcomes)
   - Anti-Patterns (failure indicators)
   - Intent Anchor: compute SHA256 hash of intent.md content
4. Update `workflow-state.md` with:
   - `Intent Hash: <anchor>`
   - `Intent Alignment Status: unreviewed`
5. Initialize `workflow-state.md` with `Current Phase: Requirements` and `recap.md` to match.
6. Route into `requirements-agent`: it interviews from scratch when the input is vague, or
   reviews-and-rewrites when the user hands over an existing ticket/PRD/draft — one skill, two
   entry modes, same gate.
7. After Requirements are approved, continue automatically into `Design` (`design-author`).
8. After Design is approved, continue automatically into `Implementation` (`agent-tdd`).
9. After Implementation handoff, stop with a clear handoff message. (Implementation ownership
   transfers to `agent-tdd`.)

## Continue Protocol

0. **Rollback Request Check:**
   - The `before_continue` hook automatically checks for pending rollbacks from prior agent-tdd runs.
   - If agent-tdd found a slicing blocker (task conflicts, design contradiction, research gap), the rollback will be surfaced with reasoning and recommended target phase.
   - Address the issue and rewind using `/isdd-rewind <target>`, then return to continue the workflow.

1. Use `workflow-manager` to find the relevant feature folder and resolve state (see its
   Decision Order — `agent-nelly:nelly-orchestrator`'s stored Intent first (when available),
   then `workflow-state.md`, then `workflow-state.json`, then open blockers, then phase files,
   then `recap.md`).
2. **[Phase 1.2]** Check cached nelly brief in `workflow-state.json` → `nelly_brief_cache`:
   - If valid (Intent Hash match + timestamp fresh): reuse cached brief
   - If invalid: fetch fresh brief via agent-nelly, update cache
3. Continue from the earliest blocked or incomplete phase; auto-advance through later phases
   whose entry gates are satisfied.
4. Pause only when a gate fails, a confirmation checkpoint is required, or implementation was
   not requested.

Do not restart from Requirements if a later phase is already the active incomplete phase,
unless requirement changes invalidate the design or tasks.

## Internal Routing Rule

Use focused skills internally rather than asking the user to switch prompts:
- `workflow-manager` — orchestration, phase detection, state repair, transitions, scaffolding.
- `requirements-agent` — requirements from scratch or from an existing draft/ticket/PRD.
- `design-author` — design, informed by `research-consolidator` and `agent-nelly:nelly-
  orchestrator` (when available).

Only expose these skill names when the user explicitly asks which one is being used, wants to
invoke one directly, or a pause message needs to explain which capability produced the output.

## Subagent Delegation

Four capabilities ship as **subagents** (`agents/`) so their bounded work runs in an isolated
context and returns only a conclusion, keeping this orchestrator thread lean across a long
workflow:

- `spec-reviewer` — delegate when `requirements-agent` needs to assess an existing draft before
  rewriting it.
- **[Phase 2+3]** `research-consolidator` — delegate during Design to produce unified research
  (design_findings, task_findings, file_summaries) in one pass, eliminating redundant research
  between design-author and agent-tdd. Replaces the prior separate planning-agent calls.
- `agent-nelly:nelly-orchestrator` — an external peer-plugin subagent, not one of this plugin's
  own `agents/`, invoked the same way (via the `Agent` tool with that literal `subagent_type`
  string), gated by the Availability Check — delegate before any phase starts, when available,
  for a goal-aware brief (Intent, Relevant entries, Intent alignment, Written); it is
  the sole writer into agent-nelly's own memory store, which agent-isdd never reads or writes
  directly. **[Phase 2+3]** Also used to query and cache file summaries for cross-feature reuse.
- `agent-ux:ux-agent` — an external peer-plugin subagent, delegate at every **phase transition**
  for chapter markers and the spec-canvas Artifact, via the UX Event Envelope (`caller:
  agent-isdd`, `event_type: phase_transition`, `phase_state`, `delta`, `artifact_path` — see
  `INTEROP.md`'s "→ agent-ux (UX rendering)" section). Status breadcrumbs between transitions
  are rendered inline (see "Visible Progress" above). It does not own the `TaskCreate` checklist
  — see "Task Tracker Sync" below.

Delegation rules:
- Prefer the subagent over inlining these when the task is well-scoped.
- Subagents cannot talk to the user. **You** own every user-facing confirmation checkpoint:
  take a subagent's returned report, surface it, get confirmation, then update
  `workflow-state.md` and `recap.md` yourself — per `workflow-manager`'s field-update contract
  (see its Lifecycle Hooks section), not a separate set of rules.
- `requirements-agent` and `design-author` stay inline for interviewing the user, but delegate
  their bounded sub-tasks (`spec-reviewer` for draft assessment; `planning-agent` for research)
  to subagents rather than doing that work in the main thread.

## Implementation Handoff (Phase 2+3 revised)

**[Phase 2+3]** Once Design is approved and implementation is requested, this skill's job is to
build a **Design Spec** and spawn `agent-tdd` for research validation, task slicing, and
implementation — a single, one-directional handoff, not an orchestrated multi-stage loop. See
`INTEROP.md` at the repo root for the exact Design Spec contract (requirements.md, design.md,
research/cache.md, pre-fetched file summaries, recap.md).

1. Extract file list from `design.md` + `research/cache.md` (all files mentioned in Research Basis
   and task_findings sections).
2. Query `agent-nelly:nelly-orchestrator` for cached file summaries (if available):
   - Pass file list to agent-nelly
   - Receive cache hits (with git_hash validation) + cache misses
   - Bundle cache hits into Design Spec handoff
3. Construct **Design Spec** with:
   - Full `requirements.md` (approved)
   - Full `design.md` (approved, with Research Basis)
   - `research/cache.md` (design_findings, task_findings, file_summaries, git_hashes)
   - Pre-fetched file summaries from agent-nelly (if available)
   - `recap.md` (summary, risks, blockers, Goal alignment)
4. Before spawning, check the session's `<system-reminder>` agent-types block for
   `agent-tdd:agent-TDD`. If absent, pause with a concrete, actionable message (e.g. "agent-tdd
   is not installed in this session — install it before requesting implementation") rather than
   attempting the work internally.
5. Spawn `agent-tdd:agent-TDD` with the Design Spec (via the `Agent` tool).
6. Take its returned handoff report:
   - If report indicates research validation escalation: pause and surface reason (user re-enters
     to address, then agent-isdd continues via before-continue hook)
   - If report indicates slicing blockers: pause with specific blocker
   - If report indicates implementation started: log handoff in `recap.md`, set
     `Workflow Status: Complete`
7. Do not resume, monitor, or drive `agent-TDD` past this initial spawn — anything after its
   own review pauses or implementation is outside this skill's scope.
8. If the report's Handoff Facts field is non-empty and `agent_nelly_available` is `true` in
   `workflow-state.json`, call `agent-nelly:nelly-orchestrator` with those facts as a `new facts`
   batch. One call only — no re-fetch of the brief needed.

## Automatic Code-Reviewer Invocation (High-Risk Slices)

**[Phase 2+3]** After agent-tdd spawns and begins Red-Green-Refactor, it marks each slice with a
Risk Tier (`standard` or `high-risk`). At the Green→Refactor pause for each slice, the
`high_risk_reviewer` hook automatically invokes code-reviewer and applies severity-based logic:

**Automatic Flow (High-Risk Slices)**:

1. **Detection**: After green tests pass, agent-tdd emits `<!--AGENT-TDD-PHASE:green_pause-->`.
2. **Invocation**: The `high_risk_reviewer` hook (SubagentStop) automatically runs `/code-reviewer`
   scoped to files touched by the high-risk slice and file-path-scoped standard slices.
3. **Severity Classification**: Code-reviewer findings are mapped to three categories:
   - **MAJOR** (critical): Any FAIL/WARN on intent, regressions, or security dimensions
   - **NON-MAJOR** (follow-up): Any FAIL/WARN on best_practices, naming, or scalability (no majors)
   - **CLEAN**: All dimensions PASS
4. **Auto-Advance Logic**:
   - **CLEAN or NON-MAJOR**: Emit resume message, create follow-up tasks, append to recap.md,
     optionally create GitHub issues. Resume agent-tdd to refactor.
   - **MAJOR**: Emit rollback marker (`<!--SDD-ROLLBACK-REQUEST-->`) to pause and return to Tasks
     phase. Developer reviews the critical findings and resubmits the slice.

**Follow-Up Tracking**:
- Non-major findings create TaskCreate items for post-refactor review
- Findings appended to recap.md with severity and task/issue references
- GitHub issues optionally created with detailed finding descriptions
- No manual intervention required for non-major findings — refactor proceeds automatically

**For Standard Slices**:
- Standard slices touching high-risk file paths (from design.md Risks section) are also reviewed
- File-path scoping reduces noise: only slices modifying critical files are reviewed
- Same severity classification and auto-advance logic applies

**Configuration** (workflow-state.json):
```json
{
  "code_reviewer_tracking": {
    "high_risk_phases": ["Phase 1", "Phase 2", ...],
    "reviewed_phases": [...],
    "config": {
      "high_risk_file_paths": ["src/models/user.py", ...],
      "review_timeout_seconds": 600,
      "skip_on_timeout": true
    }
  }
}
```

See `INTEROP.md` "Auto Code-Reviewer Invocation" section for full integration details.

## Requirements Gate

Ready to advance only when: all required fields are present, expressed in EARS format, and no
unresolved ambiguity remains. Minimum content: problem statement, user outcome, constraints,
non-goals, edge cases, success criteria, dependencies.

If any of the above are weak, vague, or missing: refuse to advance, interview the user to fill
the weakest areas first, prioritizing the most ambiguous or highest-risk gaps. If ambiguity
remains after interviewing: stop, return the partial draft, return an explicit gaps list.

## Existing Ticket Or PRD Handling

When the user provides a ticket, PRD, or existing spec, `requirements-agent`'s review mode
handles it: review first, rewrite only the weak sections into EARS format, present the changed
draft, pause for confirmation, and only then treat it as the canonical requirements artifact.
Never treat incoming material as automatically sufficient for phase advancement.

## Phase Gating

Phase gating, auto-advance rules, pause conditions, and state repair are governed entirely by
`workflow-manager` — see its `SKILL.md`.

## Native Plan Mode

`workflow-manager` owns entering native plan mode (`EnterPlanMode`) at `before-design` and
exiting it (`ExitPlanMode`) at `after-tasks` once the `Tasks` checklist passes — see its "Native
Plan Mode Gate" section for the full contract. This stays here in the orchestrator rather than
delegated to `agent-ux:ux-agent` because it is a user-facing approval checkpoint (`agent-ux:ux-agent`
never talks to the user).
Requesting approval this way is in addition to the phase gates above, not instead of them —
`ExitPlanMode` is only ever called once the Tasks checklist has already passed.

## Task Tracker Sync

`tasks.md` is a repo-persisted planning artifact, distinct from the harness's own task tracker.
Call `TaskCreate`/`TaskUpdate`/`TaskList` directly from this skill at every phase transition
(self-loaded via `ToolSearch` first) — see "Visible Progress" above.

## Artifact Convention

Per-feature artifacts are plugin-generated state, not source — they live under the project's
central SDD memory directory (`~/.claude/sdd-memory/<project-slug>/`), not the repo:

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

`workflow-manager` owns scaffolding this structure and keeping it stable across phases. Use the
canonical templates in `references/artifact-templates.md`; keep the same section order unless
the user explicitly asks to change it.

## Writing Style

Structured sections with checklists, concise prose plus bullet lists, for `requirements.md`,
`design.md`, and `recap.md`. For `tasks.md`, optimize for agent handoff: minimal narration,
explicit ordered execution steps, concrete validation steps.
