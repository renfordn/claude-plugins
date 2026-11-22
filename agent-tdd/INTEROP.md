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
| Model Tier | enum (inherit \| haiku \| sonnet \| opus) | no | Model for this slice; the caller passes it as the `Agent` tool's `model` parameter. `sonnet` for implementation, `haiku` only for trivial changes. Default: sonnet |
| Data Contracts And Interfaces | object | no | Type signatures, module boundaries, API shapes you already know. Skip if you don't have this; the agent will explore the codebase itself |
| Pre-Slice Brief | object | no | Prior project context you already gathered (e.g. from a memory subagent like agent-nelly). Purely additive — omitting it is not an error |
| Review handoff mode | enum (skip) | no | Leave unset for the default (mandatory pause after Green). Set explicitly to "skip" only when you have deliberately decided no review step will happen this session |
| Slice id / Owned files / Base commit | string / string[] / sha | no | Parallel delivery (`sliceId`, `ownedFiles`, `baseCommit`): worker verifies the base is an ancestor, edits only owned files, echoes `<!--SLICE-ID: N-->` |

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

## Test-strategist (optional, before planning tests)

`test-strategist` is a read-only agent that answers "which tests does this change actually need?"
before `test-author` or `agent-TDD` writes any. Spawn it from the main thread with an **Area**
(files, module, feature, or "whole suite"), and optionally the **Planned change** (behaviors with
acceptance criteria) and **Constraints**. It returns a report starting with
`<!--TEST-STRATEGY-REPORT-->`: existing coverage across levels, a per-behavior decision
(covered / extend / modify / new at the cheapest catching level) with a Red check per planned
test, a "Pins checked (mutation)" table proving its load-bearing claims in a throwaway copy,
consolidation candidates that name the surviving test, measured speed and parallelism fixes, and the narrowest validation
command.

How to use the report: put "covered" behaviors nowhere, turn "extend"/"modify" decisions into the
Slice Spec's Test Intent ("add a case to `<test>`"; a test whose mutation survived is a "modify"),
pass the chosen Test Level and validation
command through, and put any consolidation or deletion to the user as its own step outside
`agent-TDD`'s Red/Green/Refactor. `test-budget` remains the quick per-file pre-flight; use
`test-strategist` when the change spans files or levels, when a bug escaped existing tests, or
when the suite is slow.

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

## Resumed reports and stalled agents

- **Ask for plain-text reports on resume.** A hand-back tool (e.g. `SubagentHandback`) accepts
  one report per result, so a resumed agent's second hand-back is refused. When you resume
  `agent-TDD`, `test-author` or `code-reviewer` via `SendMessage`, add "return your report as
  your final plain-text response". If a hand-back was refused anyway, or no report arrives,
  rebuild the state from the worktree (`git status`, `git diff`), `git log`, the slice's
  `tdd_check.py` evidence log and test logs, never from memory of earlier reports.
- **Detect stalls; don't wait silently.** A background subagent can stop "waiting on background
  work" and sit idle for hours. While one runs, check it every ~20 minutes:

  ```
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agent_stall.py" --agent-id <agent id> --idle-minutes 20
  ```

  It compares the transcript's last timestamp with now and lists the agent's background Bash
  commands still running (flagging self-matching `pgrep -f` waits). Exit 3 (`stalled`): resume the
  agent with a status-check message ("report what you are waiting on; rerun it in the
  foreground"), killing any listed self-matching wait loop, or tell the user. Exit 4 (`idle`, no
  background work): it has probably finished; read its report or fall back as above. Exit 0:
  still active. Without the script, do the same by hand: compare the transcript's last
  `timestamp` with now, and check `ps` for its background commands.
- `hooks/wait_loop_guard.py` (PreToolUse Bash) denies any `pgrep -f` / `pkill -f` whose pattern
  matches the command itself, the cause of the multi-hour stalls.

## Keeping spawn prompts token-efficient

Both agents run in an isolated context and pay for every token you put in their spawn prompt —
padding it with more than the slice needs is pure waste, not safety margin. Concretely:

- **Data Contracts And Interfaces: exact excerpts, scoped to this slice.** A few lines of the
  signature(s) the criteria touch, not whole files; the agents have `Read`/`Grep`/`Glob`.
- **Don't restate the Slice Spec when resuming.** Send only the review outcome ("cleared,
  proceed to Refactor" or the blocking finding).
- **Omit optional fields you don't have** rather than inventing placeholders.
- **`test-author` gets a strict subset:** Task description, Test Intent, Data Contracts And
  Interfaces only.

## Parallel slice delivery

With `Parallel: on` agent-TDD slices a Design Spec into disjoint-file waves (contract slice
first) and stops at `slicing_complete`; the caller fans each wave out to isolated worktrees,
passing each worker `sliceId`, `ownedFiles` and `baseCommit`. Protocol:
[`references/parallel-delivery.md`](references/parallel-delivery.md), entered via
[`commands/tdd-parallel.md`](commands/tdd-parallel.md). Review-scope contract with
code-reviewer: the caller tells each slice reviewer `Review cwd: <worktreePath>`,
`--base <baseCommit>` and `Review scope: slice=N`; code-reviewer echoes
`<!--REVIEW-SCOPE: slice=N-->` and only that slice's gate clears. Old reviewers that don't echo
the scope are unscoped: an unscoped review clears all open gates when none carries a slice id, otherwise only a sole open gate; open gates older than 24h are left out of that count but keep blocking their own agent until a scoped review or a bypass label; only reviewed gates are pruned.

## Slice discipline (R7, R8, R9, R11)

agent-TDD follows `references/slice-discipline.md`: gap discovery before Red (skipped given a `<!--TEST-STRATEGY-REPORT-->`), a mutant-proved coverage-only outcome (`<!--AGENT-TDD-OUTCOME: coverage-only-->`, still reviewed at `green_pause`), a `refactor` outcome (`<!--AGENT-TDD-OUTCOME: refactor-->`: a `refactor`/`contract` slice proven by `coverage` then `green`, reviewed as usual), a red-first edit guard with logged `bypass` (its deny text carries the slice ids; coverage unlocks only `refactor`/`contract` starts; run `done` on every early stop), and UI slices needing an E2E Red or a `<!--AGENT-TDD-BLOCKED: reason="..."-->` report (no phase marker; skip the slice and its dependents). Optional Slice Spec field `ui`. Evidence entries: `references/evidence-log.md`.

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

Full contract: [`references/design-spec-mode.md`](references/design-spec-mode.md). Sections:
- One implementation of this mode (the modular alternative was retired)
- Design Spec Input Format
- Research Validation Phase
- Task Slicing & Ralph Loops
- Readiness Check & Escalation
- Test-Author Gate (added 2026-09-16)
- Test-Budget Pre-flight (caller-side, long-running projects)
- Per-Slice Implementation (after Readiness and the Test-Author Gate)
- Design Spec Handoff Report
- One-Directional Handoff
- Direct Mode (harness `Agent`-spawn failure fallback, added 2026-09-16)

## → code-reviewer

Unlike the isdd → agent-tdd handoff above (one spawn, one big handoff report), agent-tdd's
relationship with `code-reviewer` is synchronous and per-slice, not a single end-of-phase
handoff: at each slice's Green pause `agent-TDD` stops with a Review Request (`Standard`, or
`Deep` for high-risk) and the caller runs an independent code-reviewer before resuming it; after
`all_slices_complete` it requests one `Deep` coherence review over every changed file.
