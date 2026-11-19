# Interop: agent-isdd → agent-tdd (full contract)

Moved verbatim from `INTEROP.md` (split to keep the index short); the section below is the authoritative agent-tdd boundary.

## → agent-tdd (implementation, Phase 2+3 revised)

**[Phase 2+3]** At the end of Design, once Design is approved and implementation is requested,
`agent-isdd` constructs a **Design Spec** from the approved `requirements.md`/`design.md`, the
cached research findings, and pre-fetched file summaries, then spawns `agent-tdd` for research
validation, task slicing, and implementation (done serially by agent-TDD, or by `agent-tdd:tdd-parallel`
workers in a parallel run; see "Parallel handoff" below).

**Design Spec** includes:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requirements_md | string | yes | Full approved requirements.md |
| design_md | string | yes | Full approved design.md (with Research Basis section) |
| research_cache | object | yes | Research findings including design_findings, task_findings, file_summaries, git_hashes, and the resolved per-repo line-count ceiling (`{value, source}`) |
| recap_md | string | yes | Summarized recap of summary, known risks, blockers, and Goal alignment notes |

**Optional fields** (passed through but not validated):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file_summaries | object | no | Pre-fetched file summaries from agent-nelly cache (if available), merged into research_cache for files not already covered by fresh file_summaries — see skills/spec-driven-development/references/implementation-handoff.md's Standard step 2 for deduplication rationale |

**Agent-tdd responsibilities** (Phase 2+3):
1. **Research Validation** (validate only — never re-researches)
   - Validate design.md's file touchpoints against research cache
   - If cache is thin or inconsistent: flag the exact gaps and pause; agent-isdd runs the
     targeted `research-consolidator` on those gaps and resumes (agent-tdd does not re-research)
   - If design contradicts research: escalate back to agent-isdd

2. **Task Slicing** (produce `tasks.md`)
   - Produce phased, TDD-sized slices from Design + task_findings
   - Validate slice safety (3 files max, testable, acyclic dependencies)
   - Assign Risk Tiers (high-risk → spawn test-author first)

3. **Implementation** (Red-Green-Refactor per slice): serial runs (`Track: Fast`) by agent-TDD itself; parallel runs (Standard) by `tdd-parallel` workers led by the agent-isdd thread.

This is a **one-directional handoff for serial runs only** (`Track: Fast`): agent-isdd does not resume
or monitor agent-tdd past the initial spawn, with two scoped exceptions, the Test-Author Gate (below)
and Model Escalation (`hooks/model_escalate_marker.py` and `hooks/subagent_report.py` re-spawn at a
higher tier; marker vocabulary in `agent-tdd/references/escalation-paths.md`). `Track: Standard`
sends `Parallel: on`, and the agent-isdd thread then leads `agent-tdd:tdd-parallel` (see "Parallel
handoff"). Task slicing happens inside agent-tdd
(not handed back to agent-isdd as Slice Specs). Escalations back to agent-isdd (design
contradicts research, research too thin) pause with explicit reason; agent-isdd resumes via its
`before-continue` hook when user re-enters after addressing the escalation.

**Exception — Test-Author Gate (serial runs only)**: agent-TDD knows every slice's Risk Tier at the
`slicing_complete` checkpoint. In a serial run with at least one `high-risk` slice it stops there and
names them (**High-Risk Slices**); `hooks/high_risk_reviewer.py` (`SubagentStop`) writes
`test_author_pending` to `workflow-state.json`, and `implementation-handoff.md`'s step 6 spawns
`agent-tdd:test-author` per slice and resumes the same agent-TDD via `SendMessage`. In a **parallel run**
agent-TDD always stops at `slicing_complete` with the wave plan, `test_author_pending` is not used,
and the lead runs `test-author` per wave (see "Parallel handoff"). Zero high-risk slices in a serial
run means no behavior change.

**Exception — Code-Review Gate (caller-driven)**: hooks cannot spawn or resume agents, so no hook
auto-resumes a paused agent-TDD. In a **serial run** agent-TDD's mandatory Green pause (see
`agent-tdd/INTEROP.md`, "The mandatory review pause") is driven manually: run an independent review
(`code-reviewer/INTEROP.md`, "Independent review (reviewer ≠ author)"), then resume the live agent-TDD
via `SendMessage` in the same session. In a **parallel run** the agent-isdd thread, as the tdd-parallel
lead, spawns `code-reviewer` per slice with `Review scope: slice=<ID>` in the prompt;
`review_tracking` records it (see `interop-reviewers.md`). Passive tracking is described in
`skills/spec-driven-development/references/code-reviewer-checkpoint.md`.

### Agent-tdd Design Spec workflow (pointer)

`agent-tdd/agents/agent-TDD.md`'s "Design Spec workflow" is the authoritative definition of what
`agent-tdd` does with a Design Spec: research validation (validate only), task slicing (one
behavior per slice, at most 3 files, acyclic Depends On, prerequisite `fix`/`refactor` slices
ordered first), a validation pass ("Ralph Loops": size, dependency, traceability; re-slice at most 3 rounds, else escalate), Risk Tier
assignment, and a readiness check. This file does not restate those rules; it only pins the
agent-isdd side of the boundary: the Design Spec fields above, the escalations that return here
(research too thin, design contradicts research, slicing blocked by the design, or a high-risk
slice that cannot be split without a product decision), and the handoff report.

**Handoff Report Format:** marker-tagged with `<!--AGENT-TDD-PHASE:slicing_complete-->` and the fields
**Research Validation**, **Task Slicing**, **Risk Tier Distribution**, **High-Risk Slices** (exact names
or "none"), **Readiness Verdict** (`ready for implementation`, or `paused` with the reason),
**Tasks File Path**, **Handoff Facts**, and **File Summaries**. `agent-tdd/agents/agent-TDD.md`
(Design Spec workflow) and `agent-tdd/INTEROP.md`'s "Design Spec Handoff Report" are authoritative for the
exact shape.

**After Tasks readiness passes:**
- `ready`, serial run, no `high-risk` slice: agent-TDD proceeds to Red-Green-Refactor directly.
- `ready`, serial run, one or more `high-risk` slices: stop and hand back the report (Test-Author Gate above).
- `ready`, Parallel run: agent-TDD stops at `slicing_complete` with the wave plan; the lead runs
  `agent-tdd:tdd-parallel` (see "Parallel handoff").
- `paused`: return the reason; the user re-enters agent-isdd.
- Readiness and Complete-timing rules live in `implementation-handoff.md` (single home); do not
  implement before readiness passes.

**Design Spec completeness gate**: `hooks/design_spec_gate.py` (`PreToolUse`, matcher `Agent`,
scoped to `subagent_type: agent-tdd:agent-TDD`) hard-denies the spawn unless the active
feature's `requirements.md` and `design.md` are both `State: Approved` on disk — modeled on
`slice_spec_gate.py`'s `deny()` shape. `slice_spec_gate.py` validates a different, incompatible
(Slice Spec) schema and is not involved in this Design Spec path — it was removed from
`hooks.json` when Phase 2+3 eliminated unconditional per-slice Slice Spec validation, then
**re-enabled 2026-09-17** scoped to `Track: Fast`'s single-slice Slice Spec handoff (the hook
itself reads `workflow-state.json`'s `Track` and no-ops for `Track: Standard` — see
`tests/test_hooks_json.py`'s `test_slice_spec_gate_reenabled_for_fast_track`). It also checks `Implementation Requested` plus the approval hash and freezes the hash on first spawn (see "Parallel handoff" below); it
falls through with no decision when no SDD workflow is active at all.

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
call-site can work around. First observed 2026-09-15 on the `2026-09-15-expand-error-logger`
feature (investigation notes live in that feature's `workflow-state.md` in the author's local SDD
memory, not in this repo, so this is unverified here): a PreToolUse hook rejected the `Agent`
call with `"description type expected as string but provided as unknown"`. The author's
investigation attributed it to the harness (no enabled hook was thought to be producing that
`updatedInput`, and the failure reproduced for a plain `claude` agent type), i.e. it blocks *all*
`Agent`-tool spawns in the affected session, not something specific to this handoff.

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
3. Review that slice's touched files with the headless independent reviewer
   (`code-reviewer/INTEROP.md`'s "Independent review (reviewer ≠ author)", path 2 — skip the
   spawn attempt, it's already known broken here). Reviewing inline with the skill would be this
   same conversation grading its own code; do that only if the headless run also fails, labelled
   `self-reviewed`.
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

## Parallel handoff (current behavior)

- **Parallel: on.** `Track: Standard` always sends the Design Spec with `Parallel: on` (the slice count is
  unknown before slicing; a wave of width 1 is fine). `Track: Fast` sends a single Slice Spec and stays
  serial. Source: `skills/spec-driven-development/references/implementation-handoff.md`.
- **Wave plan.** With `Parallel: on`, agent-TDD writes `tasks.md` with owned files, then stops at
  `slicing_complete` with the wave plan. It does not implement. `hooks/high_risk_reviewer.py` routes a
  wave-stamped `tasks.md` to the lead: run `agent-tdd:tdd-parallel` and act as its lead
  (see `agent-tdd/references/parallel-delivery.md`), which spawns workers, runs `agent-tdd:test-author`
  for each wave's high-risk slices, reviews, verifies, merges and commits each wave. Do not resume
  agent-TDD to implement serially and do not rely on `test_author_pending` in a parallel run.
- **tasks.md path.** The Design Spec names it explicitly as `<feature spec dir>/tasks/tasks.md`; the
  hooks read only that path (`high_risk_reviewer` wave detection, `review_tracking`, `complete_guard`).
- **Implementation Mode**: rule in `implementation-handoff.md`. Both modes spawn agent-TDD with the
  Design Spec and `Parallel: on`; in `user` mode it only slices (stops at `slicing_complete`) and is
  the handoff must not resume agent-TDD to implement; `isdd-coach` then walks the slices, with
  `user_led_guard` blocking production edits. Fast track in `user` mode: no spawn.
- **Complete.** In a parallel run `Workflow Status: Complete` is set only after the lead's
  `all_slices_complete` (after integration and the coherence review); earlier would switch the gates
  off for the remaining workers.
- **Approval.** `hooks/design_spec_gate.py` is no longer read-only: on every agent-TDD spawn (workers
  included) it checks `Implementation Requested` plus the approval hash and records (freezes) the hash
  on the first spawn. Editing requirements/design mid-wave blocks the remaining spawns until
  re-approval. The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" approve <spec_dir>`
  (plan mode unavailable; run only after the user approves via `AskUserQuestion`) and
  `... refreeze <spec_dir>` (only after the user re-approves a changed scope via `AskUserQuestion`).
  The deny message prints the exact command with resolved paths.

## Release 3 additions (pointer)

Authoritative: `agent-tdd/INTEROP.md`, `agent-tdd/references/slice-discipline.md`,
`agent-tdd/references/evidence-log.md`, `agent-tdd/hooks/markers.py`. Handling rules:
`implementation-handoff.md` (step 7).

- **OUTCOME marker.** `<!--AGENT-TDD-OUTCOME: coverage-only-->` next to the phase marker: the test
  passed first time and `coverage --mutant` confirmed it; no production change. A normal reviewable slice.
- **BLOCKED marker.** `<!--AGENT-TDD-REPORT-->` plus `<!--AGENT-TDD-BLOCKED: reason="..."-->` and no
  `AGENT-TDD-PHASE` marker. The hooks (`impl_progress`, `high_risk_reviewer`, `subagent_report`)
  tolerate it: no slice state, no rollback. The lead asks the user (harness slice / accept without E2E / pause).
- **Fields.** Slice Spec `ui` (true forces the UI path); tasks.md `**UI:**` and `**Blocked:**` per slice.
- **red_first_guard.** `agent-tdd/hooks/red_first_guard.py` denies production Write/Edit in an open
  slice (after `tdd_check.py start`, until `done`) until a confirmed Red, coverage or logged `bypass`.
  Known limit: Bash writes (`sed -i`, redirects) bypass it, as they do `user_led_guard`.
- **Bypass surfacing.** `tdd_check.py bypass --slice ... --reason ...` logs a `bypass` evidence line;
  agent-TDD copies it into Validation Evidence and agent-tdd's SubagentStop hook surfaces the bypasses
  to the caller, who should read the reasons at review time.
