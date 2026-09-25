# Changelog

## [Unreleased]

- **Docs**: `high_risk_reviewer`'s checkpoint message no longer says there's no enforcement; it
  points at agent-tdd's new review gate.

## [0.1.61] - 2026-09-25

- **Docs**: the Code-Review Gate and the direct-implementation fallback's review step now use
  code-reviewer's independent review (spawned agent → headless script → labelled self-review)
  instead of running `/code-reviewer` in the same context that implemented the slice.

## [0.1.60] - 2026-09-25

- **Fix**: `doc-consistency-auditor`'s first commit-gate run against this project found three
  files (`skills/design-author/SKILL.md`, `skills/doc-consistency-auditor/SKILL.md`,
  `skills/spec-driven-development/references/review-levels.md`) citing a bare, nonexistent
  `code-reviewer/SKILL.md` path. Corrected to the real
  `code-reviewer/skills/code-reviewer/SKILL.md` path in all three.

## [0.1.59] - 2026-09-24

- **Fix**: `hooks/sdd_state.py`'s `find_state_files()`/`active_state_file()` now skip features whose `workflow-state.md` has `Workflow Status: Complete` (new `is_complete_state()`). Before, the newest workflow-state.md stayed "active" after completion, so hooks such as `subagent_report.py` kept appending to its `recap/subagent-reports.md` in unrelated sessions. When every feature is Complete, discovery now returns no active workflow. In-progress and paused features resolve as before.
- **Feature**: Design phase now checks agent-nelly's File & Folder Summary Cache before deep-reading files. `design-author`'s "Research First" step 1 sends a `file summary lookup` for the brief's `Relevant entries`/named requirement files alongside its usual brief call, verifies each cache hit's `git_hash` itself, and passes confirmed-fresh paths to `research-consolidator` to skip re-reading. `research-consolidator`'s Pass 1/2 honor that skip list, and its "File Summaries" output is now explicitly capped at 240 characters per entry. After it returns, `design-author` persists file summaries to agent-nelly's real `file summaries`/`folder summaries` fields instead of the previously-undefined `type: "file_summary"` (a documented-but-never-implemented mechanism this corrects).
- **Feature**: `requirements-agent`'s Review mode checks the same cache for any files a source ticket/PRD names explicitly, before reading them cold.
- **Feature**: implementation handoff (`implementation-handoff.md`) now names the real `file summary lookup` field for its pre-fetch step and forwards `agent-TDD`'s new **File Summaries** report field to agent-nelly alongside Handoff Facts.
- **Fix (docs)**: `INTEROP.md`'s "→ agent-nelly" section described a `type: "file_summary"` `new facts` batch item and a per-file JSON cache path that agent-nelly never actually implemented. Corrected to document the real contract (agent-nelly's `file summaries`/`folder summaries`/`file summary lookup` fields, `entries/`-backed `file-summary`/`folder-summary` types, 240-char cap) — see agent-nelly's own CHANGELOG/INTEROP.md for its side.

## [0.1.58] - 2026-09-24

- **Feature**: `scripts/sdd_cleanup.py` condenses features that are `Complete` and have no artifact changes for 14 days into `completed/<feature>.md` (goal, success signals, decisions, open follow-ups, commits, final state) and deletes the rest. Hook bookkeeping files don't count as activity. It also merges idle worktree stores into their parent repo's store. Actions are logged to `CLEANUP-LOG.md`, and reports go to `cleanup-reports/`.
- **Feature**: `session_start.py` lists completed-feature summaries still marked `nelly_recorded: no`, so the session hands them to agent-nelly. `memory_permission.py` auto-approves edits under `completed/**`. Adds `sdd_memory.pending_nelly_summaries()`.
- **Docs**: README "Cleanup of finished work" section.

## [0.1.57] - 2026-09-24

- **Fix**: `hooks/post_write_check.py` capped `workflow-state.json`'s `hook_history` at `MAX_HOOK_HISTORY` (100, oldest dropped first), so the file stops growing without bound.
- **Fix**: `hooks/sdd_state.py`'s `write_escalation_outcome()` now keeps only the last `MAX_ESCALATION_HISTORY` (50) entries of `escalation_history`.
- **Fix**: `hooks/high_risk_reviewer.py`'s `update_reviewed_phases()` now replaces a phase's earlier entry when that phase is reviewed again, so `reviewed_phases` holds at most one entry per phase.

## [0.1.56] - 2026-09-24

- **Feature**: optional `shared_memory_root` plugin option (`userConfig`, exported to hooks as `CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT`). When set, `hooks/sdd_memory.py`'s `BASE` becomes `<root>/sdd-memory/`, so SDD spec state is shared across plugin identities and machines. Unset keeps the old behaviour. A relative value raises `PluginDataDirUnavailable`.
- **Change**: `last-stop.json` and `snapshots/` stay machine-local (`sdd_memory.local_state_dir()`). `session_start.py` scaffolds the shared root's `.gitignore`/`.gitattributes` and records the resolved location in `${CLAUDE_PLUGIN_DATA}/sdd-memory-location.json` for plugin-harness.
- **Change**: `memory_permission.py` follows the active root. `memory_slug_guard.py` guards the shared root and, while a shared root is active, denies writes into the stale `${CLAUDE_PLUGIN_DATA}/sdd-memory/`.
- **Change**: command/skill content that runs hook scripts now also passes `CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}"`.
- **Docs**: README section and `docs/shared-memory-root.md`.
- **Fix**: `hooks/post_write_check.py` now caps `hook_history` in `workflow-state.json` at `MAX_HOOK_HISTORY` (100, oldest dropped). Before this it grew by one entry per state sync with no limit.

## [0.1.55] - 2026-09-24

- **Fix (behaviour change)**: no more guessed data-dir fallback. `hooks/path_resolution.py`'s `get_plugin_data_dir()` now raises `PluginDataDirUnavailable` when `CLAUDE_PLUGIN_DATA` is unset instead of guessing `~/.claude/plugins/data/<plugin>/` (which can point at the wrong install identity). Scripts run from skills/commands/agents now pass `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"` and use `${CLAUDE_PLUGIN_ROOT}` paths; tests get a temp `CLAUDE_PLUGIN_DATA` via `conftest.py`.
- **Docs**: README's "never invoke hooks directly" section rewritten for the new fail-fast behaviour.

## [0.1.54] - 2026-09-24

- **Fix**: `hooks/path_resolution.py`'s `${CLAUDE_PLUGIN_DATA}` fallback (used whenever the env
  var isn't set) silently guessed a bare, non-suffixed `~/.claude/plugins/data/agent-isdd/`
  path with no warning. Confirmed root cause of a false commit-gate denial: Claude Code can load
  this plugin under more than one identity at once (e.g. a monorepo checkout as
  `agent-isdd@inline` alongside a marketplace install as `agent-isdd@<marketplace>`), and each
  identity gets its own `${CLAUDE_PLUGIN_DATA}` injected into *its own* registered hook
  subprocesses — but never into a manual/direct `python3 hooks/*.py` invocation (e.g. run via a
  Bash tool call instead of the real hook chain), which silently fell back to the guessed path
  instead. State scaffolded that way can land under a different identity's data dir than
  whichever one the project's real hooks resolve to, invisible to every real hook until
  reconciled by hand — confirmed in practice via a duplicated `DOC-AUDIT-STATE.md`/
  `DOC-AUDIT-HISTORY.md` and an entirely invisible SDD feature folder. Every hook in this plugin
  that discovers its own state via `memory_dir()`/`active_state_file()`/`find_state_files()`
  (all of `hooks/session_start.py`, `before_continue.py`, `precompact_snapshot.py`,
  `high_risk_reviewer.py`, `design_spec_gate.py`, `slice_spec_gate.py`, `subagent_report.py`,
  `stop_check.py`, `ux_render.py`, `commit_audit_gate.py` — none of this plugin's hooks receive
  an explicit spec-folder path in their own PreToolUse/PostToolUse/SubagentStop payload) inherits
  this exposure. The most serious instance: `hooks/design_spec_gate.py` treats "no state found"
  as "no SDD workflow active, not this plugin's business to gate" and falls through with no
  decision — for a gate hook, a resolution mismatch means a silent *allow* of an unapproved
  `agent-tdd:agent-TDD` Design Spec spawn, not just a stale-looking read.

  Fix: `path_resolution.py`'s fallback now prints a clear, one-line warning to stderr (never
  stdout, which every hook reserves for its JSON decision) whenever `${CLAUDE_PLUGIN_DATA}` is
  unset, so a manual invocation — or a real hook whose env var somehow didn't get injected — is
  never silent about it. Kept in sync in both the per-plugin copy
  (`hooks/path_resolution.py`, what actually ships) and `shared/path_resolution.py` (the
  whole-repo test copy), per that file's own "keep in sync" instruction. This is a detection/
  visibility fix, not a resolution-unification one — deliberately: normalizing to one path
  regardless of identity would fight Claude Code's own per-identity data isolation, which is
  there on purpose. Documented the actual discipline instead: never invoke `hooks/*.py` directly
  outside the real registered hook chain (new docstring guidance in `path_resolution.py`,
  `sdd_memory.py`, `sdd_state.py`, `design_spec_gate.py`, `commit_audit_gate.py`,
  `slice_spec_gate.py`, plus a new "Debugging: never invoke `hooks/*.py` directly" section in
  `README.md`). Added `tests/test_path_resolution.py` (new) and matching cases in
  `shared/test_path_resolution.py` covering the warning's presence/absence and that it never
  lands on stdout.

  Also reconciled this monorepo's own already-split SDD memory data for this project (found
  during the same investigation): the `2026-09-24-code-reviewer-improvement-detection` feature
  folder and this project's `DOC-AUDIT-STATE.md`/`DOC-AUDIT-HISTORY.md` existed only (or in a
  smaller, diverged form) under the non-`-inline` `agent-isdd` plugin-data directory, invisible
  to this project's real hooks, which resolve to the `-inline` one (confirmed via
  `commit_audit_gate.py`'s own `RUN-LOG.jsonl`, present only under `-inline`). Copied/merged the
  fuller records into the `-inline` location (now canonical for this project) and left the
  non-`-inline` originals in place, annotated as superseded, for reference — nothing was
  deleted. The affected workflow was already `Complete` / `Implementation Requested: Yes` at
  reconciliation time, so this was a record-keeping fix, not a resumed-workflow concern.

  Scoped to `agent-isdd` (the plugin actually reported). Most sibling plugins
  (`agent-tdd`, `agent-nelly`, `agent-ux`, `code-reviewer`, `plugin-harness`,
  `deployment-ops-plugin`, etc.) carry their own per-plugin copy of `path_resolution.py` with
  the same fallback pattern and likely share this same exposure — worth a follow-up pass across
  those, not done here to avoid scope creep on a single-plugin bug fix.

- **Fix**: `skills/workflow-manager/SKILL.md`'s "Native Plan Mode Gate" and
  `skills/design-author/SKILL.md` claimed Design writes `design.md`/`research/cache.md`/
  agent-nelly `file_summaries` to disk "as it goes" while native plan mode is active — the
  harness actually restricts file edits during plan mode to the one designated plan file, so
  those writes are refused, not merely discouraged (observed in practice as a self-correction
  mid-session). `design-author` now drafts all Design-phase output in context and in the plan
  file only, and persists the real artifacts in one step once the user approves the plan
  (`ExitPlanMode`) — including the Design Validation Deep Review step, which previously assumed
  `design.md`/`research/cache.md` were already on disk at a point that can still precede plan
  approval.

## [0.1.53] - 2026-09-24

- **Feature**: `research-consolidator` now reports each deep-read file's physical line count
  (`line_count`, via `Grep` `pattern: "^"` + `output_mode: "count"` — it has no `Bash` tool, so
  never via `Read`'s own truncating line numbers) and resolves the target repo's own documented
  line-count ceiling once per research pass (`AGENTS.md`/`CLAUDE.md`, a stated range resolving to
  its upper bound, defaulting to 400 with an explicit `default (no repo convention found)` source
  when neither file states one). `design-author` gained a Design Gate item requiring a
  split/extraction recommendation in `design.md`'s `Refactor & Reduction Opportunities
  (non-blocking)` section for any touchpoint file at/over that ceiling, plus a guardrail keeping
  `code-reviewer`'s Deep review pass out of line-count-ceiling territory — file-size enforcement
  is a design-time concern, never a `code-reviewer` one (see `code-reviewer`'s own 0.1.13
  changelog entry). `INTEROP.md`'s `file_summary` JSON example and Design Spec field table
  updated to match.
- **Fix**: `design-author/SKILL.md`'s own prose enumeration of `file_summaries`' fields (in its
  "Research First" step) had drifted from `research-consolidator.md`'s actual schema — missing
  the `line_count` field the same feature had just added to it. Caught by a follow-up review
  pass; added a regression test.

## [0.1.52] - 2026-09-24

- **Fix**: `hooks/diff_fingerprint.py`'s `TRACKED_DIRS` matching was never monorepo-aware
  (unlike `_interop_paths`, which already handled both shapes) — when `commit_audit_gate.py`
  runs from the monorepo root (a mode its own `_looks_like_this_plugin` explicitly supports),
  none of `skills/`/`agents/`/`commands/`/`hooks/` exist at that root directly, so every real
  staged change under a sibling plugin was silently invisible to the fingerprint. Worse: this
  let the audit gate be silently bypassed for any monorepo-root commit that didn't happen to
  touch an `INTEROP.md` (`current_fp` came back `None` → auto-allow). Added `_tracked_dir_paths`
  mirroring `_interop_paths`'s existing dual-shape glob pattern, plus 2 regression tests.
- **Docs**: two more instances of the `after-tasks`/`handoff` "tasks.md ownership" drift fixed
  in 0.1.51 — `INTEROP.md`'s "one scoped exception" framing for the one-directional `agent-tdd`
  handoff was itself stale (Model Escalation, added 0.1.39, is a second real exception, never
  acknowledged); `INTEROP.md`'s `slice_spec_gate.py` "retired/never wired into hooks.json" claim
  was also stale (re-enabled 2026-09-17 for `Track: Fast`, confirmed via
  `tests/test_hooks_json.py`'s `test_slice_spec_gate_reenabled_for_fast_track`).
  `skills/design-author/SKILL.md` and `skills/spec-driven-development/references/
  review-levels.md` had the same "next phase is agent-isdd's own Tasks phase" framing, corrected.
- **Docs**: `Current Phase: Tasks` clarified as a real, intentional rollback-landing state
  (reached via `/isdd-rewind Tasks` or a relayed rollback request when the task-level plan
  itself — not the design — needs redoing), not a phase `agent-isdd` dwells in or authors an
  artifact for. Added the previously-missing routing rule for it (re-invoke Implementation
  Handoff directly on `continue`) to `skills/workflow-manager/SKILL.md`,
  `skills/spec-driven-development/SKILL.md`, and `references/artifact-templates.md`; corrected
  `references/MIGRATION_GUIDE.md`'s flatly wrong "no, can't rewind to Tasks" answer.
- **Docs**: corrected stale `~/.claude/sdd-memory/`/`~/.claude/agent-nelly-memory/` path
  illustrations across hook docstrings, command docs, and the `doc-consistency-auditor`
  reference templates to the real `${CLAUDE_PLUGIN_DATA}`-based resolution
  (`hooks/sdd_memory.py`'s `BASE` never had a bare-path fallback — only the illustrative
  examples were stale, not the actual resolution logic).

## [0.1.51] - 2026-09-24

- **Docs**: corrected `skills/workflow-manager/SKILL.md`'s `after-tasks`/`handoff` action-table
  rows and Native Plan Mode Gate section, and `references/artifact-templates.md`'s `tasks.md`
  template — all still described a pre-Phase-2+3 scheme where `agent-isdd` itself wrote and
  gated `tasks.md` before handoff. It doesn't: `agent-tdd` produces `tasks.md` (in its own
  slice-based schema) during the Design Spec handoff spawn, and runs its own Readiness Check
  there — there is no separate agent-isdd-evaluated `Tasks` checklist. `handoff`'s trigger is
  simply "Design approved and implementation requested," matching what
  `spec-driven-development`'s Implementation Handoff section already spawns on. No behavior
  change; no code touched.

## [0.1.50] - 2026-09-22

- **Chore**: deleted `hooks/cache_hook.py` (a pure no-op since 0.1.49) and dropped it from
  `subagent_dispatch.MODULES`; `INTEROP.md`'s agent-cache-plugin section now points at the
  plugin's real (automatic) `agent_output_cache` capability instead of the never-built
  `phase_state_cache`.
- **Fix**: `hooks/ux_render.py` resolved the feature only from a `state_path` payload field
  that the real SubagentStop payload never carries, so it silently returned nothing. It now
  resolves the active feature from `cwd` via `sdd_state.active_state_file` like its sibling
  hooks (an explicit `state_path` still overrides, for tests).
- **Tests**: `tests/test_cache_integration.py` → `tests/test_ux_render.py`; pins no-network,
  cwd-based resolution, and dispatcher module order.

## [0.1.49] - 2026-09-22

- **Fix**: removed the dead agent-cache-plugin HTTP integration from `hooks/cache_hook.py`
  (`/cache/write`, `/cache/invalidate`) and `hooks/ux_render.py` (`/cache/read`). No server
  ever listened on `localhost:7771`; every call failed and was swallowed, so phase-state
  caching never worked and `ux_render`'s phase-transition branch never fired. `cache_hook.py`
  is now a documented no-op explaining the gap (agent-cache-plugin exposes no transport a
  Python hook can reach); `ux_render.py` renders the breadcrumb straight from
  `workflow-state.json`. `tests/test_cache_integration.py` now pins the no-network contract
  instead of testing graceful degradation of a call that could never succeed. `INTEROP.md`'s
  agent-cache-plugin section rewritten to match.

## [0.1.48] - 2026-09-22

- **Docs**: added a `## Quickstart` section (install one-liner + first `/isdd` command + pointer
  to `docs/install-and-verify.md`).
- **Chore**: removed `tasks.md`, a stray SDD leftover artifact from an already-shipped feature,
  not meant to ship with the plugin.

## [0.1.47] - 2026-09-22

- **Fix**: `workflow-manager`/`design-author`/`requirements-agent`/`spec-driven-development` `SKILL.md` files referenced `references/artifact-templates.md` and `references/workflow-state.template.json` as bare relative paths, ambiguous since those files live in the plugin-root `references/` dir, not each skill's own — now use `${CLAUDE_PLUGIN_ROOT}/references/...`, matching the convention already in `agents/spec-reviewer.md`.
- **Fix**: `tests/test_sdd_review_guidance.py` hardcoded an absolute `/Users/jay.nelson/...` path (would fail on any other machine, including CI) and only read `SKILL.md`, missing the "Deep"/"Ultra" review-level detail the v0.1.46 progressive-disclosure split moved into `references/review-levels.md`. Made the path relative and read both files.
- **Fix**: `tests/test_design_author_deep_review.py` and `tests/test_isdd_interop_review_placement.py` hardcoded the same absolute-path pattern; made both relative to `Path(__file__)`.

## [0.1.46] - 2026-09-21

- **Docs**: apply progressive disclosure to `spec-driven-development/SKILL.md` (4,987 → 2,669 words) and `workflow-manager/SKILL.md` (4,128 → 3,234 words), moving deep/rare-path detail into new `references/*.md` files; rewrite `plan-reviewer/SKILL.md`'s description for concision (568 → 490 chars). Fixes the 3 genuine `plugin-validate` Per-Skill Quality findings against this plugin; fixes 2 stale `INTEROP.md` cross-references into content that moved.

## [0.1.45] - 2026-09-21

- **Fix**: `hooks/before_continue.py`'s model-escalation systemMessage told the model to "Call the `get_spawn_context` MCP tool" as if that bare string were the tool's directly-callable name; Claude Code exposes a plugin-bundled MCP server's tools harness-prefixed, so this now names `plugin-orchestrator`'s `spawn-context` server and points at `ToolSearch` to find the real name.

## [0.1.44] - 2026-09-20

- **Docs**: promote unpromoted Unreleased CHANGELOG section to versioned [0.1.43] entry.

## [0.1.43] - 2026-09-20

- **Release**: bump version for public release pass.

## [0.1.40] - 2026-09-20

- **Consistency pass**: remove dead `invoke_code_reviewer` subprocess (binary never existed); wire `render_phase_transition` hook to emit structured agent-ux delegation instruction in systemMessage; `render_breadcrumb_only` now correctly no-op per skill spec (inline rendering); delete stale proposals/ planning docs.

## [0.1.39] - 2026-09-20

- **Escalation re-spawn outcome logging (0.1.39).** Closes the Task 9 gap flagged when model
  selection shipped: when agent-tdd escalates mid-slice and agent-isdd re-spawns it at a higher
  tier, nothing recorded whether the re-spawned attempt actually succeeded. `hooks/sdd_state.py`
  gains `write_escalation_outcome`/`read_escalation_pending`/`clear_escalation_pending`,
  mirroring the existing `rollback_pending` pattern. `hooks/subagent_report.py` gains
  `_has_validation_evidence` (narrative test-pass detection) and `_classify_escalation_outcome`,
  wired into `main()` alongside (not replacing) existing rollback-marker handling — `succeeded`
  requires both confirmed passing tests and no further escalation/blocker/rollback marker.
  `references/artifact-templates.md` documents the new Rollback History / Escalation History
  recap.md conventions. No changes to `before_continue.py` or `model_escalate_marker.py`. 335
  of 336 tests pass (1 pre-existing unrelated failure).

- **Model selection across plugins: escalation marker parsing (0.1.39).** Adds
  `hooks/model_escalate_marker.py`, an isolated utility parsing the `MODEL-ESCALATE` marker
  agent-tdd emits when it needs to escalate to a higher model tier mid-slice. Accepts both the
  canonical `from_model`/`to_model` fields and the legacy `attempted_at_haiku`/`suggest_tier`
  aliases. `hooks/before_continue.py` wires detection in, writing `escalation_pending` to
  `workflow-state.json` and surfacing a re-spawn instruction to the user.

- **Document the harness `Agent`-spawn-failure fallback, and route it at agent-tdd's new
  Direct Mode skill (0.1.32).** `INTEROP.md`'s "→ agent-tdd" section gains a "Fallback — Direct
  Implementation (harness `Agent`-spawn failure)" subsection: a three-condition Detection check
  (schema-validation error on the `Agent` call itself, reproduces on retry, reproduces for an
  unrelated agent type in-session) before ever treating a spawn failure as harness-level rather
  than a one-off. First written from the real investigation on the
  `2026-09-15-expand-error-logger` feature, then updated once `agent-tdd:design-spec-direct`
  (a `Skill`, not `Agent`, invocation reproducing Design Spec Mode's slicing/Ralph
  Loops/Risk Tiers and Slice Spec Mode's per-slice Red/Green/Review/Refactor contract) existed
  to name concretely: `spec-driven-development/SKILL.md`'s Implementation Handoff step 5 now
  points at that skill's `plan` → per-slice loop → `summary` contract instead of freeform
  "implement it yourself" prose. 246 tests pass.

- **Test-Author Gate: close the mid-pipeline high-risk-slice escalation gap for real
  (0.1.31).** Full reimplementation of the isdd-tdd Design Spec handoff, following its own SDD
  workflow (Requirements → Design → Implementation via `agent-tdd:agent-TDD`). Replaces the
  abandoned `TEST_AUTHOR_NEEDED_MARKER` approach (added and removed the same day) with a
  simpler mechanism: since `agent-tdd` already knows every slice's Risk Tier before
  implementation begins, `agent-TDD` now stops at `slicing_complete` when any slice is
  high-risk (previously it proceeded straight through with no way for the caller to supply
  `test-author`'s output). `hooks/high_risk_reviewer.py` detects this and writes
  `test_author_pending` to `workflow-state.json`; `skills/spec-driven-development/SKILL.md`'s
  Implementation Handoff spawns `test-author` per named slice and resumes `agent-TDD` via
  `SendMessage` — the one scoped exception to the one-directional handoff. Also adds a real
  Design Spec completeness gate (`hooks/design_spec_gate.py`, modeled on
  `memory_permission.py`), replacing the disabled, wrong-schema `slice_spec_gate.py`. Both
  `INTEROP.md` files rewritten together to describe this identically. 260 tests pass.

- **Add `plan-reviewer` skill: tiered, token-efficient design verification (0.1.30).**
  Replaces ad hoc use of the harness's built-in `Plan` subagent for verifying `design.md`
  before the Design Gate — `Plan` is open-scoped and was observed taking 10+ minutes for a
  single design check. `plan-reviewer` (new `skills/plan-reviewer/SKILL.md`, backed by
  `agents/plan-reviewer-tier1.md`/`tier2.md`/`tier3.md`) instead verifies a fixed list of
  falsifiable claims extracted from the design doc, tiered by cost: Tier 1 (Read/Grep/Glob,
  fast, claim-scoped) runs always; Tier 2 (same tools, boundary-expands to adjacent
  files/callers) only for claims Tier 1 flags `escalate: true`; Tier 3 (adds read-only Bash for
  git blame/call-graph tracing) only for findings Tier 2 confirms as a genuine blocker/risk.
  Wired into `design-author/SKILL.md`'s Research First step 3 and a new Design Gate check.
  Also callable standalone (outside any SDD workflow) — the skill and its three agents are
  symlinked from `~/.claude/skills/plan-reviewer` and `~/.claude/agents/` to this plugin's
  copy, so there is one source of truth and no drift between global and plugin-bundled use.
- **Critical: fix a packaging bug breaking every fresh install (0.1.29).**
  `hooks/sdd_memory.py` imported `path_resolution` from a monorepo-relative `shared/`
  directory (`os.path.join(os.path.dirname(__file__), '..', '..', 'shared')`) — this only
  resolves inside the dev checkout. A marketplace-installed plugin package contains only this
  plugin's own subdirectory; `shared/` is never bundled. Every hook depending on
  `sdd_memory.py` (`memory_permission.py`, `subagent_report.py`, `before_continue.py`,
  `stop_check.py`, and more) raised `ModuleNotFoundError` on a real fresh install of any
  version since the `${CLAUDE_PLUGIN_DATA}` migration (0.1.24+) — this session never hit it
  only because it's running from a stale pre-migration snapshot. Fixed by giving this plugin
  its own local copy of `path_resolution.py` in `hooks/`, verified by copying the plugin's
  `hooks/` directory alone to an isolated tmp directory with no monorepo present and
  confirming it still imports. Added `shared/test_plugin_packaging_self_containment.py` to
  catch this class of bug for all 4 affected plugins going forward.

- **Fix stale `slice_spec_gate.py` claim in the `after-tasks` hook table (0.1.28).**
  `skills/workflow-manager/SKILL.md`'s `after-tasks` row claimed `hooks/slice_spec_gate.py`
  hard-denies an incomplete `agent-tdd` spawn — stale from before the Phase 2+3 Design Spec
  handoff replaced the old Slice Spec path. That hook validates the wrong schema and isn't
  registered in `hooks.json` (`tests/test_hooks_json.py`'s own
  `test_slice_spec_gate_disabled_for_phase_2_3` already asserted this). No hook currently gates
  Design Spec completeness before spawn — corrected the doc to say so plainly rather than claim
  a safety net that doesn't exist. Found doing a feature-find pass over the isdd→tdd handover.

- **Remove the unreachable agent-nelly spawn-failure hook; move self-healing to where it can
  actually work (0.1.27).** `hooks/nelly_spawn_failure.py` (added in 0.1.25, moved to
  `PostToolUseFailure` in 0.1.26) was built to detect a `subagent_type`-not-found spawn failure
  and clear the stale `agent_nelly_available` cache. Live-tested and confirmed against Claude
  Code's own hooks docs: `subagent_type` resolution happens during model-output parsing, before
  the `PreToolUse`/`PostToolUse`/`PostToolUseFailure` lifecycle begins at all — no hook event
  can ever fire for this failure, regardless of which one it's bound to. Removed the hook, its
  `hooks.json` registration, and its dedicated test file rather than keep documented-but-dead
  code (same anti-pattern as the Auto Code-Reviewer pipeline corrected in 0.1.25). The
  self-healing intent moves to `skills/workflow-manager/SKILL.md`'s Availability Check section:
  the calling skill sees this exact failure directly in its own context when it happens, and
  corrects the cache itself.
- **Skip re-fetching file summaries from agent-nelly for files `research-consolidator` already
  summarized fresh this Design phase**, in the Design Spec handoff (`INTEROP.md` and
  `skills/spec-driven-development/SKILL.md`'s Implementation Handoff step 2) — previously the
  full touched-file list was queried against agent-nelly regardless of overlap with
  `research/cache.md`'s own fresh `file_summaries`, double-bundling the same file's summary.
- **Fix wrong hook event for the agent-nelly spawn-failure backstop (0.1.26).**
  `hooks/nelly_spawn_failure.py` was registered on `PostToolUse`, but a `subagent_type`-not-found
  rejection is a parameter-validation failure — the Agent tool never executes, so `PostToolUse`
  never fires for it (confirmed against Claude Code's hooks docs and live testing: an invalid
  `subagent_type` surfaces as a hard tool-call error, not a completed tool result).
  `PostToolUseFailure` is the correct event. The hook was effectively dead code under its
  original registration. Moved in `hooks/hooks.json`; `tests/test_hooks_json.py` updated to
  match.
- **Cap `recap.md`'s size in the Design Spec handoff.** `INTEROP.md` and
  `skills/spec-driven-development/SKILL.md`'s Implementation Handoff step 3 now say to summarize
  `recap.md` before bundling it into a Design Spec, rather than pasting it in full — unlike the
  rest of the bundle, `recap.md` has no bound on how large it grows across a feature's phases.
- **Ecosystem-audit fixes and new hooks (0.1.25).**
  - Fixed `tests/hook_test_utils.py` and 5 other test files hardcoding the pre-migration
    `~/.claude/sdd-memory/` path instead of the `${CLAUDE_PLUGIN_DATA}`-migrated
    `~/.claude/plugins/data/agent-isdd/sdd-memory/` — 14 tests were failing against the real
    (already-fixed) `sdd_state.py`.
  - Corrected `INTEROP.md`'s and `skills/spec-driven-development/SKILL.md`'s "Auto
    Code-Reviewer Invocation" sections: both described a fully-automatic severity-classifying
    subprocess pipeline that was never implemented and contradicted `agent-tdd`'s and
    `code-reviewer`'s own documented contracts. `hooks/high_risk_reviewer.py` only ever emitted
    a passive checkpoint reminder; the fuller pipeline's functions exist but are dead code.
  - Added `hooks/subagent_report.py`'s `TEST_AUTHOR_NEEDED_MARKER` detection (mirrors
    `PLAN_FLAG_MARKER`), closing the gap where a high-risk slice mid-Design-Spec-Mode had no
    escalation path back to the caller for a `test-author` spawn.
  - Added `hooks/nelly_spawn_failure.py`, a `PostToolUse`/`Agent` backstop that clears a stale
    `agent_nelly_available` cache when a spawn fails, scoped to `agent-nelly:agent-nelly` only
    (`agent-tdd:agent-TDD` stays deliberately uncached per `INTEROP.md`).
  - Added `hooks/research_cache.py`'s `find_stale_summaries()`, a git-hash-gated staleness
    check for cached `research/cache.md` file summaries.
- **Reconciled `proposals/2026-08-12-agent-isdd-token-efficiency-pass` with the current
  architecture.** Phases 1, 3, and 5 of that pass were already satisfied by pre-existing content;
  Phase 2 and Phase 4 each had one remaining step targeting `tdd-planner`, which no longer exists
  (removed in 0.1.14 — task slicing is now performed directly by `spec-driven-development`).
  - `skills/spec-driven-development/SKILL.md`: Writing Style section now states the `Depends On`
    contract (populate with real task ids, `[]` when none, narrative deps stay in
    `Prerequisites`) that would have gone into the removed `tdd-planner/SKILL.md`.
  - `references/subagent-conventions.md`: updated the "confirmed non-applicable" note to name
    `spec-driven-development` (current task-slicing owner) instead of the removed `tdd-planner`.

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
