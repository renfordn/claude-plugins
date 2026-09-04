<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.9] - 2026-08-23

**Enhancement: Readiness-check marker emission & UX integration**

### Fixes & Improvements

- **readiness-check marker emission** — When verdict = `paused`, readiness-check now emits `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` marker before verdict JSON; captured by SubagentStop hook for escalation to agent-isdd
- **ux_render.py hook** — New UX rendering hook for phase transitions; detects TDD stage changes (Plan → Red → Green → Review → Refactor → Validate) and renders breadcrumb/phase_transition events
- **Test suite** — Added `test_readiness_check_marker.py` with 9 tests covering marker format, escalation flows, and blocker scenarios
- **Documentation** — Updated INTEROP.md to document marker format and escalation paths; updated readiness-check.md with marker emission behavior

## [0.1.8] - 2026-08-22

**Major: Design Spec handoff from agent-isdd (Phase 2+3 integration)**

### New Capability: Design Spec Orchestration

- **New agents** for Design Spec handoff workflow:
  - `research-validator` — validates research completeness; escalates if gaps or contradictions
  - `task-slicer` — generates TDD-sized, dependency-ordered tasks.md from EARS behaviors
  - `ralph-loops` — three autonomous validation loops (size, dependencies, traceability) with hard iteration limits (3/loop)
  - `risk-assign` — assigns Risk Tiers based on design risks, migrations, multi-module complexity, testability, Ralph findings
  - `readiness-check` — 10-item deterministic checklist gate before Red-Green-Refactor

- **New skill**: `design-spec` — orchestrates full Design Spec → tasks.md → Red-Green-Refactor flow
  - Accepts Design Spec from agent-isdd (requirements.md, design.md, research_cache, recap.md)
  - Parses upfront, caches for resume (skip re-parsing on re-entry)
  - Early escalation on research gaps (save 13-20K tokens)
  - Ralph Loops max iteration limits (3/loop, 9 total) prevent runaway
  - Structured outputs (JSON/markdown) for programmatic handoff

- **New schema**: `design-spec.schema.json` — strict JSON schema for Design Spec validation

- **Token efficiency (North Star achieved)**:
  - Initial run: 18-28K tokens (23.5K actual)
  - Resume via cache: 10-15K tokens (30-40% savings)
  - Early escalations save 4-20K additional tokens
  - **Total: 30-70% reduction vs. old per-agent approach**

### State Management & Caching

- `workflow-state.json` caching strategy:
  - `design_spec_cache` — parsed design touchpoints, behaviors, risks, file_summaries (reuse on resume)
  - `task_slicer_output` — generated tasks.md (skip re-slicing on resume)
  - `ralph_loops_results` — validation status + iterations/loop (proof of validation)
  - `risk_assignments` — Risk Tier per phase (deterministic)
  - `readiness_verdict` — ready | paused (handoff decision)

- Intent Hash validation — cache invalidated if Intent drifts

### Escalation Paths (back to agent-isdd)

Four documented escalation markers for when Design Spec flow pauses:
- `AGENT-TDD-RESEARCH-VALIDATION-FAILED` — research gaps, needs targeted re-research
- `AGENT-TDD-DESIGN-CONTRADICTION` — design contradicts research, needs clarification
- `AGENT-TDD-SLICING-REQUIRES-DECISION` — high-risk slice cannot be split, needs user decision
- `AGENT-TDD-PLAN-VALIDITY-FLAGGED` — Ralph Loops hit max iterations, likely circular dependency

### Testing

- New integration tests (`test_design_spec_orchestration.py`):
  - 7 tests covering orchestration flow, early escalations, cache correctness, token budget adherence
  - All passing; token efficiency validated (23.5K within 18-28K budget)

### Documentation

- `ORCHESTRATION.md` — token-efficient orchestration design, caching strategy, resume flow
- Updated `SKILL.md` with 7-step flow, token budget breakdown
- Updated `INTEROP.md` with Design Spec contract (from agent-isdd) and agent-tdd responsibilities
- README updated with Design Spec capability, token efficiency gains

### Breaking Changes

- None (backward compatible with Slice Spec callers)

### Migration

- Existing Slice Spec callers (if any) still work via `slice-spec` skill
- New callers use Design Spec directly (recommended for agent-isdd integration)

## [0.1.7] - 2026-08-16

- Fixed `hooks/hooks.json`: converted from the array-of-`{event, command}` shape to the record
  format (event name keys, each mapping to matcher entries with a nested `hooks` array) that the
  Claude Code CLI plugin loader actually expects. The old shape made the plugin fail to load with
  `expected: record, received array`. Commands now also use `${CLAUDE_PLUGIN_ROOT}` so they resolve
  regardless of invocation cwd, matching sibling plugins' convention.

## [0.1.6] - 2026-08-16

- Added a **Plan Validity Flag** (optional handoff-report field, marked with a literal
  `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` line) to `agent-TDD.md`, distinct from the existing
  Research Gap Flag — signals that Red/Green/review work revealed the *task itself* conflicts
  with something more fundamental, not just a missing technical fact. Stays fully caller-agnostic:
  `agent-TDD` states the conflict, never a target phase or any caller-specific vocabulary.
  `INTEROP.md` documents `agent-isdd`'s own translation of this flag into its rewind mechanism as
  a worked example, closing the gap where `agent-isdd` previously expected this plugin to emit an
  SDD-specific `<!--SDD-ROLLBACK-REQUEST:...-->` marker it never actually did.
- New `INTEROP.md` section: an optional recipe for an orchestrator that resumes/monitors a full
  `agent-TDD` slice loop to render TDD-stage progress via `agent-ux:ux-agent`, using its own
  plugin identity as `caller` and a `phase_state` of the form `TDD:<stage>` — `agent-TDD` itself
  can never be a literal `caller` (no `Agent` tool). No plugin in this ecosystem does this today;
  the recipe exists for a future orchestrator that wants to.
- `hooks/tdd_subagent_stop.py` now detects the new Plan Validity Flag marker the same way it
  already detects Research Gap Flag: a new `has_plan_validity_flag` field in `tdd-progress.json`
  and a `plan_flag=yes|no` segment in the hook's `systemMessage`. Checks the marker line first
  (matching how the caller-side `agent-isdd` hook detects it), falling back to the prose section
  text so progress tracking stays accurate for a caller with no marker-based rollback path of its
  own.
- Added `references/slice-spec.schema.json`, a machine-checkable JSON Schema mirroring the Slice
  Spec contract documented in `INTEROP.md` (six fields, two required, two enums), plus
  `tests/test_slice_spec_schema.py` checking the schema stays in sync with that contract.
  Cross-linked from `INTEROP.md`.
- Added a `slice-spec` skill (`skills/slice-spec/SKILL.md`) that walks through gathering,
  validating, and formatting a Slice Spec before spawning `agent-TDD` or `test-author`.
- Added two more worked-example transcripts under `references/examples/`:
  `review-skip-slice.md` (Review handoff mode explicitly set to `skip`, no pause between Green and
  Refactor) and `research-gap-flag-slice.md` (the real code diverges from the Slice Spec's Data
  Contracts And Interfaces, so `agent-TDD` raises a Research Gap Flag instead of guessing).
  Cross-linked from `INTEROP.md`.
- Added `scripts/bump_version.py`, which moves `CHANGELOG.md`'s `[Unreleased]` entries under a new
  version heading and updates `.claude-plugin/plugin.json`'s version to match in one step, plus
  `tests/test_bump_version.py` covering it.
- Added `CLAUDE.md` documenting the "CUPS" release shorthand (bump → commit → push → stale-cache
  removal) for Claude Code sessions working in this repo.

## [0.1.5] - 2026-08-15

- Added `hooks/` (`tdd_session_start.py`, `tdd_subagent_stop.py`, `tdd_stop.py`, `tdd_state.py`,
  `hooks.json`) to track per-slice TDD progress across `SessionStart`/`SubagentStop`/`Stop`
  events without relying on NLP over the transcript. `agent-TDD.md`'s handoff report now emits a
  machine-readable `<!--AGENT-TDD-PHASE:...-->` marker (`green_pause` or `refactor_complete`) so
  the `SubagentStop` hook can update `tdd-progress.json` reliably.
- Added `tests/test_hooks_json.py`, `tests/test_tdd_session_start.py`, `tests/test_tdd_state.py`,
  `tests/test_tdd_stop.py`, `tests/test_tdd_subagent_stop.py` covering the new hooks.

## [0.1.4] - 2026-08-13

- Reduced duplicated prose across `agents/agent-TDD.md` and `agents/test-author.md`: collapsed
  five restatements of "no `Agent` tool" to a single mention per file (canonical explanation
  stays in `INTEROP.md`), trimmed the review-pause section to a caller-mechanics-free pointer,
  collapsed the Handoff Facts and Pre-Slice Brief explanations to short back-references, folded
  `test-author.md`'s "Why you're invoked at all" section into its Preconditions paragraph, and
  tightened the Loop Prevention guardrail bullet to a one-line pointer.

## [0.1.3] - 2026-08-12

- Added explicit token-efficiency guidance to `INTEROP.md`'s Slice Spec contract: pass exact
  excerpts (not whole files) for Data Contracts And Interfaces, scope them to the slice at hand,
  skip restating the Slice Spec when resuming an `agent-TDD` instance after the review pause, omit
  optional fields rather than inventing content, and keep `test-author`'s spawn prompt to its
  strict field subset. Tightened the matching field descriptions in `agent-TDD.md` and
  `test-author.md` to say the same thing.

## [0.1.2] - 2026-08-12

- Wired the existing `tests/` suite into CI via `.github/workflows/tests.yml`: runs on every
  push and pull request to `main`, across a Python 3.9-3.12 matrix, invoking
  `python3 -m unittest discover -s tests -p "test_*.py" -v`. No git-identity step (neither test
  file performs git/subprocess operations). Added a status badge to `README.md`.

## [0.1.1] - 2026-08-11

- Added a stdlib-only Python `unittest` suite under `tests/`: a version-sync check
  (`test_version_sync.py`) verifying `plugin.json`'s `version` matches `CHANGELOG.md`'s latest
  released heading, and a doc-consistency check (`test_doc_consistency.py`) verifying
  `agent-TDD.md` and `test-author.md` stay consistent with the Slice Spec contract documented in
  `INTEROP.md`. Run via `python3 -m unittest discover -s tests -p "test_*.py" -v`; no CI wiring,
  no new dependency.
- Added two worked-example transcripts under `references/examples/`
  (`standard-tier-slice.md`, `high-risk-tier-slice.md`) demonstrating the Slice Spec contract end
  to end, including the two-part `test-author` → `agent-TDD` high-risk invocation. Cross-linked
  from `INTEROP.md`.

## [0.1.0] - 2026-08-11

- Extracted from `spec-driven-development`'s internal `agent-TDD` + `test-author` agents into a
  standalone plugin, mirroring how `agent-nelly` was pulled out of SDD for memory. `code-reviewer`
  was deliberately left behind — it's useful standalone beyond just gating TDD slices, and is
  planned as its own separate plugin rather than bundled here (see README's "Why not
  code-reviewer too" section).
- Replaced SDD's file-format coupling (`<sdd-memory-dir>/spec/<date-slug>/tasks.md`,
  `design.md`, `REVIEW-STATE.md`) with a generic **Slice Spec** the caller passes inline in the
  spawn prompt (task description, acceptance criteria, Risk Tier, optional Data Contracts And
  Interfaces, optional Pre-Slice Brief). No orchestrator-specific concepts remain in either
  agent's own instructions.
- Generalized the mandatory review gate: `agent-TDD` no longer names `code-reviewer` specifically
  and instead always pauses after Green for **caller-driven review** — any reviewer the caller
  has available (an agent, a lint pass, a human) — unless the caller's Slice Spec explicitly sets
  Review handoff mode to skip it. This preserves the safety property (no unreviewed refactor)
  without hard-coding a dependency on any specific reviewer plugin.
- SDD's own internal copies of `agent-TDD`/`test-author` are unchanged for now — this plugin
  ships standalone alongside them rather than replacing them, so the current SDD release carries
  zero risk while this plugin is validated. See the parent conversation's migration decision:
  full cutover is deferred.
