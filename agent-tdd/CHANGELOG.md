<!-- TDD-SKIP -->
## [Unreleased]

## [0.2.7] - 2026-09-20

- **Release**: bump version for plugin collection public release (Phase 9).

## [0.2.6] - 2026-09-20

- **CI**: added to python-tests CI matrix; Phase 8 CI expansion.

## [0.2.5] - 2026-09-20

- **Fix**: remove stale `injected_test_field` test artifact from Design Spec Input Format table in INTEROP.md; fix malformed `nelly_brief_cache` row (was missing description column).

## [0.2.4] - 2026-09-20

- **Pre-commit hook**: wire interop drift validator to `.githooks/pre-commit` + CI `interop-drift` job.

## [0.2.3] - 2026-09-20

- **Consistency pass**: wire `ux_render` hook cache stubs to real HTTP calls (localhost:7771); `render_phase_transition` now emits structured agent-ux delegation instruction in systemMessage; convert Design Spec Input Format bullet list in INTEROP.md to proper markdown table so schema extractor finds the correct fields.

## [0.2.2] - 2026-09-20

### Features

- **Model Tier Selection** (`slice-spec.schema.json`): New `modelTier` field
  (`inherit`/`haiku`/`sonnet`/`opus`) lets callers suggest a model tier per slice, defaulting to
  `inherit` for full backward compatibility.
- **Model Escalation Protocol** (`escalation-paths.md`): Documents the `MODEL-ESCALATE` marker
  for mid-slice escalation when a lower model tier proves insufficient, with corrected canonical
  field names (`from_model`/`to_model`, with `attempted_at_haiku`/`suggest_tier` retained as
  backward-compatible aliases).

## [0.2.0] - 2026-09-18

**Feature: Comprehensive Tiered Review Integration for ISDD**

### Features

- **Per-Slice Code Review Integration** (`agent-TDD.md`): Full Red-Green-Refactor review checkpoints with Quick (red), Standard/Deep (green based on risk tier), and conditional review holds before refactor
- **Coherence Review Gate** (`agent-TDD.md`): Post-all-slices validation with Deep (≤50% high-risk) or Ultra (>50% high-risk) level selection, comprehensive cross-slice interaction checking
- **Auto-Detection Logic** (`agent-TDD.md`): Context-driven review level selection with 5-priority hierarchy (explicit → phase → scope → prior → fallback) plus 6 real-world scenario examples
- **Ralph Loops Traceability Enhancement** (`agent-TDD.md` Loop 3): Review-level findings validation, design-phase coverage, per-slice coverage, coherence coverage, file-to-review-level mapping, risk coverage validation
- **ISDD Phase Context Documentation** (`SKILL.md`): Phase-to-level mapping table for Requirements/Design/Tasks/Per-Slice/Coherence phases with auto-detection priority order and concrete examples

### Testing

- 22 per-slice review invocation tests (Red/Green/Refactor, risk tier mapping, error handling)
- 27 coherence gate tests (level determination, scope collection, finding categorization, gate decisions, ledger storage)
- 27 auto-detection logic tests (all 5 priorities, 6 real-world scenarios)
- 29 ralph loops traceability tests (coverage validation, finding consistency, file mapping, risk coverage)
- 37 end-to-end integration tests (full workflow requirements → design → tasks → per-slice → coherence → ralph loops)

### Documentation

- Updated SKILL.md with ISDD Phase Context section and auto-detection rules
- Enhanced INTEROP.md with Strategic Review Placement by Phase table and ralph loops integration details
- Comprehensive cross-references to code-reviewer, agent-isdd, and design.md

### Improvements

- Backward compatible: Standard review remains default level when not specified
- Graceful degradation for unavailable review levels (Ultra → Deep → Standard cascade)
- Findings validation across all phases with conflict detection and escalation

## [0.1.19] - 2026-09-18

**Feature: Tiered Reviewing Strategy for Agent-TDD**

### Features

- **`SKILL.md`** (new): "Review-Level Strategy" section documenting per-slice review checkpoints (Quick/Standard/Deep), coherence gate logic (Deep/Ultra based on high-risk composition), and auto-detection priority rules (phase context, risk tier, file scope, fallback).
- **`agents/task-slicer/SKILL.md`** (new): Standard review invocation on tasks.md output, validating task clarity, Depends-On correctness, and sequencing before implementation begins.

### Improvements

- **Per-slice reviews** integrated into Red-Green-Refactor: Quick (red) → Standard/Deep (green, risk-tier-dependent) → Quick (refactor checkpoint)
- **Coherence review gate**: After all slices complete, invoke Deep (standard composition) or Ultra (>50% high-risk slices) review to validate cross-slice interactions, regressions, and module boundaries
- **Auto-detection logic**: Review level inferred from ISDD phase + risk context, supporting context-driven tier selection without explicit caller specification

### Integration

- Ralph loops Traceability validation enhanced to ingest review-level findings from all phases
- Backward compatible: existing agent-tdd workflows work unchanged (Standard level is default)

## [0.1.18] - 2026-09-17

**Feature: Direct Mode (harness `Agent`-spawn failure fallback)**

### Fixes & Improvements

- **`skills/design-spec-direct/SKILL.md`** (new): reproduces Design Spec Mode's Research
  Validation/Task Slicing/Ralph Loops/Risk Tier Assignment and Slice Spec Mode's per-slice
  Red/Green/Review/Refactor contract as a `Skill` invocation instead of an `Agent`-tool spawn,
  for use only when a caller has confirmed (per `INTEROP.md`'s new "Direct Mode" section) that
  the `Agent` tool itself is failing at the harness level in the current session. The caller
  owns the per-slice loop (`plan` → per-slice `test-author`/`slice`/review/`refactor` →
  `summary`) instead of trusting an isolated subagent to run it unsupervised — see that skill
  file's "What is genuinely lost" and "One thing this mode actually gains" sections for the
  explicit isolation/checkpoint-recoverability tradeoffs this implies.
- **`hooks/direct_mode_state.py`** (new): `read_direct_mode_state`/`write_direct_mode_state`/
  `set_slice_status`/`all_slices_done`/`first_incomplete_slice_id` — persists Direct Mode's
  per-slice progress to `direct-mode-state.json`, mirroring `tdd_state.py`'s existing read/write
  pattern. Found and fixed during review: the missing-file fallback originally shallow-copied
  the module-level default shape, sharing its nested `slices` list by reference across every
  caller that ever hit that path — one project's `set_slice_status` call would permanently leak
  into another project's "no state yet" read for the rest of the process. Fixed with
  `copy.deepcopy`; covered by a regression test.
- **`INTEROP.md`**: new "Direct Mode (harness `Agent`-spawn failure fallback...)" section
  cross-referencing the new skill; documented as a fallback, not a second supported day-to-day
  path for Design Spec Mode.

109 tests pass (12 new).

## [0.1.16] - 2026-09-16

**Feature: Test-Author Gate for Design Spec Mode high-risk slices**

### Fixes & Improvements

- **`agents/agent-TDD.md`**: "After Readiness Passes" now stops at `slicing_complete` when
  `tasks.md` contains one or more `high-risk` slices, instead of proceeding straight into
  implementation with no way for the caller to have supplied `test-author`'s output. Zero
  high-risk slices: no behavior change. The `slicing_complete` handoff report gains a new
  **High-Risk Slices** field naming them (previously only a count was reported). Replaces an
  abandoned caller-side-marker approach (`AGENT-TDD-TEST-AUTHOR-NEEDED`) added and removed the
  same day it was added, once it became clear the existing `slicing_complete` marker plus
  `tasks.md` already on disk were sufficient signal on their own.
- **`INTEROP.md`**: "Design Spec Mode" section rewritten to describe this gate, matching
  `agent-isdd/INTEROP.md`'s corresponding section exactly (both files edited together in the
  same change).

89 tests pass.

## [0.1.15] - 2026-09-16

**Critical: fix a packaging bug breaking every fresh install**

### Fixes & Improvements

- **`hooks/tdd_state.py`** imported `path_resolution` from a monorepo-relative `shared/`
  directory — only resolves inside the dev checkout, never in a marketplace-installed package,
  which bundles only this plugin's own subdirectory. Every hook depending on `tdd_state.py`
  raised `ModuleNotFoundError` on a real fresh install of any version since the
  `${CLAUDE_PLUGIN_DATA}` migration (0.1.11+). Fixed by giving this plugin its own local copy
  of `path_resolution.py` in `hooks/`, verified by copying `hooks/` alone to an isolated tmp
  directory with no monorepo present and confirming it still imports.

## [0.1.14] - 2026-09-16

**Fix: stale readiness-check references left after the modular design-spec retirement**

### Fixes & Improvements

- **`INTEROP.md`'s "Readiness Check & Escalation" section** still named a `readiness-check`
  agent as the emitter of the Readiness Check verdict and the `AGENT-TDD-PLAN-FLAG` marker — a
  leftover reference to the subagent deleted in 0.1.13's modular-pipeline retirement. Corrected
  to `agent-TDD` itself, matching the inline path that's the only one left.

## [0.1.13] - 2026-09-16

**Remove: dead modular Design Spec pipeline**

### Fixes & Improvements

- **Retired the modular `design-spec` skill** (`skills/design-spec/SKILL.md`,
  `skills/design-spec/ORCHESTRATION.md`) and its five dedicated subagents
  (`agents/research-validator.md`, `agents/task-slicer.md`, `agents/ralph-loops.md`,
  `agents/risk-assign.md`, `agents/readiness-check.md`), plus
  `references/design-spec.schema.json` and their associated tests. This pipeline was
  independently-maintained drift alongside `agent-TDD`'s own inline Design Spec Workflow —
  no known caller ever invoked it (`agent-isdd` always spawns `agent-TDD` directly), and it
  emitted an incompatible escalation-marker vocabulary that `agent-isdd`'s own hooks never
  recognized. See `INTEROP.md`'s "Design Spec Mode" section for the full history.
- Updated `README.md` and `INTEROP.md` to describe the single remaining (inline) Design Spec
  path.
- **`INTEROP.md`'s Design Spec Input Format** now notes `recap.md` should be summarized rather
  than pasted in full for a long-running feature — matches the same guidance added to
  `agent-isdd/INTEROP.md` and `spec-driven-development/SKILL.md`'s handoff-construction steps.

## [0.1.12] - 2026-09-16

**Fix: test-isolation leak in `${CLAUDE_PLUGIN_DATA}` env var tests**

### Fixes & Improvements

- **`tests/test_tdd_state.py`** — the three `ClaudePluginDataEnvVarTests` tests
  `importlib.reload()`'d `tdd_state` inside a `patch.dict(os.environ, ...)` context but never
  reloaded it back afterward, permanently corrupting the module-global `BASE` in `sys.modules`
  for every test file collected later in the same run (`test_tdd_stop.py`,
  `test_tdd_subagent_stop.py`). Each test now reloads `tdd_state` again after its patched-env
  context exits, restoring `BASE` to its real value regardless of test outcome.

## [0.1.11] - 2026-09-16

**Chore: storage directory migration**

### Fixes & Improvements

- **`${CLAUDE_PLUGIN_DATA}` env var support** — `hooks/tdd_state.py`'s `BASE` now resolves via the
  official `${CLAUDE_PLUGIN_DATA}` env var, falling back to `~/.claude/plugins/data/agent-tdd/`
  when unset, instead of a hardcoded `~/.claude/agent-tdd-state/` path

## [0.1.10] - 2026-09-15

**Fix: ecosystem audit compatibility fixes**

### Fixes & Improvements

- **INTEROP.md drift** — documented that "Design Spec Mode" has two independent, non-interchangeable implementations: the inline pipeline in agent-TDD.md (what agent-isdd actually spawns) and the modular `skills/design-spec.md` pipeline, previously undocumented

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
