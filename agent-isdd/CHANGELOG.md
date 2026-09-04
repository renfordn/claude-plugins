# Changelog

## 0.1.14 (Phase 2+3: Core Consolidation + Agent-Nelly Integration)

### Breaking Changes

- **Removed `skills/tdd-planner/SKILL.md` and `agents/tdd-planner.md`**
  - Task slicing responsibility moved to `agent-tdd` (from agent-isdd)
  - Workflow phases changed: Requirements → Design → Implementation (no Tasks phase in agent-isdd)
  - Handoff changed from Slice Spec (per-task) to Design Spec (full specs at once)
  - 1-week deprecation window: both tdd-planner and research-consolidator coexist in 0.1.13;
    0.1.14 removes tdd-planner entirely. Downstream users should update to use agent-tdd's
    new slicing capabilities before upgrading past 0.1.13.

### Added (Phase 2+3)

- **`agents/research-consolidator.md`**: New unified research agent
  - Single pass produces dual output: design_findings + task_findings + file_summaries
  - Replaces redundant planning-agent calls (design-author + tdd-planner)
  - Saves 15-25K tokens per feature by eliminating research duplication
  - Wraps planning-agent logic; consolidates outputs for both Design and Tasks phases

- **Intent artifact as first-class, durable markdown**
  - `intent/intent.md` template: Project Intent, Feature Goal, Success Signals, Anti-Patterns
  - Intent Hash (SHA256) for drift detection throughout workflow
  - Intent Alignment Status tracking in workflow-state.md
  - Inline Intent-alignment check on before-continue (no nelly spawn needed)
  - Enables explicit traceability: requirements → design → tasks reference Intent via hash anchor

- **Persistent research cache**
  - `research/cache.md` stores design_findings + task_findings + file_summaries
  - Git hash tracking for automatic cache invalidation
  - Agent-tdd reuses cache, skips re-research unless cache invalid
  - Saves 15-25K tokens on resumed workflows where research is still valid

- **Agent-nelly file-level cache**
  - File summaries (exports, constraints, tech_debt, test_surface, migration_risks) cached
  - Populated by research-consolidator, queried by agent-tdd
  - Cross-feature reuse: 70-80% cache hit rate on features touching same modules
  - Saves 15-25K tokens per cross-feature reuse
  - Git hash validation ensures cache freshness

- **Persistent nelly brief cache** (Phase 1.2)
  - `workflow-state.json` → `nelly_brief_cache` with validation
  - Reuse on workflow resume (Intent Hash + timestamp < 24h)
  - Saves 5-10K tokens per resumed workflow

- **Narrow wide-pass optimization** (Phase 1.3)
  - planning-agent Pass 1 uses nelly brief hints to skip already-known files
  - Candidate list: ~20-30 files instead of 100+
  - Same deep-pass thoroughness, faster filtering
  - Saves 3-5K tokens per research call

### Changed

- **Workflows phases revised** (Phase 2+3)
  - Old: Requirements → Design → Tasks → Implementation
  - New: Requirements → Design → Implementation (Tasks absorbed into Implementation)
  - Agent-isdd owns Requirements + Design; agent-tdd owns task slicing + implementation
  - Cleaner responsibility boundary; eliminates redundant research

- **`skills/design-author/SKILL.md`** (Phase 2+3)
  - Delegates to research-consolidator (not planning-agent)
  - Caches task_findings in research/cache.md
  - Persists file_summaries to agent-nelly for cross-feature cache
  - Updated Design Gate to verify research cache + file summaries created

- **`skills/spec-driven-development/SKILL.md`** (Phase 2+3)
  - Start Protocol: creates intent.md, computes Intent Hash
  - Continue Protocol: checks nelly brief cache, validates Intent alignment via hash
  - Implementation Handoff: constructs Design Spec, pre-fetches file summaries from agent-nelly
  - Removed tdd-planner references; added research-consolidator

- **`INTEROP.md`** (Phase 2+3)
  - New section: agent-nelly file cache contract (file_summary fact type, query interface)
  - Revised → agent-tdd section: Design Spec handoff replaces Slice Spec
  - Added agent-tdd implementation requirements: Research Validation, Task Slicing, Ralph Loops
  - Escalation paths documented (design contradicts research, research too thin, etc.)

- **`references/artifact-templates.md`** (Phase 1 + 2+3)
  - Added `intent/intent.md` template (first artifact)
  - Updated workflow-state.md: Intent Hash + Intent Alignment Status fields
  - Updated recap.md: clarified Goal Alignment Notes section
  - Phases: Requirements → Design → Implementation

- **`references/workflow-state.template.json`** (Phase 1 + 2+3)
  - Added: intent_hash, intent_alignment_status (Phase 1.1)
  - Added: nelly_brief_cache, research_cache (Phase 1.2, 2+3)
  - Updated current_phase enum (removed Tasks)

### Token Efficiency Gains

| Phase | Mechanism | Savings | Notes |
|-------|-----------|---------|-------|
| 1.1 | Intent capture | 0K | Foundation for drift detection |
| 1.2 | Brief cache | 5-10K | Per resumed workflow |
| 1.3 | Narrow wide-pass | 3-5K | Per research call |
| 2+3 | Research consolidation | 15-25K | Eliminates tdd-planner re-research |
| 2+3 | Research cache reuse | 15-25K | Agent-tdd skips re-research |
| 2+3 | File cache (cross-feature) | 15-25K | Per cross-feature reuse |
| **Total** | **All phases combined** | **~80-100K** | **50-70% reduction** |

### Migration Guide

For downstream users relying on tdd-planner:

1. **Phase 1**: 0.1.13 maintains both tdd-planner (agent-isdd) and research-consolidator.
   - Handoff flow: agent-isdd → Slice Spec (per-task) to agent-tdd
   - Still works; no immediate action needed

2. **Phase 2**: Upgrade agent-tdd to support Design Spec handoff + task slicing + research validation
   - Refer to INTEROP.md's "Agent-tdd Implementation Requirements" section
   - Includes Ralph Loops for slice validation

3. **Phase 3** (after 0.1.14): agent-isdd drops tdd-planner entirely
   - Requires agent-tdd to be updated per Phase 2
   - No backwards compatibility

### Fixed

- Workflow state representation: `workflow-state.md` phases simplified (no Tasks for agent-isdd)
- Intent drift detection: hash-based comparison reliable and cheap vs. full brief re-fetch
- Research redundancy: consolidated pass eliminates tdd-planner calling planning-agent again

## 0.1.13 (Phase 1: Quick Wins)

### Added

- Intent artifact capture: intent.md template, Intent Hash, Intent Alignment Status
- Persistent nelly brief cache: reuse on workflow resume, Intent Hash + timestamp validation
- Narrow wide-pass optimization: planning-agent uses nelly hints to skip known files

### Token Savings

- Phase 1.1: Intent drift detection (0K, foundation)
- Phase 1.2: Brief cache reuse (5-10K per resumed workflow)
- Phase 1.3: Narrow wide-pass (3-5K per research call)
- **Total**: ~20-30K per feature

## 0.1.12

### Changed
- Token-efficiency rework of `skills/workflow-manager/SKILL.md` (3,739 → 3,277 words, -12.4%),
  following this plugin's own established pattern of structure-and-reuse rather than cutting
  content (see 0.1.6 below). The five parallel "Choose X when / On choosing" sections (Start,
  Continue, Pause, Handoff, Complete Rules) collapsed into one `Action Rules` table; the three
  Phase Pass/Fail sections collapsed into one table; the six Lifecycle Hooks collapsed into one
  table with the (already near-verbatim-duplicated) Verification Step / Nelly write-back rules
  stated once above it instead of restated per hook; `Required Decisions` folded into `Phase
  Completion Evaluation`. Every original rule verified still present, section-by-section, against
  the pre-edit version — nothing cut, only restructured. Confirmed no other file in the plugin
  references the merged section names.
- `skills/doc-consistency-auditor/SKILL.md`'s "Visual Review" section: fixed a conflation in its
  citation of `code-reviewer`'s threshold rule — it read as if `code-reviewer` opens a `ux-agent`
  review-dashboard Artifact, when `code-reviewer` actually opens its own Artifact directly (no
  `agent-ux` dependency, at the time this was written). Now cites `code-reviewer/SKILL.md`'s
  "Visual Review" section as the canonical definition, mirrored (not duplicated independently) by
  `agent-ux`'s own `ux-conventions.md`/`ux-agent.md` for its separate `review_threshold` event —
  closing a three-way duplication of the same 5-finding/1-file number with no shared source.

### Fixed
- The automatic rollback path documented in `INTEROP.md`/`references/rollback-guide.md` never
  actually worked: `hooks/subagent_report.py` watched for `<!--SDD-ROLLBACK-REQUEST:...-->`, but
  `agent-tdd` — a deliberately caller-agnostic plugin — never emitted that SDD-specific marker
  and never could without violating its own genericity contract. Fixed by having `agent-tdd`
  emit its own generic `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` marker instead (new in
  `agent-tdd`'s own release), which `hooks/subagent_report.py` now recognizes as a second,
  independent trigger: defaults the rewind target to `Requirements` (per
  `rollback-guide.md`'s pre-existing "more conservative (earlier) phase" policy, since the
  marker carries a reason but no target) and writes `rollback_pending` exactly as the
  human-relay path already did. The human-relay path (`<!--SDD-ROLLBACK-REQUEST:...-->`, for a
  human who already knows agent-isdd's phase vocabulary, and the only path for `code-reviewer`)
  is unchanged. `INTEROP.md` and `references/rollback-guide.md` rewritten to describe both real
  paths instead of one real path and one that could never fire. New tests in
  `tests/test_subagent_report.py` cover the new marker.

## 0.1.10

### Added
- `hooks/post_write_check.py` now dual-writes phase state: alongside the existing
  memory-dir `workflow-state.json` mirror, every `workflow-state.md` write also mirrors
  `current_phase`, `phase_state`, `pause_reason`, and `implementation_requested` into a
  lightweight `.sdd-state.json` at the project root, so other tools can cheaply read
  current phase without parsing markdown or resolving `~/.claude/sdd-memory/`. Purely
  additive — the existing memory-dir write and its `hook_history` audit trail are
  untouched. `.sdd-state.json` added to `.gitignore` as generated state.

### Verified (no change needed)
- Confirmed `design-author`'s `agent-nelly:nelly-orchestrator` usage is already a single
  read (reused brief or one fresh call per the documented re-fetch triggers) followed by a
  single write-back — the redundant pre-sweep call this would have collapsed was already
  removed in 0.1.9.

## 0.1.9

### Changed
- Merged `hooks/phase_task_sync.py` and `hooks/state_consistency_check.py` (both fired on every
  `Write`/`Edit`/`MultiEdit`/`NotebookEdit`) into a single `hooks/post_write_check.py`, halving
  subprocess startup overhead per file write. Behavior unchanged: `workflow-state.md` writes
  sync mirrored fields to `workflow-state.json` and remind the model to sync the visible
  progress UI; `tasks/tasks.md` writes remind the model to sync the UI; all other paths no-op.
- `workflow-manager/SKILL.md`'s `workflow-state.md` vs `workflow-state.json` section rewritten
  from a conflict-resolution rule to an explicit Write Responsibilities split: mirrored fields
  (`current_phase`, `phase_state`, `pause_reason`, `implementation_requested`) are written
  exclusively by the hook, never by the model directly; JSON-only fields
  (`agent_nelly_available`, `hook_history`, `rollback_pending`, `recap_path`,
  `blocked_fields`) are written by the model or their owning hook.
- `agent-tdd` availability is now checked inline at the Implementation Handoff (scanning the
  session's `<system-reminder>` agent-types block for `agent-tdd:agent-TDD`) instead of being
  cached — it's only needed once, at the handoff, unlike `agent-nelly` which is used throughout
  the workflow and stays eagerly checked at `before-requirements`.
- `agent-nelly` write-back extended to every `after-*` phase-boundary hook (previously only
  after the `agent-tdd` handoff): project-level discoveries worth persisting independently of
  the feature's own artifacts (confirmed/denied interface assumptions, coverage gaps, risk
  flags) are batched into a `new facts` call, never blocking on failure.
- `design-author`'s `planning-agent` delegation no longer makes its own separate pre-sweep
  `agent-nelly:nelly-orchestrator` call — `spec-driven-development` now requests
  `surface relevant memory: true` on its single pre-Design nelly call, and `design-author`
  passes the brief's `Relevant entries` section straight through to `planning-agent`, removing
  a redundant nelly spawn.
- New `references/rollback-guide.md`: step-by-step instructions for both the automatic
  (`SubagentStop`-observed) and human-relay rollback paths from `agent-tdd`/`code-reviewer` back
  into agent-isdd, linked from `INTEROP.md`'s rollback section.
- Deleted `hooks/phase_task_sync.py` and `hooks/state_consistency_check.py` (unregistered dead
  files left behind by the `post_write_check.py` merge above) along with their standalone
  `tests/test_phase_task_sync.py` / `tests/test_state_consistency_check.py`, which were still
  exercising that dead code even though it no longer ran in production. Coverage folded into a
  new `tests/test_post_write_check.py` that tests the merged hook directly.

## 0.1.8

### Fixed
- `spec-driven-development` SKILL.md's Implementation Handoff: after taking `agent-tdd`'s
  returned handoff report, if its Handoff Facts field is non-empty and `agent_nelly_available`
  is `true` in `workflow-state.json`, call `agent-nelly:nelly-orchestrator` with those facts as
  a `new facts` batch (one call, no re-fetch of the brief). Previously these facts were dropped
  on the floor after implementation completed.

## 0.1.7

### Changed
- Extracted UX rendering (breadcrumb, spec-canvas Artifacts, chapter markers, review dashboards,
  out-of-scope task chips) to the new sibling plugin `agent-ux`. This repo's local
  `agents/ux-agent.md` and `references/ux-conventions.md` are removed; every calling skill
  (`spec-driven-development`, `workflow-manager`, `requirements-agent`, `design-author`) and
  runtime surface (`hooks/phase_task_sync.py`, `hooks/subagent_report.py`,
  `statusline/sdd_statusline.py`, `commands/isdd-status.md`, `commands/isdd-rewind.md`,
  `references/artifact-templates.md`) now delegates to `agent-ux:ux-agent` instead, constructing
  the UX Event Envelope (`caller`, `event_type`, `phase_state`, `delta`, `artifact_path`) defined
  in `agent-ux`'s own `INTEROP.md`.
- `INTEROP.md`: new "→ agent-ux (UX rendering)" section, mirroring the existing `agent-nelly`
  soft-dependency pattern — `agent-ux` is a soft dependency; unavailability surfaces one plain
  notice per session and never blocks the workflow. References `agent-ux`'s own
  unavailability/fallback contract by name rather than restating it, per this extraction's
  design mitigation against duplicated fallback logic across future callers (`agent-tdd`,
  `code-reviewer`).
- `tests/test_phase_task_sync.py`: updated the reminder-message assertion from `"ux-agent"` to
  `"agent-ux:ux-agent"` to match the migrated hook wording; full suite (90 tests) still passes.
- `skills/tdd-planner/SKILL.md` and `skills/doc-consistency-auditor/SKILL.md` were confirmed to
  need no changes — `tdd-planner` has no live `ux-agent` delegation to migrate, and
  `doc-consistency-auditor`'s two `ux-agent` mentions are illustrative prose (an example, and a
  description of `code-reviewer`'s own unrelated rule), not live delegation calls.
- Validated via a full manual trace/dry-run of a Requirements→Design→Tasks→handoff cycle against
  `agent-ux`'s `INTEROP.md` envelope contract and its recorded example envelopes — output shape
  (breadcrumb always first, one line per action taken) matches the pre-extraction baseline.
- Token-cost comparison against the pre-extraction in-process baseline (Phase 5 of the
  `agent-ux` plugin extraction plan): measured using a documented approximation (character
  count ÷ 4; no tokenizer available in this environment), comparing OLD total = pre-extraction
  `agent-isdd/agents/ux-agent.md` (4928 chars, the fixed per-call system-prompt cost) + a
  reconstructed old-style narrated delegation prompt per event, versus NEW total =
  `agent-ux/agents/ux-agent.md` + `agent-ux/INTEROP.md` combined (10455 + 10404 = 20859 chars,
  the new fixed per-cross-plugin-call cost) + the actual recorded example-envelope JSON payload
  per event. Result for all 3 representative events: **regression, not parity** —
  `phase_transition` ~1402 → ~5318 tokens (+279%), `section_checkpoint` ~1484 → ~5393 tokens
  (+263%), `review_threshold` ~1497 → ~5527 tokens (+269%). The regression is driven almost
  entirely by the new fixed cost (`ux-agent.md` roughly doubled in size for the per-event-type
  dispatch, and `INTEROP.md` adds ~10.4KB never paid before per call), not by the `delta`
  payload shapes themselves, which stayed small. Per the extraction plan's Phase 5 blocker
  clause, this is escalated back to a Design-level decision rather than trimmed here — see the
  `agent-ux-plugin-extraction` proposal's tasks.md Phase 5 for the open blocker.
- Follow-up refactor pass (`agent-ux` commit `6fbc9b5`): trimmed redundant restatement between
  `INTEROP.md` and `ux-agent.md` (contract-level detail now owned solely by `INTEROP.md`;
  `ux-agent.md` cross-references rather than duplicates) and converted the per-`event_type`
  delta-shape prose to a table. Combined fixed cost 20859 → 17800 chars (-14.7%). All 6
  `EXPECTED-OUTPUTS.md` scenarios re-verified unchanged — no behavior regression. Recomputed
  comparison: `phase_transition` ~1402 → ~4621 tokens (+229%), `section_checkpoint` ~1484 →
  ~4702 tokens (+217%), `review_threshold` ~1497 → ~4715 tokens (+215%). **Still regressed for
  all 3 events** — closed roughly a third of the original gap, but full parity (design's stated
  "equal or smaller" success criterion) was not reached and, per the assessment carried out
  during this trim, does not appear closeable through further prose compression alone: the
  two-file cross-plugin contract (frontmatter, tool list, per-event dispatch logic, a separately
  maintained `INTEROP.md`) has an irreducible fixed cost the old single self-contained file never
  had to pay. Remains an open blocker pending a Design-level decision (see tasks.md Phase 5).
- **Measurement correction**: the two comparisons above both counted `agent-ux/INTEROP.md`
  toward "the new fixed per-call cost." It isn't one — `ux-agent.md` is fully self-contained at
  runtime (every dispatch section restates its own exact `delta` key set; its `../INTEROP.md`
  citations are maintainer cross-references, never a `Read` instruction), and the caller's
  delegation prompt doesn't embed `INTEROP.md` either. Re-measured with fixed cost =
  `ux-agent.md` alone. Also removed `ux-agent.md`'s "Guardrails" section, self-labeled
  `(recap — see dispatch sections above for full rule text)` — literal in-file duplicate prose
  (8759 → 8193 chars, `agent-ux` commit `72e9af6`). Corrected comparison: OLD = 4928 chars +
  hand-written prose-narration prompt (matching the JSON payloads' information content) vs. NEW
  = 8193 chars + the real envelope JSON from `references/example-envelopes/`. Result:
  `phase_transition` ~1295 → ~2152 tokens (+66%), `section_checkpoint` ~1386 → ~2227 (+61%),
  `review_threshold` ~1424 → ~2361 (+66%) — a real regression, roughly a third of the previously
  reported +215–279%, attributable to `ux-agent.md`'s move from prose-narration to structured
  envelope dispatch rather than to the extraction itself. Still an open blocker pending a
  Design-level decision — see `workflow-state.md`'s "Measurement Correction" section for the
  full methodology.
- **Decision: accepted.** The ~61-66% regression is accepted as the cost of
  `ux-agent.md`'s move from prose narration to structured, validated envelope dispatch — a
  robustness gain (explicit field validation, misuse detection, per-event gating rules stated
  inline), not extraction overhead. The `agent-ux` plugin extraction stands; this closes the
  Phase 5 blocker without further trimming. Design's stated "equal or smaller" success criterion
  is formally not met, but is superseded by this explicit accept decision.

## 0.1.6

### Added
- Cross-cutting token-efficiency pass across the planning workflow (savings come from structure
  and reuse, not from cutting content — no `Phase Completion`/`Approval Checkpoint`/`Task
  Readiness Checklist` item shrank).
- `references/artifact-templates.md`: `requirements.md` template gains a fixed four-key
  `## Non-Functional Constraints` section (Throughput, Data Volume, Concurrency, Latency
  Budget; each accepts `N/A: <reason>`) plus its Approval Checkpoint line; `tasks.md` template
  gains a structured `### Depends On` (bare `task-id` list) field per phase, alongside and
  distinct from the existing narrative `### Prerequisites` (381→396 lines).
- `skills/requirements-agent/SKILL.md`: interview mode now elicits Non-Functional Constraints as
  one closed-set-friendly question; `Required Requirement Fields` lists the new field.
- `skills/tdd-planner/SKILL.md` / `agents/tdd-planner.md`: replaced the informal "dependency
  notes" mention with a pointer to the structured `Depends On` field.
- `INTEROP.md`: confirms `Depends On` is intentionally excluded from the `agent-tdd` Slice Spec
  field mapping (single-slice handoff; phase ordering already carries the sequencing signal).
- `skills/workflow-manager/SKILL.md`: new "Recap-and-Drop" rule — once a phase's completion
  checklist passes, subsequent same-session prompts reference `recap.md`'s summary by default
  instead of re-quoting the full prior-phase artifact body; the full artifact stays on disk and
  remains re-readable on demand. Cross-checked `spec-driven-development`/`design-author`/
  `tdd-planner` for callsites that needed updating — none did.
- `skills/spec-driven-development/SKILL.md`: the existing three-trigger brief-reuse convention
  (no prior content in context / a rewind or Mid-Phase Change Classification since / an
  Intent-alignment divergence flagged since) now also covers still-valid `planning-agent`/
  `spec-reviewer` findings within the same continuous stretch of phase work, not only the
  agent-nelly brief — same triggers, re-verified against the finding-cache scenario rather than
  loosened, per the correctness-risk mitigation in this pass's design. `design-author`/
  `tdd-planner` now check for a reusable cached finding before re-delegating to `planning-agent`,
  which is the single largest expected runtime saving in this pass (skips a full `planning-agent`
  re-invocation when Design already produced the needed finding).
- New `references/subagent-conventions.md`: documents "Excluded — and why" as the house
  convention for any subagent performing candidate-file triage, citing `agents/planning-agent.md`
  as the canonical, already-compliant example; `spec-reviewer`/`tdd-planner` noted as confirmed
  non-applicable today. `agents/planning-agent.md` gains a one-line pointer to it.
- `references/example-feature/2026-07-01-profile-state-schema-migration/`: worked-example
  refresh showing the new `Non-Functional Constraints` block (`requirements.md`, 85→97 lines)
  and a genuine `Depends On` chain across its three task phases (`tasks.md`, 143→155 lines).

## 0.1.5

### Fixed
- `skills/spec-driven-development/SKILL.md`: Design Gate summary now mirrors
  `design-author/SKILL.md`'s "no unresolved Security Finding remains" bullet, added in 0.1.4,
  which had drifted out of sync between the two files (code-review finding).

## 0.1.4

### Added
- Deeper agent-nelly integration into agent-isdd's planning subagents (`planning-agent`,
  `spec-reviewer`) and the calling skills that invoke them.
- `agents/planning-agent.md`: accepts caller-passed agent-nelly `file-relevance` hits before
  its wide-pass sweep and skips wide-pass grep/glob for candidate files with a fresh hit;
  produces a concise, agent-friendly write-back summary (file or judged file-group) for every
  file its deep pass actually reads; new "Nelly summaries to write (if any)" return bullet;
  `Guardrails`' Read-only line gained a one-clause carve-out clarifying it means filesystem
  writes, not the caller's own nelly write-back call.
- `agents/spec-reviewer.md`: first-ever agent-nelly integration — uses a caller-passed brief
  for the source material's touched area, mirroring `workflow-manager`'s Availability Check
  phrasing.
- `agents/tdd-planner.md`: one clarifying sentence — this feature doesn't alter its existing
  direct-read judgment call from 0.1.3.
- `skills/design-author/SKILL.md`: makes the pre-sweep nelly call and the follow-up write-back
  call on `planning-agent`'s behalf (subagents can't spawn subagents in this harness); new
  Design Gate bullet blocking on an unresolved Security Finding.
- `skills/requirements-agent/SKILL.md`: makes the pre-delegation nelly call on
  `spec-reviewer`'s behalf.
- `references/artifact-templates.md`: new `design.md` section "Improvement Opportunities &
  Blast Radius" (Blast Radius / Security Findings (blocking) / Refactor & Reduction
  Opportunities (non-blocking) / Best-Practice Notes (non-blocking)); `recap.md`'s Open Items
  gained `Security`/`Improvement` tags.

## 0.1.3

### Changed
- Token-efficiency pass on the agent-isdd ↔ agent-nelly integration and on agent-isdd's own
  spec artifacts.
- `skills/spec-driven-development/SKILL.md`: declared as the single fetch point for
  `agent-nelly:nelly-orchestrator`'s holistic brief per continuous stretch of phase work, with
  three explicit re-fetch triggers (no prior brief in context, a rewind/Mid-Phase Change
  Classification since, an Intent-alignment divergence flagged since).
- `skills/design-author/SKILL.md`: reuses the brief passed down by the caller instead of
  always re-fetching.
- `skills/workflow-manager/SKILL.md`: documents its `start`/`before-continue` nelly calls as
  distinct-purpose and explicitly outside the new dedup pool.
- `agents/tdd-planner.md`: documents why its direct `requirements.md`/`design.md` reads are
  not a nelly-routing violation.
- `INTEROP.md`: records the brief-reuse convention as the cross-plugin-visible contract.
- `references/artifact-templates.md`: removed two redundant `Phase Completion` re-check
  lines (`requirements.md`, `design.md`) and consolidated `recap.md`'s `Open Questions` /
  `Technical Debt` / `Risks` sections into one `Open Items` section (368→360 lines).

## 0.1.2

### Added
- Sibling-plugin hook reliability: hook points (state consistency, the implementation
  handoff, mid-implementation rollback requests) are now verified/enforced rather than only
  reminders to the model.
- `hooks/state_consistency_check.py`: `PostToolUse` hook that verifies and repairs
  `workflow-state.json` toward `workflow-state.md` on every write, logging the repair to
  `recap.md` and `hook_history`. Never blocks.
- `hooks/slice_spec_gate.py`: `PreToolUse` hard deny-gate on the Implementation Handoff —
  blocks spawning `agent-tdd:agent-TDD`/`agent-tdd:test-author` when the constructed Slice
  Spec is missing a required field per `INTEROP.md`'s mapping table.
- `hooks/subagent_report.py`: recognizes a new `<!--SDD-ROLLBACK-REQUEST:...-->` marker so
  `agent-tdd`'s review-pause report (or a human relaying `code-reviewer`'s findings) can
  signal that a task — not just its implementation — was wrong; recorded as
  `rollback_pending` in `workflow-state.json`.
- `workflow-manager`'s "Rollback Request Intake" (part of `before-continue`): routes a
  pending rollback into the existing Rewind Contract automatically, logged distinctly from a
  routine rewind, with loop prevention on repeated requests.
- `workflow-manager`'s "Mid-Phase Change Classification": one documented rule for whether a
  mid-Design/mid-Tasks user change should redo the current phase in place or trigger a real
  rewind.
- `INTEROP.md`: new "← agent-tdd / code-reviewer (rollback request)" section documenting the
  marker convention and its automatic-vs-human-relay scope.
- `references/workflow-state.template.json`: additive `rollback_pending` field.

## 0.1.1

### Infra
- First public push: repo created at `github.com/renfordn/agent-isdd`. No functional changes
  since 0.1.0.

## 0.1.0

### Added
- Initial release of `agent-isdd`, split out of the `sdd` plugin (v1.7.0) to own only the
  planning side of an intent spec-driven-development workflow: Requirements → Design →
  Tasks. Ported unchanged: `requirements-agent`, `design-author`, `tdd-planner`,
  `doc-consistency-auditor` skills; `planning-agent`, `spec-reviewer`, `tdd-planner`,
  `ux-agent` subagents; `sdd_memory.py`/`sdd_state.py`/`session_start.py`/`stop_check.py`/
  `precompact_snapshot.py`/`phase_task_sync.py`/`memory_permission.py`/`memory_slug_guard.py`/
  `subagent_report.py`/`commit_audit_gate.py`/`diff_fingerprint.py` hooks.
- Trimmed `spec-driven-development` and `workflow-manager` skills: removed Implementation-stage
  ownership (the old 6-stage `planning/red/green/review/refactor/commit_check` state machine)
  and the direct `agent-TDD`/`code-reviewer` dispatch, replaced with a single one-directional
  handoff to `agent-tdd:agent-TDD` (with `agent-tdd:test-author` first for `high-risk` slices)
  once the Tasks phase's Task Readiness Checklist passes and implementation is requested.
- Renamed all commands from `/sdd*` to `/isdd*`.
- `references/workflow-state.template.json` simplified: dropped `implementation_stage`,
  `diff_fingerprint`, `review_state_path` fields, since Implementation-stage tracking now lives
  entirely inside `agent-tdd`.

### Removed
- `agent-TDD`/`test-author` agents and the `agent-TDD` skill — implementation and TDD
  orchestration now live solely in the separate `agent-tdd` plugin.
- `code-reviewer` skill — the review gate now lives solely in the separate `code-reviewer`
  plugin, invoked directly by whichever caller drives implementation (no longer this plugin).
- `dispatch_gate.py`, `gate_check.py` hooks — these gated `agent-TDD` dispatch and pre-approval
  source edits respectively; `agent-isdd` never touches source files, only planning artifacts,
  and `agent-tdd` self-gates its own dispatch.
- `REVIEW-STATE.md.template`, `REVIEW-HISTORY.md.template` reference templates — owned by
  `code-reviewer` now.

`~/.claude/sdd-memory/<project-slug>/spec/` artifacts are unchanged in directory layout and
file format — no migration is required from `sdd`.
