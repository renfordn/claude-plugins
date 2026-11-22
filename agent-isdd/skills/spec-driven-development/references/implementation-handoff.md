# Implementation Handoff (Phase 2+3 revised) — full contract

Once Design is approved and implementation is requested, this skill's job is to hand off to
`agent-tdd` for implementation. A serial run is a single, one-directional handoff, not an
orchestrated multi-stage loop. A parallel run means this skill acts as the tdd-parallel lead
(step 8). `Track: Standard` sends a **Design Spec** with `Parallel: on` (steps below);
`Track: Fast` sends a single **Slice Spec** instead and stays serial — see "Fast Track: Slice
Spec handoff" right after these steps for that branch in full.

## Standard: Design Spec handoff

See `INTEROP.md` at the repo root for the exact Design Spec contract (requirements.md,
design.md, research/cache.md, pre-fetched file summaries, recap.md).

1. Extract file list from `design.md` + `research/cache.md` (all files mentioned in Research Basis
   and task_findings sections).
2. **Subtract, then query.** `research/cache.md`'s own `file_summaries` field (produced fresh by
   `research-consolidator` earlier in this same Design phase — see `design-author/SKILL.md`'s
   Research First section) already covers every file that pass touched. Querying
   `agent-nelly:agent-nelly` for those same files again would bundle the same summary into the
   Design Spec twice — once fresh from this session's research, once again from nelly's cache.
   Remove those files from the extracted list before querying, so the nelly call only asks about
   files research-consolidator's pass didn't cover (files named in requirements/design but never
   deep-read, or adjacent files worth knowing about from earlier features). If the resulting list
   is empty, skip the nelly query entirely — there's nothing left to ask about.
   - Pass the reduced file list to agent-nelly (if available) via `file summary lookup` (see
     `agent-nelly/agents/agent-nelly.md`'s "File & Folder Summary Cache" section)
   - Receive cache hits (`description` + `git_hash`) + cache misses; validate each hit yourself
     by comparing the returned `git_hash` against `git hash-object <path>` on the current file —
     a mismatch is a miss, not a hit
   - Bundle confirmed cache hits into the Design Spec's `research_cache.file_summaries` (merged
     alongside the fresh ones from step 1, per `INTEROP.md`'s `file_summaries` field description)
3. Construct **Design Spec** with:
   - Full `requirements.md` (approved)
   - Full `design.md` (approved, with Research Basis)
   - `research/cache.md` (design_findings, task_findings, file_summaries, git_hashes)
   - Pre-fetched file summaries from agent-nelly (if available)
   - The tasks.md location, stated explicitly: `<feature spec dir>/tasks/tasks.md`. The hooks read only
     that path (`high_risk_reviewer` wave detection, `review_tracking`, `complete_guard`), so a
     tasks.md written anywhere else is invisible to them.
   - `Parallel: on`, for every Standard-track handoff (slicing happens inside agent-TDD, so the
     slice count is not known yet; a wave of width 1 is fine under tdd-parallel)
   - `recap.md`, **summarized, not pasted in full** — unlike the other fields above, `recap.md`
     grows unbounded across a long-running feature's phases, and `agent-TDD` only needs enough of
     it to inform implementation, not a full phase-by-phase history. Extract just: the current
     summary, any open risks or blockers, and the Goal-alignment note — a few sentences, not the
     whole file. If `recap.md` is already short (a new feature, few phases so far), passing it in
     full is fine; the summarization step exists for the case where it's grown large, not as a
     blanket rule to always compress it.
4. Before spawning, check the session's `<system-reminder>` agent-types block for
   `agent-tdd:agent-TDD`. If absent, pause with a concrete, actionable message (e.g. "agent-tdd
   is not installed in this session — install it before requesting implementation") rather than
   attempting the work internally.
   Then settle Implementation Mode (see "Implementation Mode and approval" below) and write
   `Implementation Mode: <answer>` to `workflow-state.md` before any spawn. In `user` mode the spawn
   still happens (step 5, `Parallel: on`) but agent-TDD only slices: see "User-led slicing" below.
5. Spawn `agent-tdd:agent-TDD` with the Design Spec (via the `Agent` tool, `model: "sonnet"`; for a
   Fast-track Slice Spec use its Model Tier, which may be `haiku` for a trivial change). If this spawn
   fails at the tool-call layer itself (a `PreToolUse` schema-validation error on the `Agent`
   call, not an error from the spawned agent) and reproduces identically on retry and for an
   unrelated agent type in the same session, this is the harness `Agent`-spawn bug, not an
   installation or Design Spec problem — see `INTEROP.md`'s "Fallback — Direct Implementation
   (harness `Agent`-spawn failure)" section for the Detection conditions (confirm all of them
   before falling back — never on a single failure) and the fallback loop: invoke
   `agent-tdd:design-spec-direct` via the `Skill` tool (never `Agent` — that skill exists
   because `Skill` calls aren't subject to this bug), driving its `plan` → per-slice
   `test-author`/`slice`/review/`refactor` → `summary` loop yourself instead of trusting an
   isolated `agent-TDD` spawn to run it unsupervised.
6. **[Added 2026-09-16] Test-author pause check (serial runs only)** — after the spawn returns, check
   `workflow-state.json` for `test_author_pending` (written by `hooks/high_risk_reviewer.py`
   when `agent-TDD`'s report is at `slicing_complete` with one or more high-risk slices — see
   its **High-Risk Slices** field, and `agent-tdd/INTEROP.md`'s "Design Spec Mode" section for
   the full contract). If set:
   - Spawn `agent-tdd:test-author` once per slice named in `test_author_pending.slices`,
     passing that slice's Task description/Test Intent/Data Contracts (per
     `agent-tdd/INTEROP.md`'s existing test-author field-subset rule — Task description, Test
     Intent, Data Contracts And Interfaces only).
   - Bundle every returned test into one resume message.
   - Resume the same `agent-tdd:agent-TDD` instance via `SendMessage` with the bundled results,
     asking for its report as its final plain-text response (a second hand-back is refused).
     While it runs, check it for stalls with `agent-tdd/scripts/agent_stall.py`; on a stall,
     resume it with a status check or tell the user, never wait silently; if its report is lost,
     rebuild state from the worktree, `git log` and test logs (`agent-tdd/INTEROP.md`,
     "Resumed reports and stalled agents").
   - Clear `test_author_pending` from `workflow-state.json` (mirrors `clear_rollback_pending`'s
     existing pattern in `hooks/sdd_state.py`).
   - Serial runs only. In a parallel run the tdd-parallel lead runs `agent-tdd:test-author` for
     each wave's high-risk slices (`agent-tdd/references/parallel-delivery.md`); do not resume
     agent-TDD to implement serially.
7. Take its returned handoff report (the resumed one, if step 6 applied; the original one
   otherwise):
   - If report indicates research validation escalation: pause and surface reason (user re-enters
     to address, then agent-isdd continues via before-continue hook)
   - If report indicates slicing blockers: pause with specific blocker
   - If report indicates implementation started (serial run): log handoff in `recap.md`, set
     `Workflow Status: Complete`. For a parallel run, do this only after the lead's
     `all_slices_complete` (see step 8)
   - If the report carries `<!--AGENT-TDD-BLOCKED: reason="..."-->` and **no** `AGENT-TDD-PHASE`
     marker (a UI slice with no E2E harness; see `agent-tdd/references/slice-discipline.md` section 4),
     it is not a green pause and not a failure. Skip that slice and its dependents (the tasks
     `**Blocked:**` field), keep running independent slices, then ask via `AskUserQuestion` with three
     options: **add a harness slice** (insert it ahead of the blocked slice), **accept the slice
     without E2E** as a recorded fallback (note it in `recap.md` and in `workflow-state.md` Hook Notes),
     or **pause**. Never mark a blocked slice done or reviewed.
   - A report with `<!--AGENT-TDD-OUTCOME: coverage-only-->` (the first-run pass: the test already
     passed and `coverage --mutant` confirmed it pins the behavior, no production change) is a normal
     slice: it stops at `green_pause` and gets the usual independent review. So does `<!--AGENT-TDD-OUTCOME: refactor-->` (a `refactor`/`contract` slice proven by `coverage` then `green`).
8. **Parallel run.** When agent-TDD returns `slicing_complete` with a wave plan, run
   `agent-tdd:tdd-parallel` on the written tasks.md and act as its lead (see
   `agent-tdd/references/parallel-delivery.md`): spawn, review, verify, merge and commit each wave.
   Set `Workflow Status: Complete` and forward Handoff Facts only after the lead's
   `all_slices_complete` (after integration and the coherence review). Setting Complete earlier
   would turn the gates off for the remaining workers, because `active_state_file` skips Complete
   features. For a serial run, do not resume or monitor `agent-TDD` past step 6's test-author
   pause or a Model Escalation re-spawn; its own per-slice review pauses are outside this skill's
   scope.
9. If the report's Handoff Facts field is non-empty and `agent_nelly_available` is `true` in
   `workflow-state.json`, call `agent-nelly:agent-nelly` with those facts as a `new facts`
   batch. In the same call, if the report's **File Summaries** field (see
   `agent-tdd/agents/agent-TDD.md`'s section of that name) is also non-empty, pass its items as
   `file summaries` too — one call carries both, no re-fetch of the brief needed.

## Implementation Mode and approval

Before the spawn (step 4) settle `Implementation Mode`: `agent` (agent-TDD implements, the default)
or `user` (user-led: Claude writes tests on request, never production code; see the `isdd-coach`
skill). If the user already stated the mode in this conversation (e.g. "I'll write the code, coach
me"), that is their say-so: record it without asking again. Ask via `AskUserQuestion` only when the
mode is not stated. Write `Implementation Mode: <answer>` to `workflow-state.md`. `user_led_guard` enforces `user`; never change it
without the user's say-so.

`design_spec_gate` checks `Implementation Requested` plus the approval hash on every agent-TDD
spawn, including parallel workers, and records the hash on the first spawn. Editing
requirements/design mid-wave therefore blocks the remaining spawns until `refreeze`. Its deny
message prints the exact command with resolved absolute paths; prefer copying that. Runnable form:
- Run `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" approve "<spec_dir>"`
  only after the user approves via `AskUserQuestion` (plan mode unavailable); it sets
  `Implementation Requested` and `Approval Pending`.
- Run `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" refreeze "<spec_dir>"`
  only after the user re-approves a changed scope via `AskUserQuestion`.

## User-led slicing

In `user` mode agent-isdd still spawns agent-TDD with the Design Spec and `Parallel: on`, so
agent-TDD only slices: it stops at `slicing_complete`, writes no production code, and writes
`<feature spec dir>/tasks/tasks.md` with Risk Tiers and waves. The approval hash freezes at that spawn,
as in agent mode. `user_led_guard` does not block the tasks.md write (the memory dir is allowed).
The handoff must not resume agent-TDD to implement in user mode, and does not run `tdd-parallel`
or the test-author pause check. Route to the `isdd-coach` skill, which walks those slices; on the
Fast track it coaches the single Slice Spec slice (see "Fast Track" below: no spawn in user mode).

## Fast Track: Slice Spec handoff

`Track: Fast` replaces the Design Spec steps above entirely — no task-slicing, no test-author
gate (that gate exists specifically for a Design Spec's high-risk multi-slice case), no
mandatory post-Green review pause:

1. Use the `agent-tdd:slice-spec` skill to assemble a single Slice Spec straight from the
   approved `design.md` (and `requirements.md`) — this skill already exists for exactly this:
   gathering and validating the fields a Slice Spec needs and emitting a correctly formatted
   spawn prompt block. No `tasks.md` is created; the Design checklist's "Ready to move to
   Tasks" item is satisfied instead as "ready for direct Slice Spec handoff" (see
   `design-author/SKILL.md`).
2. In that Slice Spec, explicitly set **Review handoff mode: skip** — `Track: Fast`'s whole
   point is momentum, so the mandatory pause after Green does not apply here. (A caller can
   still re-review afterward via the standalone `code-reviewer` skill if it wants to; this just
   means `agent-TDD` doesn't block on it.)
3. Same session/availability check as step 4 above: confirm `agent-tdd:agent-TDD` is in the
   session's agent-types listing before spawning; same harness-bug fallback as step 5 above if
   the spawn itself fails at the tool-call layer.
4. **If the Slice Spec's Risk Tier is `high-risk`**: this is a *caller-driven upfront* split,
   not the Standard path's hook-driven mid-flight resume (that pattern —
   `hooks/high_risk_reviewer.py` setting `test_author_pending` after `agent-TDD`'s own
   slicing-complete report — belongs to Design Spec Mode (agent-TDD's own slicing) and never fires for
   a Slice Spec Mode spawn). Per `agent-tdd/INTEROP.md`'s "Two-part invocation" section: spawn
   `agent-tdd:test-author` first, passing only Task description/Test Intent/Data Contracts And
   Interfaces from the Slice Spec, take its returned test file(s) and failure confirmation, and
   fold that into the Slice Spec (telling `agent-TDD` not to write its own test for that
   behavior) before spawning it. For `standard` Risk Tier, skip straight to the next step.
5. Spawn `agent-tdd:agent-TDD` with the Slice Spec (Slice Spec Mode, single invocation). In
   `Implementation Mode: user`, skip this spawn: Fast never writes tasks.md, so route to `isdd-coach`,
   which coaches the single Slice Spec slice itself as slice 1, built with the `slice-spec` skill.
6. Take its returned handoff report: pause and surface a research-gap flag if raised (same as
   Standard step 7's first bullet); otherwise log the handoff in `recap.md` and set
   `Workflow Status: Complete`. No step 6/8 equivalent from the Standard path applies here —
   step 4 already handled the one high-risk case upfront, so there's no post-hoc
   test-author-pause-then-resume cycle to manage.
7. Same as Standard step 9: forward non-empty Handoff Facts (and any non-empty File Summaries) to
   `agent-nelly:agent-nelly` if available.

## Handoff overview (moved from SKILL.md's Implementation Handoff section, verbatim)

Read by `spec-driven-development` when starting the Implementation handoff.

Once Design is approved and implementation is requested, this skill's job is to hand off to
`agent-tdd` for implementation. A serial run is a single, one-directional handoff, not an
orchestrated multi-stage loop; a parallel run means this skill acts as the tdd-parallel lead.
`Track: Standard` sends a **Design Spec** with `Parallel: on`; `Track: Fast` sends a single
**Slice Spec** (serial) with `Review handoff mode: skip`. See
`references/implementation-handoff.md` for the full contract: Design Spec construction (file
list extraction, the `agent-nelly` subtract-then-query step, the recap summarization rule),
Slice Spec construction, the availability check before spawning, the harness-`Agent`-spawn-bug
fallback, the test-author pause/resume steps, and the Handoff Facts write-back.
