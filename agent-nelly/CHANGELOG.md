<!-- TDD-SKIP -->
## [Unreleased]

- `hooks/nelly_auto_extract.py` / `hooks/nelly_commit_extract.py` — auto-confirmation of recurring
  inferred entries. Every entry these hooks write now carries `metadata.seen_count` (starting at
  1); a later dedup hit on the same slug increments it in place instead of a silent no-op, and once
  a still-`confidence: inferred` entry's `seen_count` reaches 3, it's flipped to
  `confidence: explicit` automatically — no `/nelly-memory review-inferred` needed for
  high-frequency patterns. Each promotion appends one `Action: promoted` block to
  `CONSOLIDATION-LOG.md`. `scripts/build_index.py`'s index records now carry `seen_count` too.
  Pure Python, no LLM; already-`explicit` entries are never re-promoted or demoted.
- `hooks/nelly_session_start.py` — the `SessionStart` hook's entry surfacing now reads
  `nelly-index.json` directly (via `scripts/build_index.py`'s pre-index) instead of just listing
  entry slugs: a compact, token-bounded brief reports total entry count plus `error-prevention`/
  `technique` type counts, then up to 5 most-relevant entries with truncated descriptions —
  explicit-confidence `error-prevention` entries always sorted first (highest signal), the rest by
  recency. Pure index reads only, no entry-file re-opens, no LLM call. Falls back to the old plain
  slug listing when the index hasn't been built yet.
- `hooks/nelly_commit_extract.py` — a new `PostToolUse` hook (matched on `Bash`) that parses
  `git commit` success output already present in tool stdout (`[branch hash]` header, `N file(s)
  changed` summary, create/delete mode lines) and writes one inferred `technique` entry per
  detected commit, deduped by commit hash and tagged from changed top-level dirs. Pure Python, no
  `git` subprocess calls, no LLM.
- `scripts/nelly_populate_from_git.py` — a new one-shot (safely re-runnable) pre-populator that
  mines existing `git log` history in one or more repos and writes an inferred `technique` entry
  per commit, so a brand-new memory store isn't empty on day one. Reuses
  `nelly_commit_extract.py`'s slug pattern (`git-pattern-<hash[:12]>`), tag derivation, and dedup
  check, so entries it seeds are indistinguishable from ones the live commit hook would have
  written, and re-running it after real commits accumulate skips anything already recorded.
  Accepts `--repo` (repeatable), `--limit` (default 200 commits/repo), and `--dry-run`; with no
  `--repo` given, auto-discovers git repos up to 2 directory levels deep under `$NELLY_REPO_BASE`
  (default `~/Codebase`). Rebuilds `nelly-index.json` via `build_index.build_all()` after writing.
  Pure Python stdlib plus one `git log` subprocess call per repo, no LLM.

## [0.2.3] - 2026-08-16

- `scripts/nelly_weekly_consolidate.py` — a standalone, no-LLM script for unattended weekly memory
  upkeep, registered as a scheduled task (Sunday 09:00) via the `scheduled-tasks` MCP. It scans
  every project's memory store plus the `global/` tier for consolidation candidates
  (near-duplicate slug/description pairs, `error-prevention` entries with `confidence: inferred`
  that sat unconfirmed past 90 days, and entries some other entry's `metadata.supersedes` names
  but that were never actually archived), writes a human-readable report to
  `~/.claude/agent-nelly-memory/consolidation-reports/YYYY-MM-DD.md`, and auto-archives (never
  deletes) the stale-inferred entries — logging each archive as an `Action: archived` block in the
  affected project's `CONSOLIDATION-LOG.md` and rebuilding `nelly-index.json` afterward via
  `build_index.build_all()`. Near-duplicate and superseded-anomaly candidates are report-only —
  merging still requires `nelly-orchestrator`'s judgment via `/nelly-memory consolidate`, which
  this script deliberately does not attempt to replicate. Supports `--dry-run` and `--stale-days`.
- `commands/nelly-memory.md` — added `list-inferred` (read-only listing of every
  `confidence: inferred` `error-prevention` entry) and `review-inferred` (interactive batch
  confirm/discard over that same list) subcommands, closing the loop on inferred lessons that
  previously accumulated silently with no visibility and no way to act on more than one at a
  time. `nelly-orchestrator.md` gained matching `list inferred lessons` and `discard error
  lesson: <name>` actions — the latter archives an unconfirmed inferred entry (archive-not-delete
  guarantee applies) without ever promoting it to `explicit`.
- Pre-index JSON (`nelly-index.json`) alongside each memory store (per-project and the `global/`
  tier), built and kept fresh by `scripts/build_index.py` and a new `PostToolUse` hook,
  `hooks/nelly_index_update.py`. Each record carries `slug`/`type`/`confidence`/`description`
  (first line)/`tags`/`file_path`/`mtime` — no full entry content. `nelly-orchestrator.md`'s
  topical `Relevant entries` matching now reads this index first instead of opening every
  `entries/*.md` file, ranks matches, and opens files only for the top 5 (plus any
  `error-prevention` candidate, to preserve the inferred-confidence exclusion gate, and any
  `file-relevance` candidate when `target files` was passed, since the index carries no
  `metadata.files`); everything else outside the top 5 gets a description-only summary sourced
  straight from the index. This closes the scope gap noted when the 0.2.1 index fields shipped
  without description text.

## [0.2.2] - 2026-08-15

- Proactive suggestion hooks: a new `PreToolUse` hook, `hooks/nelly_proactive_surface.py`, wired
  into `hooks/hooks.json` alongside the existing guardrail hooks. It deterministically matches a
  `Write`/`Edit`/`MultiEdit` target path against `MEMORY.md`'s new `paths:` index field and, on a
  match, emits a one-line `permissionDecisionReason` nudge — no `Agent`-tool call, no
  `nelly-orchestrator` invocation, silent no-op on no match, empty/missing memory store, or
  `NELLY_GATE=off`. An `error-prevention` entry only surfaces when its entry file's real
  `metadata.confidence` is `explicit`, read from the file itself rather than the index's mirrored
  (and potentially stale) `confidence:` field.
- `hooks/nelly_memory.py`'s `write_index_line()`/`parse_index_line_fields()` gained an optional
  `paths` field (semicolon-joined repo-relative paths), additive and backward-compatible with
  old-format index lines.
- Chore: removed duplicated prose across `agents/nelly-planning-agent.md`,
  `agents/nelly-research-agent.md` (now sharing a new `agents/nelly-brief-consumer-base.md`),
  `agents/nelly-orchestrator.md`'s repeated inferred-confidence/graceful-degradation restatements,
  `INTEROP.md`'s response-shape narration, and `commands/nelly-memory.md`'s duplicated
  archive-not-delete guarantee (now canonical in its Cross-cutting rules section).

## [0.2.1] - 2026-08-10

- Token-efficiency pass over `nelly-orchestrator.md`'s always-loaded system prompt and the
  surfacing path: removed three pure-documentation "Test-shape note" blocks (~23 lines with zero
  runtime relevance) into `references/future-validation-notes.md`, and added optional
  `type`/`confidence`/`files` fields to `MEMORY.md` index lines (`hooks/nelly_memory.py`'s new
  `write_index_line()`/`parse_index_line_fields()`) so `handoff surfacing` calls can skip opening
  an entry file that the index already rules ineligible by type, without ever weakening the
  inferred-confidence exclusion gate (left byte-for-byte unchanged) or being used as a substitute
  for it. Old-format index lines keep working via a safe "unknown, open the file" fallback.
  Plain `surface relevant memory` calls still open every entry file — the index carries no
  description text, so this pass does not reduce their cost; that scope decision was made and
  accepted explicitly rather than expanding the index schema.
- `INTEROP.md` now documents the two-hop `nelly-planning-agent`/`nelly-research-agent`
  brief-repaste cost as an accepted, harness-constrained tradeoff (no subagent-to-subagent calls
  in this harness), so consumers can decide whether they need both subagents for a task before
  paying the brief's token cost twice.

## [0.2.0] - 2026-08-10

- Added two new entry types, `file-relevance` and `error-prevention`, extending the entry
  template without changing any existing entry type's behavior.
- File-relevance matching — a `target files` brief input against which `nelly-orchestrator`
  returns a `File relevance:` sub-list, and file-change-aware staleness for these entries,
  additive to the existing 90-day age-based prune.
- Error-prevention recording — explicit-primary capture via a new `error lesson` input, plus a
  narrowly-scoped best-effort automatic detection path that only ever produces `inferred`-
  confidence entries. A structural exclusion invariant keeps `inferred` entries out of every
  surfacing path (briefs, handoff, spinoff) until a human confirms them via the new
  `confirm error lesson` input, which promotes them to normal confidence.
- Supersession write-back for error-prevention entries, reusing the existing archive mechanism
  and logging a new `Action: superseded` value in `CONSOLIDATION-LOG.md`.
- `handoff surfacing` — a narrower brief-request mode for consumer orchestrators to call at
  their own phase/agent-transition points, documented in `INTEROP.md`'s new "Handoff points"
  section.
- Aside-spinoff context bundles — an `aside task description` brief input that returns
  conditional `Spinoff prompt:`/`Spinoff tldr:` output shaped for `spawn_task`-style handoff to
  a separate context.
- Two new subagents, `nelly-planning-agent` and `nelly-research-agent`, both working from a
  caller-supplied memory brief only — neither ever accesses memory files directly.
- `commands/nelly-memory.md` — added `error-lesson` and `confirm-lesson` subcommands.
- Review caught and fixed a recurring ordering-hazard pattern (a restriction declared in a
  later section while an earlier step already performed the action needing gating) in three
  places (Phases 4, 7), and it was proactively avoided in a fourth (Phase 8) — a real finding
  worth naming, in the spirit of the 0.1.4 entry's bug-found-via-review framing.

## [0.1.7] - 2026-08-10

- Added `INTEROP.md` — the first documented consumer contract for a plugin other than
  spec-driven-development: path resolution via `hooks/nelly_memory.py`, `nelly-orchestrator`'s
  brief request/response contract, `hooks.json`'s automatic-on-install wiring (no consumer-side
  hook needed), the `slug` terminology disambiguation (`project_slug()` vs. SDD's "feature
  slug"), and the standalone-independence guarantee, all restated in fully generic language.
- Added `references/example-consumer-pa-jay.md` — an illustrative (not wired-up) worked example
  showing how `claude-pa`'s real `money-check` skill would call `nelly-orchestrator`, using its
  actual MCP tool names and `auth_required` graceful-degradation convention. No file in
  `claude-pa`'s own repo was touched.
- Generalization audit (recorded in this feature's `design.md`): re-checked
  `agents/nelly-orchestrator.md`, `hooks/nelly_memory.py`, `hooks/nelly_memory_permission.py`,
  `hooks/nelly_slug_guard.py`, and `hooks/nelly_session_start.py` — no code-level SDD-specific
  assumption found; the prior feature had already generalized the implementation and
  `test_no_workflow_lifecycle_terms_in_output` already guards it. No production code changed;
  `pytest -q hooks/` confirmed unchanged at 70/70 before and after.
- Added a `MANUAL-VALIDATION.md` section for the one live-session step this feature still
  needs: confirming `nelly-orchestrator`'s brief contract holds for a non-SDD-shaped caller —
  not yet executed.

## [0.1.6] - 2026-08-10

- `MANUAL-VALIDATION.md` — ran Fixture Set G/H/I (batch fact write-back, added in 0.1.5)
  live from an `EnterWorktree` scratch cwd: duplicate-pair merge (3 facts in, 2 entries
  out), no-duplicate batch (2 facts in, 2 independent entries), and partial-failure
  independence (one fact's write genuinely blocked via macOS `chflags uchg`, confirmed the
  other fact still wrote, indexed, and promotion-judged normally, and the batch did not
  abort). All three verified by direct filesystem inspection, not self-reported agent
  output. The first partial-failure attempt used `chmod 444`, which turned out not to
  block the write tool's atomic rename-over-target pattern (only directory permission is
  needed for that) — `nelly-orchestrator` correctly reported the true outcome instead of
  fabricating a failure to match the fixture, which is recorded as a positive finding
  about the validation approach, not a bug.

## [0.1.5] - 2026-08-10

- `nelly-orchestrator` — added a `new facts` (plural) batch input alongside the existing
  singular `new fact`, so a caller with several facts to record (e.g. `sdd`'s agent-TDD
  Handoff Facts For Memory, which can list multiple facts per slice) makes one subagent call
  instead of N. Driven by `sdd` 1.7.0's real integration: its own docs describe writing back a
  list of handoff facts through a contract that only ever accepted one fact per call. Includes
  an in-batch near-duplicate check (grouping items that describe the same underlying fact
  before any write happens, reconciled into one merged entry) and sequential per-entry
  write-then-promote processing so a single entry's failure doesn't abort the rest of the
  batch.

## [0.1.4] - 2026-08-10

- Fixed `nelly-orchestrator`'s "Recording a new fact" and "Import" flows silently failing to
  create the entry file while still reporting success and updating `MEMORY.md`'s index —
  `entries/` had no directory-creation step (unlike the existing `archive/` file-move
  mechanism, which already did an explicit `mkdir`). Found via live end-to-end verification of
  a separate plugin's (`sdd`) integration with agent-nelly, reproduced and confirmed with direct
  filesystem checks rather than trusting the agent's self-reported success. Added
  `ensure_entries_dir()`/`--entries-path` to `hooks/nelly_memory.py`, wired both flows to call
  it via `Bash` before writing the entry file, and both now require a post-write verification
  read before reporting success. New regression test reproduces the exact sequence and asserts
  the entry file exists on disk, not just the index line.

## [0.1.3] - 2026-08-09

- `MANUAL-VALIDATION.md` — completed the full manual-validation runbook, using
  `EnterWorktree` to give the live session a genuinely different real working
  directory (resolving the prior structural blocker where a subagent couldn't
  impersonate a different project cwd past `nelly_slug_guard.py`). All fixtures
  (promotion buckets A/B/C, staleness/prune, consolidation, intent alignment,
  `view` empty/populated, `import` create/skip/overwrite) now pass, verified by
  direct filesystem inspection rather than self-reported agent output.

## [0.1.2] - 2026-08-09

- `MANUAL-VALIDATION.md` — ran the empty-project and delegation-grep fixtures live;
  recorded a structural finding that `nelly_slug_guard.py` correctly blocks a subagent
  from impersonating a different project cwd, confirming the remaining fixtures need a
  session whose real working directory is a scratch project.

## [0.1.1] - 2026-08-09

Initial build: a standalone, general-purpose memory orchestration plugin for Claude Code,
generalizing the spec-driven-development plugin's `memory-orchestrator` capability so any
plugin or skill can use it, independent of SDD.

- `hooks/nelly_memory.py` — path-resolution API (`project_slug`, `memory_dir`, `entry_path`,
  `archive_path`, `list_entries`, `global_dir`) under an independent store,
  `~/.claude/agent-nelly-memory/`.
- `hooks/nelly_memory_permission.py` / `hooks/nelly_slug_guard.py` — structural guardrail
  hooks (auto-approve reads/writes under the memory root, deny wrong-slug writes).
- `hooks/nelly_session_start.py` — SessionStart announcement (memory root, Intent, entries,
  bounded global index).
- `agents/nelly-orchestrator.md` — sole owner of the memory store: goal-aware brief assembly,
  intent-alignment checking, cross-project promotion (LLM judgment), and two new learning
  behaviors — staleness detection with archival, and consolidation of near-duplicate entries
  (both archive-not-delete, never silent).
- `commands/nelly-memory.md` — `/nelly-memory view | import | prune | consolidate`.
- `references/` — entry and log templates.
- 65 passing tests; `MANUAL-VALIDATION.md` — a runbook for the live-session-only fixtures.
