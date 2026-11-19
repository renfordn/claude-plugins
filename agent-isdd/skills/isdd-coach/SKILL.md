---
name: isdd-coach
description: Coach user-led mode. Invoked by /isdd.
user-invocable: false
---

# ISDD Coach (user-led Implementation Mode)

Entered from `implementation-handoff.md` when the Implementation Mode answer is `user`. The user
writes the production code. You coach.

## Before you start

1. Resolve the active workflow. If there is none, route the user to `/isdd`; do not coach.
2. If `Implementation Mode` is not `user`, follow the mode rule in `implementation-handoff.md`: a mode
   the user already stated is recorded without asking again; ask via `AskUserQuestion` only when the
   mode is not stated. Write `Implementation Mode: user` only from their statement or answer.

Why: `user_led_guard` and review tracking only work with an active workflow and mode `user`.

## Ground rules

- Claude never writes production code in user-led mode. `user_led_guard` enforces this: it denies
  non-test repo edits and allows test files and the memory dir. If a deny fires, do not work around
  it (no Bash writes); ask the user to make the change.
- Write tests only when the user asks. Otherwise explain what the test should pin down and let the
  user write it.
- Never change `Implementation Mode` without the user's say-so. If the user wants agent-led, ask
  via `AskUserQuestion`; they (or you, on their explicit answer) set `Implementation Mode: agent`.
- Don't spawn agent-TDD to implement while the mode is `user`; its only user-mode job is slicing.

## Walk the slices

- Standard track: agent-TDD already sliced (it stopped at `slicing_complete` and wrote
  `<feature spec dir>/tasks/tasks.md`). Read it and take slices in dependency order, one at a time.
- Fast track: no agent-TDD spawn and no tasks.md. You coach the single Slice Spec slice yourself as
  slice 1, building it with the `slice-spec` skill.

Present each slice with the
Slice Spec field names (see `agent-tdd/references/slice-spec.schema.json`):

- `taskDescription`: the behavior to build, in one sentence.
- `acceptanceCriteria`: the observable behavior a test must pin down (the slice's Test Intent).
- `riskTier`: `standard` or `high-risk`; high-risk slices get a deeper review.
- `dataContractsAndInterfaces`: signatures and module boundaries to honor.
- `sliceId` / `ownedFiles`: which slice this is and the files it may touch.

Keep slices small: more than 3 files or ~5 assertions means suggest splitting before Red.

## Red, Green, Refactor

1. **Red**: the user writes (or asks you to write) the failing test. Confirm it fails for the
   intended reason, not an import error.
2. **Green**: the user writes the minimum production change. Hint and review; do not type it.
3. **Refactor**: the user tidies with tests green; re-run after each step.

For evidence, run the checker (resolve the agent-tdd plugin path; search for
`agent-tdd/scripts/tdd_check.py` if it does not expand):

```
python3 <agent-tdd plugin>/scripts/tdd_check.py red   --slice "Slice N: <title>" -- <test cmd>
python3 <agent-tdd plugin>/scripts/tdd_check.py green --slice "Slice N: <title>" -- <test cmd>
```

Open each slice with `tdd_check.py start --slice "Slice N: <title>" --kind feature` (or `--kind refactor`/`contract` for behavior-preserving slices) and close it with
`tdd_check.py done --slice "Slice N: <title>"` (recommended; they scope `red_first_guard`).

- **First-run pass:** if the user's new test already passes, do not contrive a Red. Run
  `tdd_check.py coverage --mutant "<cmd>" --slice ... -- <test cmd>`; confirmed means a coverage-only
  slice (no production change, still reviewed).
- **Refactor path:** for a `refactor`/`contract` slice run `coverage --mutant` on the characterization test, change the code, then `green`; it is reported as `<!--AGENT-TDD-OUTCOME: refactor-->`.
- **Bypass:** `tdd_check.py bypass --slice ... --reason "<why>"` only when Red cannot come first.
- **Guards:** the user edits outside Claude's tools, so `red_first_guard` and `user_led_guard` only
  constrain Claude's own writes. Both may deny; either deny wins.
- **UI slice with no E2E harness:** agent-tdd reports `AGENT-TDD-BLOCKED`; follow
  `implementation-handoff.md` step 7 (skip dependents, ask the user).

Red must fail and Green must pass. Quote the `TDD-EVIDENCE` lines back to the user. Never claim
Red or Green you did not observe.

## Review

When the user's Green passes, spawn the `code-reviewer:code-reviewer` agent with the Agent tool.
The prompt must include the literal line `Review scope: slice=N` (N is the slice id), plus the
changed files (tests included) and the slice's `acceptanceCriteria`; use `Deep` review for
high-risk slices. Only that agent's SubagentStop records a review; running the skill inline does not.

A completed code-reviewer review of the slice counts for the R3 review gate: `review_tracking`
records it, and `complete_guard` blocks Complete while high-risk slices are unreviewed. Relay the
findings to the user; the user decides how to fix them. For a fallback, use only
`Accepted via AskUserQuestion: <slice ids | all>: <reason>` after the user agrees.

## After the last slice

Summarize slices done, evidence lines and review outcomes. Complete only follows the normal
workflow-manager flow once every slice is reviewed as required.
