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

- **Task description** (required) — the behavior to implement, plain language.
- **Acceptance criteria / Test Intent** (required) — the observable behavior a test must pin
  down. If you can't state this yet, don't spawn the agent — it will stop and report the gap.
- **Risk Tier** (optional, default `standard`) — `standard` or `high-risk`. Drives whether the
  test-author split applies.
- **Data Contracts And Interfaces** (optional) — type signatures, module boundaries, API shapes
  you already know. Skip it if you don't have this; the agent will explore the codebase itself.
- **Pre-Slice Brief** (optional) — prior project context you already gathered (e.g. from a
  memory subagent like `agent-nelly`). Purely additive — omitting it is not an error.
- **Review handoff mode** (optional) — leave unset for the default (mandatory pause after Green).
  Set explicitly to "skip" only when you have deliberately decided no review step will happen
  this session.

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

What you do with that pause is up to you:

- Run your own reviewer (a `code-reviewer`-style agent, a lint pass, a human) scoped to the files
  `agent-TDD` named in its handoff.
- Resume the same `agent-TDD` instance (e.g. via `SendMessage` to its agent id) once review
  clears, telling it to proceed to Refactor. If your reviewer surfaced a blocking finding, pass
  that back on resume — `agent-TDD` will not proceed to Refactor until it hears the finding is
  resolved.

If you genuinely have no reviewer available this session, that's a deliberate choice you make
explicit via Review handoff mode — not a silent default.

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

## Design Spec Mode (agent-isdd integration, Phase 2+3 revised)

Agent-tdd optionally accepts a **Design Spec** as an alternative to Slice Spec mode. This mode is
for orchestrators like `agent-isdd` that hand off full Design specs (requirements + design + research
cache) and need agent-tdd to:

1. **Validate research completeness** (are design file-touchpoints in the cache?).
2. **Slice the design into TDD-ready phases** (produce tasks.md with phased, testable slices).
3. **Apply Ralph Loops validation** (size, dependency, traceability).
4. **Implement all slices end-to-end** (Red-Green-Refactor per slice, no return until complete or escalation).

### Design Spec Input Format

Pass a **Design Spec** inline in the spawn prompt:

- **requirements.md** (full, approved) — user stories and acceptance criteria.
- **design.md** (full, approved) — file touchpoints, interfaces, research basis section.
- **research/cache.md** — design_findings, task_findings, file_summaries, git_hashes from prior
  research consolidation.
- **recap.md** (optional) — summary, known risks, blockers, Goal alignment notes.
- **Pre-fetched file summaries** (optional) — cached context keyed by file path (from agent-nelly
  or prior deep-reads).

### Research Validation Phase

Agent-tdd validates:
- Are design.md's file touchpoints present in research/cache.md?
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

Before proceeding to per-slice implementation, `readiness-check` agent emits a **Readiness Check** verdict:
- ✓ **Ready For Implementation** — tasks.md is final, proceed to Red-Green-Refactor per slice.
- ✗ **Paused** — escalate with specific reason (research gap, design contradiction, slicing
  blocker, etc.). Caller (agent-isdd) pauses; user re-enters and addresses the reason.

**Marker Emission:** When verdict = `paused`, readiness-check emits:
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

### Per-Slice Implementation (after Readiness)

Once Readiness Check passes, agent-tdd iterates through tasks.md:
- For each slice: Plan → Red → Green → (mandatory review pause) → Refactor → Validate.
- High-risk slices: caller spawns test-author first; agent-tdd takes that test as Red.
- Standard slices: agent-tdd writes Red itself.
- **No return to caller** until all slices complete (except escalations).

### Design Spec Handoff Report

**After Research Validation + Task Slicing (before per-slice implementation):**

Emit phase marker: `<!--AGENT-TDD-PHASE:slicing_complete-->`

Provide:
- Research Validation summary (findings, gaps if any).
- Task Slicing summary (count, distribution).
- Ralph Loops status (all passed / which loop, iteration N of max).
- Risk Tier distribution (high-risk count vs. standard).
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
initial spawn. Task slicing happens inside agent-tdd (not handed back to agent-isdd). Escalations
back to agent-isdd (research gap, design contradiction, slicing blocker) pause with explicit reason;
agent-isdd resumes via its `before-continue` hook when user re-enters after addressing the escalation.
