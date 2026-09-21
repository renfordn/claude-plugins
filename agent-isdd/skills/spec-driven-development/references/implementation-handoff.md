# Implementation Handoff (Phase 2+3 revised) — full contract

Once Design is approved and implementation is requested, this skill's job is to hand off to
`agent-tdd` for implementation — a single, one-directional handoff, not an orchestrated
multi-stage loop. `Track: Standard` sends a **Design Spec** (steps below); `Track: Fast` sends a
single **Slice Spec** instead — see "Fast Track: Slice Spec handoff" right after these steps for
that branch in full. Both are one-directional handoffs with no orchestrated multi-stage loop;
only the spec shape and `agent-tdd` mode differ.

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
   - Pass the reduced file list to agent-nelly (if available)
   - Receive cache hits (with git_hash validation) + cache misses
   - Bundle cache hits into Design Spec handoff
3. Construct **Design Spec** with:
   - Full `requirements.md` (approved)
   - Full `design.md` (approved, with Research Basis)
   - `research/cache.md` (design_findings, task_findings, file_summaries, git_hashes)
   - Pre-fetched file summaries from agent-nelly (if available)
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
5. Spawn `agent-tdd:agent-TDD` with the Design Spec (via the `Agent` tool). If this spawn
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
6. **[Added 2026-09-16] Test-author pause check** — after the spawn returns, check
   `workflow-state.json` for `test_author_pending` (written by `hooks/high_risk_reviewer.py`
   when `agent-TDD`'s report is at `slicing_complete` with one or more high-risk slices — see
   its **High-Risk Slices** field, and `agent-tdd/INTEROP.md`'s "Design Spec Mode" section for
   the full contract). If set:
   - Spawn `agent-tdd:test-author` once per slice named in `test_author_pending.slices`,
     passing that slice's Task description/Test Intent/Data Contracts (per
     `agent-tdd/INTEROP.md`'s existing test-author field-subset rule — Task description, Test
     Intent, Data Contracts And Interfaces only).
   - Bundle every returned test into one resume message.
   - Resume the same `agent-tdd:agent-TDD` instance via `SendMessage` with the bundled results.
   - Clear `test_author_pending` from `workflow-state.json` (mirrors `clear_rollback_pending`'s
     existing pattern in `hooks/sdd_state.py`).
   - This is the **one** scoped exception to step 7 below — resuming here, for this specific
     reason, is expected. Nothing else about the one-directional handoff changes: this skill
     still never resumes `agent-TDD` for an ordinary per-slice Green→Refactor review pause, only
     for this single upfront test-author gate before per-slice implementation begins.
7. Take its returned handoff report (the resumed one, if step 6 applied; the original one
   otherwise):
   - If report indicates research validation escalation: pause and surface reason (user re-enters
     to address, then agent-isdd continues via before-continue hook)
   - If report indicates slicing blockers: pause with specific blocker
   - If report indicates implementation started: log handoff in `recap.md`, set
     `Workflow Status: Complete`
8. Do not resume, monitor, or drive `agent-TDD` past step 6's single test-author pause —
   anything after that (its own per-slice review pauses, or implementation) is outside this
   skill's scope, same as before this change.
9. If the report's Handoff Facts field is non-empty and `agent_nelly_available` is `true` in
   `workflow-state.json`, call `agent-nelly:agent-nelly` with those facts as a `new facts`
   batch. One call only — no re-fetch of the brief needed.

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
   slicing-complete report — belongs to Design Spec Mode's task-slicer path and never fires for
   a Slice Spec Mode spawn). Per `agent-tdd/INTEROP.md`'s "Two-part invocation" section: spawn
   `agent-tdd:test-author` first, passing only Task description/Test Intent/Data Contracts And
   Interfaces from the Slice Spec, take its returned test file(s) and failure confirmation, and
   fold that into the Slice Spec (telling `agent-TDD` not to write its own test for that
   behavior) before spawning it. For `standard` Risk Tier, skip straight to the next step.
5. Spawn `agent-tdd:agent-TDD` with the Slice Spec (Slice Spec Mode, single invocation).
6. Take its returned handoff report: pause and surface a research-gap flag if raised (same as
   Standard step 7's first bullet); otherwise log the handoff in `recap.md` and set
   `Workflow Status: Complete`. No step 6/8 equivalent from the Standard path applies here —
   step 4 already handled the one high-risk case upfront, so there's no post-hoc
   test-author-pause-then-resume cycle to manage.
7. Same as Standard step 9: forward non-empty Handoff Facts to `agent-nelly:agent-nelly` if
   available.
