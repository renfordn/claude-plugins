# Interop: agent-isdd

This plugin owns Requirements → Design → Tasks only. It hands off to three sibling plugins
rather than owning their work. This document is the authoritative description of each boundary,
for both agent-isdd's own maintainers and the sibling plugins' maintainers to cross-check.

> Status: skeleton written in Phase 1 of the `agent-isdd` scope refactor; the concrete Slice
> Spec mapping below is implemented and finalized in Phase 3. See
> `~/.claude/sdd-memory/users-jay-nelson-codebase-ai-plugins-claude-agent-isdd/spec/2026-08-12-isdd-plugin-scope-refactor/`
> for the full requirements/design/tasks this repo was built from.

## → agent-tdd (implementation, Phase 2+3 revised)

**[Phase 2+3]** At the end of Design, once Design is approved and implementation is requested,
`agent-isdd` constructs a **Design Spec** from the approved `requirements.md`/`design.md`, the
cached research findings, and pre-fetched file summaries, then spawns `agent-tdd` for research
validation, task slicing, and implementation.

**Design Spec** includes (validated by plugin-harness):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requirements_md | string | yes | Full approved requirements.md |
| design_md | string | yes | Full approved design.md (with Research Basis section) |
| research_cache | object | yes | Research findings including design_findings, task_findings, file_summaries, git_hashes |
| recap_md | string | yes | Summarized recap of summary, known risks, blockers, and Goal alignment notes |

**Optional fields** (passed through but not validated):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file_summaries | object | no | Pre-fetched file summaries from agent-nelly cache (if available), merged into research_cache for files not already covered by fresh file_summaries — see skills/spec-driven-development/references/implementation-handoff.md's Standard step 2 for deduplication rationale |

**Agent-tdd responsibilities** (Phase 2+3):
1. **Research Validation** (optional re-research gaps only)
   - Validate design.md's file touchpoints against research cache
   - If cache is thin or inconsistent: run targeted deep-read only on gaps
   - If design contradicts research: escalate back to agent-isdd

2. **Task Slicing** (produce `tasks.md`)
   - Produce phased, TDD-sized slices from Design + task_findings
   - Validate slice safety (3 files max, testable, acyclic dependencies)
   - Assign Risk Tiers (high-risk → spawn test-author first)

3. **Implementation** (Red-Green-Refactor per slice, existing behavior)

This is a **one-directional handoff**: agent-isdd does not resume or monitor agent-tdd past
the initial spawn, with one scoped exception (Test-Author Gate, immediately below). Task
slicing happens inside agent-tdd (not handed back to agent-isdd as Slice Specs). Escalations
back to agent-isdd (design contradicts research, research too thin) pause with explicit reason;
agent-isdd resumes via its `before-continue` hook when user re-enters after addressing the
escalation.

**Exception — Test-Author Gate (automatic, `spec-driven-development` skill-driven,
added 2026-09-16)**: `agent-tdd` already determines every slice's Risk Tier during Task Slicing
and Risk Tier Assignment (Phases 2 and 4 below), *before* per-slice implementation begins — so a
high-risk slice needing `test-author` is never actually discovered mid-pipeline, it's known at
the `slicing_complete` checkpoint. When `tasks.md` contains at least one `high-risk` slice,
`agent-TDD` stops there and hands back a report naming them (its **High-Risk Slices** field —
see `agent-tdd`'s own `agents/agent-TDD.md`). `hooks/high_risk_reviewer.py` (on `SubagentStop`)
detects this and writes `test_author_pending` to `workflow-state.json`, structurally parallel to
this file's existing `rollback_pending` field.
`skills/spec-driven-development/references/implementation-handoff.md`'s Standard step 6 reads it,
spawns `agent-tdd:test-author` once per named slice,
bundles the results, and resumes the same `agent-TDD` instance via `SendMessage` — the *only*
point this skill ever resumes `agent-tdd`. Zero high-risk slices means zero behavior change:
`agent-TDD` proceeds straight through exactly as before this exception existed. This closes a
gap from an earlier attempt at the same problem (a caller-side marker,
`TEST_AUTHOR_NEEDED_MARKER`, added and then removed the same day it was added, once it became
clear no marker was needed at all — see `hooks/subagent_report.py`'s own comment for that
history).

**Exception — Code-Review Gate (manual, caller-driven)**: `agent-TDD`'s Review pause between
Green and Refactor is mandatory for *every* slice (see `agent-tdd`'s own `INTEROP.md`, "The
mandatory review pause"), not just high-risk ones — the automatic path described below in "Auto
Code-Reviewer Invocation" only covers high-risk slices and standard slices that touch a
high-risk file path, so most standard-risk slices still hit this manual path. Corrected
2026-09-15: this used to (incorrectly) claim the `before-continue` hook detects agent-tdd's
paused state and auto-resumes it via `SendMessage`; neither `hooks/before_continue.py` nor
`spec-driven-development/SKILL.md` implement that — both explicitly disclaim owning
resumption of a paused `agent-tdd` (see their own source comments/scope notes) — and a hook
could not do this even in principle: hooks are blocking subprocesses with no `Agent`/`SendMessage`
tool access, the same constraint documented for `agent-nelly`'s hook-bound-consumer pattern in
its own `INTEROP.md`.

What actually happens, matching `agent-tdd`'s own generic guidance ("What you do with that
pause is up to you" / resume via `SendMessage`): the user (or whichever context is driving)
runs `/code-reviewer` themselves, then manually resumes the still-live `agent-tdd` session —
via `SendMessage` to its agent id, in the *same* session — passing along whether/what review
found. This is a same-session, live-agent-id operation; it has no relationship to
`/isdd-continue` or `workflow-state.json`, both of which resume the SDD *workflow* across
sessions, not a specific paused subagent instance within one.

### Agent-tdd Implementation Requirements (Phase 2+3)

Agent-tdd must implement three new phases before Red-Green-Refactor:

**Phase 1: Research Validation**
- Input: Design Spec (requirements.md, design.md, research/cache.md, file_summaries)
- Validate research completeness:
  - Are design.md's file touchpoints in research/cache.md?
  - Are interfaces documented?
  - Are constraints captured?
- Decision:
  - ✓ Research thorough: proceed to slicing
  - ✗ Research thin: run targeted research-consolidator (on gaps only)
  - ✗ Design contradicts research: escalate back to agent-isdd (pause, surface reason)

**Phase 2: Task Slicing**
- Input: Requirements + Design + validated research + task_findings
- Produce tasks.md with:
  - Phased, TDD-sized slices (one behavior change, one file/module touched if possible)
  - Risk Tiers per slice (high-risk → spawn test-author first)
  - Depends On graph (topological sort, acyclic)
  - Test Intent + Validation Target per slice
- Rules: One behavior per slice, safe for Red-Green-Refactor isolation
- Apply Ralph Loops (see below)

**Phase 3: Validation (Ralph Loops)**

Three autonomous validation loops, max 3-5 iterations each:

1. **Slice Size Validation Loop**
   - For each slice: count files, estimate test surface, verify Red-Green-Refactor feasibility
   - If oversized: split, adjust dependencies
   - Exit when: all slices ≤ 3 files, testable, no slice depends on > 2 others

2. **Dependency Correctness Loop**
   - Build Depends On graph, run topological sort
   - Verify: acyclic, no hidden dependencies
   - If cycle/missing dep: reorganize, re-slice
   - Exit when: acyclic, complete

3. **Research-to-Implementation Traceability Loop**
   - For each slice's "Ordered Steps": validate against research/cache.md
   - Verify: file/interface exists, constraint respected
   - If missed research: run targeted deep-read, update cache, call agent-nelly
   - If contradiction: flag as known risk in slice
   - Exit when: traceable or flagged

**Phase 4: Risk Tier Assignment**
- high-risk when:
  - design.md's Risks And Tradeoffs names a risk touching this slice's files
  - Slice is a migration (schema, API breaking change)
  - Touches multiple independent modules
  - Weak testability
- Default: standard

**Phase 5: Ready-to-Implement Check**
- Readiness checklist:
  - [ ] At least one concrete phase exists
  - [ ] Each phase has objective, Risk Tier, steps, test intent, validation target
  - [ ] Slices are safe for TDD (≤ 3 files, acyclic dependencies)
  - [ ] No unresolved blocker
  - [ ] State: Ready For Implementation

**Escalation Paths Back to agent-isdd:**
- Research gap too large: pause, provide specific files needing research
- Design contradicts research: pause, surface contradiction (design-author fixes)
- Slicing requires product decision: pause, ask user which strategy
- High-risk slice cannot be split: pause, confirm oversized + high-risk acceptable

**Handoff Report Format:**
```
Verdict: ready | paused (with specific reason)
Phase breakdown: 1-line summary
Tasks file path: tasks/tasks.md
Slicing confidence: high | medium (if research feels incomplete)
Ralph Loops results: all passed | <loop name> iteration X of max
```

**After Tasks readiness passes:**
- If verdict == `ready` and no slice is `high-risk`: proceed to Red-Green-Refactor per slice
  directly (existing agent-tdd behavior, unchanged).
- If verdict == `ready` and one or more slices are `high-risk`: stop and hand back the report
  (naming them) instead of proceeding — see "Exception — Test-Author Gate" above for the full
  contract. This is not an escalation/pause in the sense of the paths below (nothing is wrong;
  the plan is fine); it's a different reason to return, requiring `test-author` output before
  implementation can start.
- If verdict == `paused`: return reason; user re-enters agent-isdd to address it.
- Do NOT proceed to implementation until readiness checklist fully passes, and (when
  applicable) until the Test-Author Gate has been satisfied.

**Design Spec completeness gate**: `hooks/design_spec_gate.py` (`PreToolUse`, matcher `Agent`,
scoped to `subagent_type: agent-tdd:agent-TDD`) hard-denies the spawn unless the active
feature's `requirements.md` and `design.md` are both `State: Approved` on disk — modeled on
`hooks/memory_permission.py`'s pattern, replacing the retired `slice_spec_gate.py` (which
validated a different, incompatible schema and was never wired into `hooks.json` for this
handoff path). Read-only; never mutates state; falls through with no decision when no SDD
workflow is active at all.

**Availability check**: unlike `agent-nelly`, which is checked eagerly at `before-requirements`
and cached in `workflow-state.json` because it is used throughout the workflow, `agent-tdd` is
only needed once — at the handoff. Check availability inline at that point by scanning the
current session's `<system-reminder>` agent-types block for the string `agent-tdd:agent-TDD`.
No caching or `workflow-state.json` field is needed. If absent, pause with a concrete,
actionable message (e.g. "agent-tdd is not installed in this session — install it before
requesting implementation") rather than attempting the work internally.

**Fallback — Direct Implementation (harness `Agent`-spawn failure)**: distinct from
"`agent-tdd` not installed" above, this covers the case where `agent-tdd:agent-TDD` *is*
installed but every attempt to spawn it fails at the tool-call layer itself — a genuine Claude
Code harness bug, not something a differently-worded prompt, a retry, or a different spawn
call-site can work around. First confirmed 2026-09-15 on the `2026-09-15-expand-error-logger`
feature (see that feature's `workflow-state.md` for the full investigation trail): a PreToolUse
hook rejected the `Agent` call with `"description type expected as string but provided as
unknown"`, traced conclusively to the harness itself — no currently-enabled hook in any
installed plugin was producing that `updatedInput`, and the failure reproduced identically for
a plain `claude` agent type unrelated to `agent-tdd`, meaning it blocks *all* `Agent`-tool spawns
in the affected session, not something specific to this handoff.

**Detection** — treat the spawn as harness-blocked, not a one-off flake, only once **all** of
these hold:
1. The `Agent` call fails with a `PreToolUse` schema-validation error on the tool call itself
   (not an error returned *by* the spawned agent).
2. A repeat attempt with the same Design Spec reproduces the identical error text.
3. A trivial `Agent` spawn to an unrelated agent type (e.g. plain `claude`) in the same session
   also fails the same way — confirming it's session/harness-wide, not specific to
   `agent-tdd:agent-TDD` or to this feature's Design Spec content.

Do not retry blind beyond this. If a later `/isdd-continue` session re-hits a rollback or
escalation that traces back to this same blocker, check for a harness fix first (retry once)
rather than repeating the full investigation.

**Fallback action** — once confirmed harness-blocked, `agent-isdd` (or whichever skill/session is
driving) invokes `agent-tdd:design-spec-direct`
(`agent-tdd/skills/design-spec-direct/SKILL.md`) via the `Skill` tool, never `Agent` — that skill
exists specifically because a `Skill` call is not subject to this harness bug. It reproduces
Design Spec Mode's Research Validation/Task Slicing/Ralph Loops/Risk Tier Assignment (its `plan`
sub-mode) and Slice Spec Mode's per-slice Red/Green/Review/Refactor contract (its `test-author`/
`slice`/`refactor` sub-modes), one slice at a time, with `agent-isdd` itself owning the loop
instead of trusting an isolated subagent to run it unsupervised:

1. Call `plan` once → `tasks.md` + readiness verdict. Escalate exactly as a real `agent-TDD`
   spawn would on a `paused` verdict.
2. For each slice in dependency order: if `high-risk`, call `test-author <slice-id>` first
   (passing only Task description/Test Intent/Data Contracts — see that skill's own prompt-
   hygiene rule for why), then call `slice <slice-id>` → "Implementation Complete" handoff
   (Red confirmed, Green done, Refactor still pending).
3. Review that slice's touched files via the `code-reviewer` skill (the same Review Gate this
   handoff would otherwise require — see "Auto Code-Reviewer Invocation" below).
4. No blocking finding → call `refactor <slice-id>`, mark the slice done, advance to the next
   slice. Blocking finding → pause on this slice; do not call `refactor` and do not advance.
5. Once every slice is `done`, call `summary` → final handoff. Run the full regression suite
   (not just new tests) and confirm no unrelated pre-existing failures were introduced.
6. Record in `workflow-state.md`: that this was a direct-implementation fallback (not a normal
   `agent-tdd` handoff), the harness bug's signature and detection evidence, and the review/
   regression results — so a later session doesn't mistake "implemented directly" for "never
   implemented" or re-attempt an already-fixed handoff blindly. Persist per-slice progress in
   `direct-mode-state.json` (see `design-spec-direct/SKILL.md`'s "Caller-owned loop" section) so
   a session restart mid-loop resumes at the right slice.

This preserves the *procedural* shape of test-author's isolation (a test written before its
implementer commits to an approach) and every per-slice review checkpoint a real spawn would
have — see that skill's "What is genuinely lost" section for what a `Skill` call cannot
replicate (true context isolation, agent-enforced loop prevention) even with this structure.

This is a fallback, not a preferred path — always attempt the real `agent-tdd:agent-TDD` spawn
first on every fresh attempt at this handoff; only fall back once Detection's three conditions
are all met for *that* attempt.

## ← agent-tdd / code-reviewer (rollback request)

Sometimes `agent-tdd`'s Green→Refactor review pause (or `code-reviewer`) discovers that the
*task* itself — not just the implementation — was wrong. There is no cross-plugin IPC to build
a live push channel for this, so the return path is a documented marker convention plus a
check `agent-isdd` performs on its own re-entry, not agent-isdd reaching into `agent-tdd`'s
active loop. Two genuinely different marker formats feed two different paths below — this used
to be documented as one marker with two delivery paths, which was wrong: `agent-tdd` never emits
SDD-specific vocabulary (see its own `INTEROP.md`), so it cannot literally emit the human-relay
marker below itself. That was a real gap, not just a documentation gap — closed by giving
`agent-tdd` its own generic marker instead of assuming it would speak agent-isdd's.

**Automatic path** (agent-tdd's own generic signal): `agent-tdd`'s **Plan Validity Flag** (see
`agent-tdd/INTEROP.md`'s section of the same name) is a caller-agnostic marker —
`<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` — with no target phase, since `agent-tdd` has no
concept of agent-isdd's phase vocabulary. When `agent-tdd:agent-TDD`'s spawn report contains it,
`hooks/subagent_report.py`'s `SubagentStop` handler recognizes it (independently of its normal
narrative-report capture, which excludes implementation-phase reports otherwise), defaults the
rewind target to `Requirements` — per `references/rollback-guide.md`'s existing "Which target
phase to name" policy: an unclear or absent target defaults to the more conservative (earlier)
phase, since it's always safer to re-confirm a phase that may have been fine than to skip past
one that actually needs revision — and writes `rollback_pending` to `workflow-state.json` plus a
`Pending Rollback Request` line to `workflow-state.md`, with the reason text tagged so a later
reader (or `workflow-manager`'s own "Rollback Request Intake," which reads the reason and can
re-target forward per its documented rule) knows `Requirements` was defaulted, not derived from
the reason. The next `before-continue` hook checks for it first and routes into the Rewind
Contract.

**Human-relay path** (agent-isdd's own vocabulary, for a human relaying a finding): a human (or
whichever context is driving) who already knows agent-isdd's phase names can paste this marker
directly into a message re-entering agent-isdd:

```
<!--SDD-ROLLBACK-REQUEST: target=<Requirements|Design|Tasks> reason="..."-->
```

`before-continue` recognizes it in user input the same way, when present — this is the path for
`code-reviewer`'s findings, or any `agent-tdd` resume happening via `SendMessage` in a session
agent-isdd isn't part of, since neither has an automatic hook of its own. For step-by-step
instructions on both paths, see [`references/rollback-guide.md`](references/rollback-guide.md).

Do not treat either path as a fully automatic guarantee on its own: the automatic path only
fires when `agent-tdd` actually raises a Plan Validity Flag on its *initial* spawn report (not
on a later `SendMessage` resume, which this hook does not observe), and only ever targets
`Requirements` by default — human-relay remains the only path with an explicit target, and the
only path for `code-reviewer` altogether.

## → code-reviewer (review gate)

The agent-isdd workflow layer does not invoke `code-reviewer` directly. However, agent-isdd's 
constituent skills — particularly `design-author` — invoke it at appropriate phase boundaries 
(see Strategic Review Placement below). For implementation-phase reviews, it is `agent-tdd`'s 
responsibility (per `agent-tdd`'s own `INTEROP.md`) to arrange the review gate with whichever 
context is driving implementation after the handoff above.

## → agent-ux (UX rendering)

At every phase transition, section-confirmation checkpoint, review-dashboard threshold, and
out-of-scope-task flag, `agent-isdd` delegates to `agent-ux:ux-agent` instead of an in-process
agent, constructing the UX Event Envelope (`caller: agent-isdd`, `event_type`, `phase_state`,
`delta`, `artifact_path`) defined in `agent-ux`'s own `INTEROP.md` — that document is the
authoritative schema (envelope shape, the five per-`event_type` delta shapes, and the
pull-over-push invariant); this section only states how `agent-isdd` uses it, not a duplicate
definition.

`agent-ux:ux-agent` is a **soft dependency**, same pattern as `agent-nelly` below: if it is not
installed or otherwise unreachable, `agent-isdd` catches the missing-plugin condition, surfaces
one plain notice for the session (not one per event), and continues without blocking — see
`agent-ux`'s `INTEROP.md` "Unavailability and fallback contract" section for the full generic
contract (including its own internal fallback when a specific rendering tool like `Artifact` is
unavailable), referenced here by name rather than restated.

The `TaskCreate`/`TaskUpdate`/`TaskList` checklist is not part of this delegation — `agent-ux`'s
isolated subagent context cannot reach deferred tools, so the calling skill renders/refreshes the
checklist directly, unchanged from today's local-agent behavior.

## → agent-nelly (memory)

Before starting or continuing meaningful phase work, `agent-isdd` delegates to
`agent-nelly:agent-nelly` for a goal-aware brief — nelly's four output sections are
`Intent`, `Relevant entries`, `Intent alignment`, and `Written`; agent-isdd uses `Intent` to
seed/check the feature's `Goal` field, and `Intent alignment` as the divergence signal — rather
than reading `~/.claude/sdd-memory/` cross-feature index files directly. If `agent-nelly` is
unavailable, agent-isdd surfaces one plain notice and continues without the Intent-alignment
check — never a hard dependency.

agent-isdd still owns writing its own per-feature `spec/` artifacts
(`workflow-state.md`/`.json`, `requirements.md`, `design.md`, `tasks.md`, `recap.md`) under
`~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/` directly — that scaffolding
(`hooks/sdd_memory.py`) is not part of what `agent-nelly` owns.

Within a continuous stretch of phase work, agent-isdd does not re-call
`agent-nelly:agent-nelly` on every step once a brief has already been fetched and is
still visible in context — it reuses the in-session brief instead. The full re-fetch-trigger
convention lives in `skills/spec-driven-development/SKILL.md`'s Goal-Aware Memory section (this
is a documentation pointer, not a duplicate definition). `workflow-state.json` is intentionally
unchanged by this dedup convention — it carries no brief-caching field.

**Write-back during spec phases**: at each `after-*` hook (`after-requirements`,
`after-design`, `after-tasks`), when `agent_nelly_available` is `true`, agent-isdd calls
`agent-nelly:agent-nelly` with a `new facts` batch containing any project-level
discoveries worth persisting across future sessions — for example: interface assumptions
confirmed or denied during requirements, coverage gaps or unexpected interfaces found during
design research, risk flags raised. The criterion is "would a future conversation benefit from
knowing this independently of this feature's own artifacts?" — ephemeral workflow state (user
confirmed step N, phase advanced) never qualifies. Choose the call shape by content: a positive
discovery (a confirmed interface, a constraint, a risk) is a `new fact`/`new facts` batch; a
discovery that a specific approach was tried and rejected is an `error lesson` instead. If the
call fails or nelly is unavailable, log a one-line note in `recap.md` and continue — it is never
a blocking condition.

**[Phase 2+3] File-level cache via `new facts` batches**: after `research-consolidator` completes
during Design phase, `design-author` extracts `file_summaries` from the research output and
persists them to agent-nelly via a `new facts` batch with type: `"file_summary"`. Schema per
summary:

```json
{
  "type": "file_summary",
  "path": "src/api/client.ts",
  "summary": "HTTP client wrapper with retry logic",
  "exports": ["class ApiClient { request() }", "function retry<T>(...)"],
  "constraints": ["Singleton: initialized once", "Not re-entrant"],
  "tech_debt": ["Retry backoff hardcoded"],
  "dependencies": ["axios", "events"],
  "test_surface": ["Mock ApiClient.request()", "Test retry behavior"],
  "migration_risks": ["Request state cached; changes to error handling must clear cache"],
  "git_hash": "abc123def456",
  "touched_by": [{"feature": "payment-flow", "date": "2026-08-22"}]
}
```

Agent-nelly caches file summaries in `~/.claude/agent-nelly-memory/<project>/files/<slug>.json`
for cross-feature reuse. When `agent-isdd` needs file context during a later feature (Design
phase or agent-tdd slicing phase), it queries agent-nelly for cached summaries by file path;
agent-nelly returns cache hits with git_hash validation and cache misses.

Agent-nelly's file cache is optional and transparent to agent-isdd: if unavailable, agent-isdd
continues without pre-loaded file context (slower, but correct). The integration assumes
agent-nelly:agent-nelly supports:
- `type: "file_summary"` in `new facts` batches (storage)
- A query interface to retrieve file summaries by path (retrieval, with git_hash validity check)

This is documented here as the contract both plugins can cross-check; agent-nelly's own `INTEROP.md`
is authoritative for its side of the contract.

## → agent-cache-plugin (no direct integration)

agent-isdd does **not** exchange any data with agent-cache-plugin directly, and never has.

Until 0.1.48, `hooks/cache_hook.py` and `hooks/ux_render.py` POSTed phase state to an
agent-cache-plugin HTTP server on `localhost:7771`. That server never existed — agent-cache-plugin
has no `bin` entry and no listener anywhere — so every request failed and was swallowed as
"graceful degradation". 0.1.49 removed the HTTP code; 0.1.50 removed `cache_hook.py` entirely.
`ux_render.py` now renders the breadcrumb straight from `workflow-state.json` (the source of
truth for phase state) and never emits a `phase_transition` delegation — the
`spec-driven-development` skill does that itself at every phase change.

**What agent-cache-plugin does for agent-isdd anyway**: its automatic `PreToolUse`/`PostToolUse`
hooks on the `Agent` tool cache every subagent output in the session (including agent-isdd's
`planning-agent`, `research-consolidator`, `spec-reviewer` spawns) with no caller action — see
agent-cache-plugin's `STRUCTURE.md` → "Capabilities" → `agent_output_cache`. That is the only
integration surface, and it needs nothing from this plugin.

**Why no explicit integration**: agent-cache-plugin's other surfaces — two subagents reachable
only via the `Agent` tool, CLI commands with no store/retrieve verb, and a Node-only in-process
JS API — are not callable from a Python hook process. If a reachable transport ever appears,
wire it as a new module in `hooks/subagent_dispatch.MODULES` between `subagent_report` and
`ux_render`.

---

## Strategic Review Placement via Review Levels (Current Approach)

The tiered review-level feature (Quick/Standard/Deep/Ultra) provides the design pattern for 
strategic review placement across ISDD phases. Rather than hooks managing invocation, 
callers (agent-tdd, spec-driven-development skills) invoke `/code-reviewer` directly at the 
appropriate level for each phase context. This is simpler, debuggable, and respects the 
harness constraint that hooks cannot invoke skills.

| Phase | Review Level | Purpose | When | Invoked By |
|-------|--------------|---------|------|-----------|
| Design | Deep | Coherence validation | After design complete, before Tasks | design-author (agent-isdd skill) |
| Tasks | Standard | Clarity check | After task slicing, before implementation | task-slicer (agent-tdd internal) |
| Per-Slice (Green) | Standard or Deep | Implementation check | After slice passes tests | agent-tdd (Deep if high-risk) |
| Coherence Review | Deep or Ultra | Cross-slice validation | After all slices complete | agent-tdd (Ultra if >50% high-risk) |

### Ralph Loops Integration

Review findings feed into ralph loops validation at multiple checkpoints:

- **Design-phase Deep review** → Traceability validation input: does design.md touch the right files?
- **Tasks-phase Standard review** → Dependency Correctness loop: are task dependencies valid?
- **Per-slice Standard review** → Per-slice correctness: implementation matches slice requirements
- **Coherence review (Deep/Ultra)** → Cross-slice Traceability validation: did all slices co-evolve correctly?

Each review level produces findings appropriate to its scope; ralph loops' Traceability validation 
then confirms that design-level decisions were respected through implementation.

### Auto-Detection Rules

Auto-detection of review level lives in **calling code** (agent-tdd, spec-driven-development), 
not in hooks or `code-reviewer` itself. Callers apply these rules (in priority order) when 
invoking `/code-reviewer`:

1. Explicit request (caller-specified `review_level`)
2. ISDD workflow phase (Requirements → Standard, Design → Deep, Tasks → Standard, Implementation → context-dependent)
3. Risk tier (high-risk slices → Deep, standard → Standard)
4. File scope (single function → Quick, single file → Standard, multiple → Deep)
5. Fallback: Standard

This keeps review-level selection close to the context that motivated it, rather than trying 
to infer it from static configuration.
