---
name: design-spec-direct
description: >
  Harness-bug fallback for Design Spec Mode. Reproduces agent-TDD's Research
  Validation, Task Slicing, Ralph Loops, Risk Tier assignment, and per-slice
  Red-Green-Refactor contract as a Skill invocation (no Agent tool) instead of
  an Agent-tool subagent spawn. Use only when agent-isdd/INTEROP.md's "Fallback
  — Direct Implementation" Detection conditions are confirmed for the current
  session — this is a fallback, not a preferred path.
---

# Design Spec Direct Mode

This skill exists for exactly one situation: `agent-tdd:agent-TDD` cannot be spawned because the
`Agent` tool call itself is failing at the harness level in this session (see
`agent-isdd/INTEROP.md`'s "Fallback — Direct Implementation (harness `Agent`-spawn failure)"
section for the three-condition Detection check — confirm all three before using this skill, on
every fresh attempt at the handoff).

It is **not** a rewrite of Design Spec Mode's autonomous multi-slice loop. Design Spec Mode
(`agents/agent-TDD.md`'s "Design Spec Workflow" section) deliberately does not return to its
caller between slices — that property depends on running as an isolated subagent that the
caller trusts to work unsupervised. A `Skill` has no such isolation: it runs inline in the same
conversation that will do the reviewing. So this skill instead reproduces **Slice Spec Mode's**
existing contract (`agents/agent-TDD.md`'s "Required workflow" + "The mandatory review pause" in
`INTEROP.md:73-90`) once per slice, and puts the caller in the same per-slice checkpoint loop it
would already be in for a normal single-slice spawn — just called via `Skill`, not `Agent`.

## Modes

Invoke via `Skill(skill: "agent-tdd:design-spec-direct", args: "<mode> ...")`.

### `plan`

Input (pass inline, same fields as a normal Design Spec): `requirements.md`, `design.md`,
`research/cache.md`, `recap.md` (optional), pre-fetched file summaries (optional).

Run exactly agent-TDD's Design Spec Mode **Phase 1 (Research Validation)** through **Phase 5
(Readiness Check)** — see `agents/agent-TDD.md:135-254` for the full procedure (unchanged, reuse
verbatim): research completeness check, slicing into TDD-sized phases, the three Ralph Loops
(Slice Size, Dependency Correctness, Research-to-Implementation Traceability), and Risk Tier
assignment.

**Stop after Phase 5, unconditionally** — this is the one structural difference from Design Spec
Mode. Do not continue into per-slice implementation regardless of whether any slice is
high-risk (Design Spec Mode's "one or more high-risk slices" pause in `agent-TDD.md:274-282`
does not apply here, because the caller is about to drive every slice individually anyway).

Return:
- `tasks.md` (per `agents/agent-TDD.md:156-192`'s format).
- Verdict: `ready` or the specific Escalation Path that fired (`agent-TDD.md:256-264`) —
  identical semantics to Design Spec Mode's escalation, same caller handling (pause, surface
  reason, resume via re-entry once addressed).

### `test-author <slice-id>`

Input: that slice's Task description, Test Intent, and Data Contracts And Interfaces only —
**the caller must not include any implementation approach, chosen file structure beyond what
Data Contracts already states, or code sketch in this call's prompt.** There is no real context
isolation here (same conversation as the `slice` mode call that follows), so the substitute is
prompt hygiene: withhold anything that would let this step's Red test conform to an
implementation instead of to the stated behavior. This preserves the *procedural* protection
`test-author` exists for (a test written before its implementer has committed to an approach)
even though it can't preserve full isolation.

Reuse `agents/test-author.md`'s own instructions for what "write only the failing Red test"
means in practice. Return the test file(s) and confirmation the test fails for the intended
reason — identical output shape to a real `test-author` spawn.

Only invoke this mode when the slice's Risk Tier (from `plan`'s `tasks.md`) is `high-risk`, or
the caller explicitly wants the split for a `standard` slice. Skip it otherwise — `slice` mode
writes its own Red test in that case, same as Slice Spec Mode always has.

### `slice <slice-id>`

Input: the slice's full entry from `tasks.md` (Task description, Test Intent, Validation Target,
Ordered Steps, Files, Risk Tier), plus — only for a high-risk slice — the test file and failure
confirmation `test-author` mode just returned.

Run agent-TDD's existing Plan → Red → Green procedure (`agents/agent-TDD.md:90-121`) for this one
slice:
- `standard` tier: write Red yourself, then Green.
- `high-risk` tier: take the supplied test as Red (do not re-author it), then Green.
- If the real code diverges materially from the slice's Data Contracts/Files assumptions, stop
  and return a **Research Gap Flag** instead of guessing — same rule as `agent-TDD.md:290-299`.
- If Green work reveals the *task* itself conflicts with existing tested behavior, return a
  **Plan Validity Flag** instead — same rule as `agent-TDD.md:301-317`.

**Stop after Green, unconditionally** — do not proceed to Refactor. Return a handoff report
mirroring Slice Spec Mode's "Handoff report" fields (`agent-TDD.md:327` onward): behavior
implemented, files touched, test run output, Risk Tier, any Research Gap Flag / Plan Validity
Flag, and explicit confirmation the change is a minimal Green with Refactor still pending.

This is the "Implementation Complete" handoff in the loop below — the caller reviews before
calling this skill again for the same slice's `refactor` mode.

### `refactor <slice-id>`

Only call after the caller's own review (see "Caller-owned loop" below) found no blocking
finding for this slice. Run agent-TDD's Refactor → Validate steps
(`agents/agent-TDD.md:126-131`) for this slice only: clarity/structure improvements, behavior
unchanged, re-run the slice's Validation Target. Return confirmation of what was refactored and
what validation ran.

### `summary`

Call once, after every slice in `tasks.md` has completed `refactor` mode. Produce the same
overall handoff shape Design Spec Mode returns at full completion (`agent-TDD.md:380` onward's
Design Spec Mode fields) — summary of all slices, Handoff Facts for the caller's memory store if
any, final validation state.

## Caller-owned loop (what agent-isdd actually drives)

This skill never loops across slices itself — every mode call is scoped to one slice (or the
one-time `plan`/`summary` calls) and returns. The calling skill (`agent-isdd`'s
`spec-driven-development`) owns the loop, exactly as it already would own resuming a real
`agent-TDD` Agent-tool spawn after its mandatory review pause:

```
plan                                  → tasks.md, verdict
for each slice in tasks.md (dependency order):
    if slice.risk_tier == high-risk:
        test-author <slice-id>        → failing test
    slice <slice-id>                  → "Implementation Complete" handoff
    caller runs independent review    (headless path, scoped to files this slice touched)
    if review has a blocking finding:
        pause — surface finding, do not call refactor, do not advance to next slice
    else:
        refactor <slice-id>           → slice done
        continue to next slice
summary                               → final handoff, log recap.md, mark Workflow Status: Complete
```

The review step matters more here than anywhere: this conversation just wrote the code, so
reviewing it with the `code-reviewer` skill inline would be self-review. The `Agent` tool is
already known broken in this session, so skip the spawn attempt and go straight to path 2 of
`code-reviewer/INTEROP.md`'s "Independent review (reviewer ≠ author)" — its headless script,
which runs in a separate process. Only if that also fails, review inline and label it
`self-reviewed` per path 3.

This is the loop from `agent-isdd/INTEROP.md`'s Fallback section, made concrete. Persist
progress in the feature's `direct-mode-state.json` (sibling to `workflow-state.json`) so a
session restart mid-loop resumes at the right slice instead of re-running completed ones:

```json
{
  "mode": "direct",
  "tasks_file": "tasks/tasks.md",
  "current_slice": "Slice 3",
  "slices": [
    {"id": "Slice 1", "status": "done", "risk_tier": "standard"},
    {"id": "Slice 2", "status": "done", "risk_tier": "high-risk"},
    {"id": "Slice 3", "status": "awaiting_review", "risk_tier": "standard"}
  ]
}
```

`status` values: `pending`, `red_green_done` (awaiting review — set right after `slice` mode
returns), `awaiting_review` (review in progress), `blocked` (a review finding paused this
slice), `done` (refactor complete).

## One thing this mode actually gains: checkpoint/`/rewind` coverage

Not every difference from a real spawn is a loss. Claude Code's checkpointing tracks file edits
made by Claude's own editing tools during the current turn, but its own docs are explicit that
**subagent edits are not restored** unless the subagent is a foreground forked skill
(`context: fork` with `background: false`, or a case the harness always foregrounds) — see
[code.claude.com/docs/en/checkpointing](https://code.claude.com/docs/en/checkpointing)'s
"Subagent edits not restored" section. A real `agent-TDD`/`test-author` spawn is a background
`Agent`-tool subagent either way, so none of its edits are ever checkpoint-tracked — `/rewind`
cannot touch them; git is the only undo path, which is exactly why the existing rollback design
(`agent-isdd/INTEROP.md`'s Rewind Contract) only ever moves a phase pointer and never attempts a
file-level restore.

This skill is a plain `Skill` invocation with no `context: fork` declared (nothing in this
plugin ecosystem uses `context: fork`), so its `test-author`/`slice`/`refactor` edits happen
inline in the calling session's own turn — ordinary, checkpoint-tracked edits. A direct-mode
slice that goes sideways can be undone with `/rewind` (restore code, or code and conversation)
the same way any other in-turn edit can, which a real `agent-TDD` spawn's edits never could be.
Don't design around this — it's incidental to using `Skill` instead of `Agent`, not a reason to
prefer direct mode — but it's worth knowing the fallback path is strictly more recoverable via
the harness's own undo mechanism than the primary path is.

## What is genuinely lost versus a real `agent-TDD`/`test-author` spawn

State this plainly in the feature's `workflow-state.md` when this skill is used — do not let a
later session mistake a direct-mode run for a normal handoff:

- **No context isolation.** `test-author` mode and `slice` mode run in the same conversation, not
  separate subagent contexts. The prompt-hygiene rule above (withhold implementation approach
  from the `test-author` call) is a real mitigation, not a full substitute — a careful reader of
  the transcript could still infer intent that true isolation would have prevented.
  `agent-isdd`'s own escalation review loses the same independence for the identical reason.
  Code review does not: the headless reviewer above runs in its own process.
- **Loop prevention is caller-enforced, not agent-enforced.** Design Spec Mode's "stop after 2
  identical fix attempts" rule (`agent-TDD.md:84-88`) depends on a single agent instance tracking
  its own attempt count across a slice. Split across separate `slice` mode calls, the caller must
  track and enforce this itself via `direct-mode-state.json` if a slice needs more than one Green
  attempt.
