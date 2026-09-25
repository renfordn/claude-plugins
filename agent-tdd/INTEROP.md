<!-- TDD-SKIP -->
# Interoperability: Integrating Agent TDD Into Another Plugin

Agent TDD is a general-purpose strict-TDD implementation subsystem for Claude Code. It is not
specific to spec-driven-development (SDD) — SDD is simply its first real consumer. This document
is the contract for any *other* plugin author (or any orchestrating skill) who wants to use it.

Nothing below requires SDD to be installed, and nothing below is specific to SDD's concepts
(feature slugs, `tasks.md`/`design.md`, workflow phases). If you're looking for how SDD itself
uses these agents, that's an implementation detail of the SDD plugin, not part of this contract.

## The harness constraint that shapes everything here

Subagents in this harness cannot spawn other subagents — a named `Agent` tool grant in a
subagent's own frontmatter does not resolve when that subagent tries to use it (observed in past
sessions, not a documented platform guarantee; re-verify if harness behavior seems to have
changed). Concretely:

- `agent-TDD` cannot invoke `test-author` itself, even for a high-risk slice.
- `agent-TDD` cannot invoke a reviewer itself, no matter what reviewer you use.

**You — the calling skill running in the main thread — are the only actor that can invoke
`test-author` or drive the review pause.** Both agents are written knowing this; neither will try
to reach the other.

## The Slice Spec (what you pass in)

Before spawning `agent-TDD`, assemble a Slice Spec and pass it inline in the spawn prompt — there
is no file it reads on its own. A machine-checkable version of the same contract lives in
[`references/slice-spec.schema.json`](references/slice-spec.schema.json) (field names, the two
required fields, and the two enums); validate against it if you're assembling the spec
programmatically. The [`slice-spec`](skills/slice-spec/SKILL.md) skill in this plugin walks
through gathering and validating these fields by hand.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Task description | string | yes | The behavior to implement, plain language |
| Acceptance criteria / Test Intent | string | yes | The observable behavior a test must pin down. If you can't state this yet, don't spawn the agent — it will stop and report the gap |
| Risk Tier | enum (standard \| high-risk) | no | Drives whether the test-author split applies. Default: standard |
| Model Tier | enum (inherit \| haiku \| sonnet \| opus) | no | Suggested model tier for this slice based on complexity. 'inherit' uses the caller's default model. Default: inherit |
| Data Contracts And Interfaces | object | no | Type signatures, module boundaries, API shapes you already know. Skip if you don't have this; the agent will explore the codebase itself |
| Pre-Slice Brief | object | no | Prior project context you already gathered (e.g. from a memory subagent like agent-nelly). Purely additive — omitting it is not an error |
| Review handoff mode | enum (skip) | no | Leave unset for the default (mandatory pause after Green). Set explicitly to "skip" only when you have deliberately decided no review step will happen this session |

## Two-part invocation (the high-risk split)

For a `standard`-tier slice, spawn `agent-TDD` once with the Slice Spec above; it writes its own
Red test and runs straight through to its Green/pre-review handoff. See a full worked transcript
in [`references/examples/standard-tier-slice.md`](references/examples/standard-tier-slice.md).
Two related branches, each with their own worked transcript:

- **Review handoff mode explicitly set to `skip`** — no pause between Green and Refactor, single
  invocation start to finish. See
  [`references/examples/review-skip-slice.md`](references/examples/review-skip-slice.md).
- **The real code diverges from the Slice Spec's Data Contracts And Interfaces** — `agent-TDD`
  stops and raises a Research Gap Flag instead of guessing. See
  [`references/examples/research-gap-flag-slice.md`](references/examples/research-gap-flag-slice.md).

For a `high-risk`-tier slice:

1. Spawn `test-author` first, passing it the Task description, Test Intent, and any Data
   Contracts And Interfaces. Take its returned test file(s) and failure confirmation.
2. Spawn `agent-TDD`, including `test-author`'s output in the Slice Spec and telling it not to
   write its own test for that behavior. It treats that supplied test as Red and proceeds to
   Green.

See a full worked transcript of both separate invocations in
[`references/examples/high-risk-tier-slice.md`](references/examples/high-risk-tier-slice.md).

## The mandatory review pause

`agent-TDD` always stops after Green and hands back a report (see its own file for the exact
fields) rather than proceeding to Refactor — unless your Slice Spec explicitly set Review
handoff mode to skip. This is deliberate: it preserves "no unreviewed refactor" as a property of
the agent regardless of what reviewer (or non-reviewer) you have available.

What you do with that pause:

- Review the handoff's Review Request (level, scope, refactor intent) with a reviewer that is not
  `agent-TDD` and did not see its reasoning. With `code-reviewer` installed, follow its
  INTEROP.md "Independent review (reviewer ≠ author)": spawn `code-reviewer:code-reviewer`, fall
  back to its headless script if spawning fails, and label anything else `self-reviewed`. Any
  other independent reviewer (a different agent, a human) is fine too. `agent-TDD` never reviews
  itself.
- Resume the same `agent-TDD` instance (e.g. via `SendMessage` to its agent id) once review
  clears, telling it to proceed to Refactor. If your reviewer surfaced a blocking finding, pass
  that back on resume — `agent-TDD` will not proceed to Refactor until it hears the finding is
  resolved.

If you genuinely have no reviewer available this session, that's a deliberate choice you make
explicit via Review handoff mode — not a silent default.

**The review gate enforces this** (`hooks/review_gate.py`). When `agent-TDD` stops at
`green_pause`, a `SendMessage` to that agent is denied until one of these is recorded:

- the `code-reviewer:code-reviewer` agent returned a `<!--CODE-REVIEWER-REPORT-->`, or
- code-reviewer's `scripts/review_headless.sh` printed one, or
- the resume message itself says `self-reviewed`, `review skipped`, or `reviewed by: <who>` (a
  human or another reviewer). Those resumes go through, and the label stays in the transcript.

The denial message tells the caller what to do. State lives in `review-gate.json` next to
`tdd-progress.json`. The gate covers the Green pause only, not the coherence review, and it
fails open if the hook itself errors.

## Keeping spawn prompts token-efficient

Both agents run in an isolated context and pay for every token you put in their spawn prompt —
padding it with more than the slice needs is pure waste, not safety margin. Concretely:

- **Data Contracts And Interfaces should be exact excerpts, not whole files.** Paste the specific
  signature(s), type(s), or module boundary the slice touches — a few lines, not a pasted file.
  Both agents have `Read`/`Grep`/`Glob` and will fetch anything else they actually need; the field
  exists to save them a lookup you already did, not to preload the file.
- **Scope it to this slice.** Only include contracts/interfaces the slice's acceptance criteria
  actually touch. A wider dump doesn't reduce ambiguity — it makes the one relevant fact harder to
  find in the prompt.
- **Don't restate the Slice Spec when resuming.** Resuming the same `agent-TDD` instance after the
  review pause (see above) continues its existing context — send only the review outcome/decision
  ("cleared, proceed to Refactor" or the specific blocking finding to fix), not the Slice Spec
  again.
- **Omit optional fields you don't have** (Pre-Slice Brief, Data Contracts And Interfaces) rather
  than filling them with placeholder text or speculative content — an absent field costs nothing;
  an invented one costs tokens and risks steering the agent on a guess.
- **`test-author` gets a strict subset.** Pass it only Task description, Test Intent, and Data
  Contracts And Interfaces — not Risk Tier, Pre-Slice Brief, or Review handoff mode, none of which
  it acts on.

## Plan Validity Flag (optional signal that the task itself, not just the code, may be wrong)

`agent-TDD`'s handoff report may include a **Plan Validity Flag** field, marked with a literal
`<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` line immediately after the phase marker, only when Red,
Green, or the review pause revealed that the *task* conflicts with something more fundamental —
not merely a missing technical fact (that's the separate Research Gap Flag). `agent-TDD` has no
concept of your planning phases, terminology, or rewind mechanism, and never will — it states the
conflict in plain language and stops there. Interpreting and acting on it is entirely your call
as the caller.

If your ecosystem has its own "the plan needs to be redone" concept (a rewind, a re-plan request,
a ticket reopened), treat a present Plan Validity Flag as your trigger for it, using the `reason`
text to decide how far back to go. `agent-isdd` is a concrete example: its own `INTEROP.md`
documents translating this flag into its `<!--SDD-ROLLBACK-REQUEST:...-->` marker via its
`hooks/subagent_report.py` (defaulting the rewind target to its own most-conservative phase when
the reason doesn't clearly indicate a specific one, then letting its `workflow-manager` skill
re-evaluate the target against the reason text at intake) — that translation lives entirely on
`agent-isdd`'s side, not here; this plugin never emits SDD-specific vocabulary.

If you have no such mechanism, a Plan Validity Flag is safe to surface to a human and otherwise
ignore — it's advisory, never a blocking condition on its own.

## Rendering TDD-stage progress with `agent-ux` (optional)

If your ecosystem also uses the `agent-ux:ux-agent` rendering plugin and your orchestrator is the
one resuming/monitoring an `agent-TDD` instance across its stages (Plan → Red → Green → Review →
Refactor → Validate) — `agent-TDD` itself never can be, having no `Agent` tool (see "The harness
constraint" above) — you may construct a `phase_transition` envelope yourself at each stage
boundary you observe from `agent-TDD`'s reports (its `<!--AGENT-TDD-PHASE:...-->` marker, plus
your own knowledge of which stage just started), using **your own plugin's identity** as the
envelope's `caller` (never `agent-tdd` — this plugin can't be a caller, since it never invokes
anything), and a `phase_state` of the form `TDD:<stage>` (e.g. `TDD:green`). Per `agent-ux`'s own
`INTEROP.md`, any `phase_state` matching that `TDD:` prefix is excluded from chapter marking
regardless of `caller` — only the breadcrumb renders — so you don't need a caller-specific rule of
your own to get that behavior; `agent-ux` already applies it based on the phase_state shape alone.

This is genuinely optional and orthogonal to everything else in this contract — omitting it costs
you TDD-stage visual progress, nothing else. No plugin in this ecosystem does this today (`SDD`'s
own handoff is deliberately one-directional and doesn't monitor past the initial spawn — see
`agent-isdd`'s own `INTEROP.md`); this section exists so a *different* orchestrator that does want
to drive the full loop has a documented recipe rather than having to invent one.

## Handoff Facts (optional memory integration)

Neither agent has an `Agent` tool or any file-based memory store of its own. If your ecosystem
has a memory subagent, mention it in the Pre-Slice Brief and read the **Handoff Facts** field in
`agent-TDD`'s report for anything worth persisting (ownership discovered, weak coverage found, a
behavior/interface change made) — writing it back is your responsibility, not the agent's.

The same applies to the **File Summaries** field (see `agents/agent-TDD.md`'s section of that
name) — `agent-TDD` reports `{path, summary, git_hash}` items for any file it read during
slicing/implementation that the Design/Slice Spec's pre-fetched summaries didn't already cover;
your orchestrator persists them to your memory subagent (e.g. agent-nelly's `file summaries`
field) alongside Handoff Facts. `agent-isdd`'s implementation-handoff does exactly this — see its
`skills/spec-driven-development/references/implementation-handoff.md`.

## Design Spec Mode (agent-isdd integration, Phase 2+3 revised)

Agent-tdd optionally accepts a **Design Spec** as an alternative to Slice Spec mode. This mode is
for orchestrators like `agent-isdd` that hand off full Design specs (requirements + design + research
cache) and need agent-tdd to:

1. **Validate research completeness** (are design file-touchpoints in the cache?).
2. **Slice the design into TDD-ready phases** (produce tasks.md with phased, testable slices).
3. **Apply Ralph Loops validation** (size, dependency, traceability).
4. **Implement all slices end-to-end** (Red-Green-Refactor per slice, no return until complete or escalation).

### One implementation of this mode (the modular alternative was retired)

**Added 2026-09-15, documenting existing (undocumented) drift; retired 2026-09-16.** Steps 1–3
above used to exist as two separate, independently-maintained implementations in this plugin,
discovered as undocumented drift and then removed once neither documentation nor any real caller
justified keeping both:

`agent-TDD` itself performs Research Validation, Task Slicing, all three Ralph Loops, Risk Tier
Assignment, and the Readiness Check as its own instructions (see `agents/agent-TDD.md`'s "Design
Spec Workflow" section) — a single spawn of `agent-TDD` with a Design Spec does the entire
pipeline through to implementation. This is the only path there has ever been a real caller for:
`agent-isdd`'s `spec-driven-development` skill spawns `agent-tdd:agent-TDD` directly, and this is
the only source of the `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` marker (see "Plan Validity Flag"
above) and `<!--AGENT-TDD-PHASE:...-->`.

A second, modular implementation (`skills/design-spec/SKILL.md`, orchestrating five separate
subagents — `research-validator`, `task-slicer`, `ralph-loops`, `risk-assign`, `readiness-check`,
one phase each) existed alongside it, emitting its own incompatible escalation-marker vocabulary
recognized only by `plugin-harness`'s `SubagentStop` hook, never by `agent-isdd`'s own
`hooks/subagent_report.py`. No known caller ever invoked it — `agent-isdd` always bypassed it in
favor of the inline path above — so it was removed rather than kept as a documented-but-dead
alternative. If you want its per-phase token-accounting/resume-caching behavior back, that's a
fresh design decision, not something to resurrect from `git log`.

### Design Spec Input Format

Pass a **Design Spec** inline in the spawn prompt (exact field names required for plugin-harness validation):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requirements_md | string | yes | Full approved requirements.md with user stories and acceptance criteria |
| design_md | string | yes | Full approved design.md with file touchpoints, interfaces, research basis section |
| research_cache | object | yes | Research findings: design_findings, task_findings, file_summaries (keyed by path), git_hashes |
| recap_md | string | yes | Summary, known risks, blockers, Goal alignment notes (summarized, not full history) |
| nelly_brief_cache | object | no | Pre-fetched cached context from agent-nelly (if available) |

**modelPreference (capability metadata, not a spawn-prompt field):** plugin-harness's
`CapabilityMap` records `{"min_tier": "haiku", "preferred_tier": "sonnet"}` against this
capability (`agent-tdd`'s `design_spec_slicing`) — task slicing and Ralph Loop validation are
judgment-heavy enough to warrant at least `haiku`, with `sonnet` preferred. This is advisory
metadata `plugin-harness` uses to resolve a suggested model tier (via
`CapabilityMap.get_available_models()` / `resolve_model_tier()`), not something a caller sets
when spawning `agent-TDD` directly — see the Slice Spec's `modelTier` field above for the
per-slice caller-facing equivalent.

### Research Validation Phase

Agent-tdd validates:
- Are design.md's file touchpoints present in research_cache?
- Are interfaces and constraints documented?
- Any obvious gaps (a file touched but not researched)?

**Decision:**
- ✓ **Research thorough** → proceed to Task Slicing.
- ✗ **Research thin** → escalate with specific files/areas needing targeted research.
- ✗ **Design contradicts research** → escalate with the specific contradiction.

Agent-tdd does **not** attempt re-research itself — it identifies gaps precisely and escalates to
the caller (agent-isdd owns the research-consolidation loop for targeted re-research).

### Task Slicing & Ralph Loops

Agent-tdd produces **tasks.md** (see `references/tasks-schema.json`) with:
- Phased, TDD-sized slices (one behavior per slice, ≤ 3 files per slice ideally).
- Risk Tiers (standard or high-risk).
- Depends On graph (topological order, acyclic).
- Test Intent + Validation Target per slice.
- Ordered Steps (concrete, grounded in research).

Agent-tdd validates via three Ralph Loops (max 3–5 iterations each):
1. **Slice Size Validation** — all slices ≤ 3 files, testable.
2. **Dependency Correctness** — acyclic, no hidden dependencies.
3. **Research-to-Implementation Traceability** — steps match cache, constraints respected.

### Readiness Check & Escalation

Before proceeding to per-slice implementation, `agent-TDD` itself emits a **Readiness Check**
verdict as part of its own instructions (see `agents/agent-TDD.md`'s "Phase 5: Readiness Check"
— corrected 2026-09-16; this used to name a separate `readiness-check` agent, a leftover
reference to the retired modular pipeline described above):
- ✓ **Ready For Implementation** — tasks.md is final. If no slice is `high-risk`, proceed
  directly to Red-Green-Refactor per slice. If one or more slices are `high-risk`, stop instead
  and hand back the report — see "Test-Author Gate" below; this is a distinct reason to return,
  not the `Paused` verdict below (nothing about the plan is wrong).
- ✗ **Paused** — escalate with specific reason (research gap, design contradiction, slicing
  blocker, etc.). Caller (agent-isdd) pauses; user re-enters and addresses the reason.

**Marker Emission:** When verdict = `paused`, `agent-TDD` emits:
```
<!--AGENT-TDD-PLAN-FLAG:reason="<specific blocker reason>"-->
```
The caller's SubagentStop hook (e.g., `agent-isdd`'s `subagent_report.py`) captures this marker and translates it into its own escalation mechanism (e.g., `<!--SDD-ROLLBACK-REQUEST:...-->`), triggering the appropriate rewind phase.

**Escalation paths:**
- Research gap: "File `src/api.ts` not in cache; needs interface review."
- Design contradiction: "Design assumes `User.role` but schema has `User.permissions`."
- Slicing blocked: "Tasks 3 and 4 cannot be split without breaking acyclic dependency."
- High-risk unsplittable: "Slice is 5 files + high-risk; confirm acceptable or refactor design."

For comprehensive escalation documentation including Mid-Slice Research Request, Plan Validity Flag, and
detailed resume mechanisms, see [`references/escalation-paths.md`](references/escalation-paths.md).

### Test-Author Gate (added 2026-09-16)

Every slice's Risk Tier is already known by Readiness Check (Phase 4, Risk Tier Assignment,
runs before this) — so a high-risk slice's need for `test-author` is never actually discovered
mid-pipeline, it's known upfront. When Readiness Check passes with one or more `high-risk`
slices in `tasks.md`, `agent-TDD` stops at the `slicing_complete` handoff (see *Design Spec
Handoff Report* below — its **High-Risk Slices** field names them) instead of proceeding to
implementation, and awaits resume — the exact same "stop, hand back a report, await
caller-driven resume via `SendMessage`" shape as *The mandatory review pause* above, not a new
mechanism. The caller spawns `test-author` once per named slice, bundles the results, and
resumes the same `agent-TDD` instance with them. Zero high-risk slices: no pause, proceed
straight through exactly as before this gate existed.

This replaces an earlier, abandoned approach (a caller-side marker,
`AGENT-TDD-TEST-AUTHOR-NEEDED`, briefly added and then removed the same day, once it became
clear no marker was needed — the existing `slicing_complete` marker plus `tasks.md` already on
disk are sufficient for the caller to detect the condition without `agent-TDD` needing to say
anything new).

### Per-Slice Implementation (after Readiness and the Test-Author Gate)

Once Readiness Check passes and (if applicable) the Test-Author Gate above has been satisfied,
agent-tdd iterates through tasks.md:
- For each slice: Plan → Red → Green → (mandatory review pause) → Refactor → Validate.
- High-risk slices: use the test supplied via the Test-Author Gate above as Red.
- Standard slices: agent-tdd writes Red itself.
- **No return to caller** until all slices complete (except escalations). The Test-Author Gate
  above is not an exception to this — it happens *before* per-slice implementation begins, not
  during it.

### Design Spec Handoff Report

**After Research Validation + Task Slicing (before per-slice implementation):**

Emit phase marker: `<!--AGENT-TDD-PHASE:slicing_complete-->`

Provide:
- Research Validation summary (findings, gaps if any).
- Task Slicing summary (count, distribution).
- Ralph Loops status (all passed / which loop, iteration N of max).
- Risk Tier distribution (high-risk count vs. standard).
- **High-Risk Slices** — the exact slice names/ids that are `high-risk`, or "none". What the
  Test-Author Gate above actually acts on; the distribution count alone isn't enough.
- Readiness Verdict (ready for implementation / paused with reason).
- tasks.md file path.
- Handoff Facts (constraints, test surfaces, migration risks, etc.).

**Per-slice reports (during implementation):**

Standard Slice Spec mode reports (green_pause / refactor_complete).

**Final report (all slices complete):**

Emit phase marker: `<!--AGENT-TDD-PHASE:all_slices_complete-->`

Provide:
- Slicing Summary (total slices, distribution, risk tiers).
- Implementation Summary (files changed, test coverage, refactors).
- Validation Summary (test suites run, coverage metrics, unvalidated areas).
- Risks and Follow-ups (tech debt, testing gaps).
- Handoff Facts (final discoveries worth persisting).

### One-Directional Handoff

This is a **one-directional handoff** — agent-isdd does not resume or monitor agent-tdd past the
initial spawn, with one scoped exception: the Test-Author Gate above, which agent-isdd's
`spec-driven-development` skill does resume for, and only for that. Task slicing happens inside
agent-tdd (not handed back to agent-isdd). Escalations back to agent-isdd (research gap, design
contradiction, slicing blocker) pause with explicit reason; agent-isdd resumes via its
`before-continue` hook when user re-enters after addressing the escalation.

### Direct Mode (harness `Agent`-spawn failure fallback, added 2026-09-16)

Everything above this section assumes the caller can actually spawn `agent-TDD` via the `Agent`
tool. When that assumption fails — the `Agent` tool call itself is rejected at the harness level
(a `PreToolUse` schema-validation error on the call, not an error from the spawned agent),
confirmed recurring rather than a one-off flake — spawning is not available at all, and no
retry, prompt change, or call-site change fixes it. See `agent-isdd/INTEROP.md`'s "Fallback —
Direct Implementation" section for the exact three-condition Detection check.

[`skills/design-spec-direct/SKILL.md`](skills/design-spec-direct/SKILL.md) reproduces this mode's
Research Validation → Task Slicing → Ralph Loops → Risk Tier Assignment (`plan` sub-mode,
unchanged from the pipeline above, just returning to the caller instead of continuing into
implementation) plus **Slice Spec Mode's** existing per-slice contract (`test-author`, `slice`,
`refactor` sub-modes) invoked once per slice via the `Skill` tool instead of `Agent`. It
deliberately does *not* reproduce this section's "No return to caller until all slices complete"
property — a `Skill` call has no subagent isolation to make that property meaningful, so the
caller checkpoints every slice instead (Red/Green → review → decide → refactor or pause).

This is a fallback path, invoked only when the Detection conditions in `agent-isdd/INTEROP.md`
are confirmed, not a second supported way to run Design Spec Mode day-to-day. See that skill
file for the full mode contract, the caller-owned loop it expects, and what isolation guarantees
are genuinely lost (not just relocated) versus a real `agent-TDD`/`test-author` spawn.

## → code-reviewer

Unlike the isdd → agent-tdd handoff above (one spawn, one big handoff report), agent-tdd's
relationship with `code-reviewer` is synchronous and per-slice, not a single end-of-phase
handoff: `agent-TDD.md`'s "Automatic Code-Reviewer Invocation" section invokes `/code-reviewer`
after each slice's Red (Quick), Green (Standard or Deep for high-risk), and Refactor-intent
(Quick) steps, plus once more for Deep/Ultra post-slices coherence review after
`all_slices_complete`. `plugin-harness`'s `orchestrator/routing_table.json` models the
net effect of that whole per-slice loop as the single phase transition
`(agent-tdd, red_green_refactor_complete) -> code-reviewer` for its own routing-table validation
— this section exists so that route has a real handoff target to validate against, matching
what `agent-TDD.md` actually does rather than introducing a second, competing handoff shape.
