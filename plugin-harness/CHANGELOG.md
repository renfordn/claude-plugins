<!-- TDD-SKIP -->
## [Unreleased]

- **Docs**: `scripts/check_skill_invocation_consistency.py`'s rule 2 rationale now scopes the
  "never a subagent" rule to the `code-reviewer` *skill*, since code-reviewer now also ships a
  separate reviewer agent for independent review. Patterns unchanged.

- **Fix**: `hooks/hook_state.py`'s `active_state_dir()`/`workflow_state_path()` now skip features whose `workflow-state.md` has `Workflow Status: Complete`. Before, a completed feature stayed "active" as the newest workflow-state.md, and `before_continue.py`/`subagent_stop.py` kept writing its `workflow-state.json`, lock file and `hook_telemetry_log.jsonl` in unrelated sessions. When every feature is Complete, these hooks now take their no-active-workflow path. In-progress and paused features resolve as before.

## [2.1.7] - 2026-09-24

- **Fix**: `orchestrator/harness_context_cache.py`'s `set()` now always removes its temp file in a `finally` block. After a successful write it also deletes `.context-cache.json-*.tmp` files older than `STALE_TMP_SECONDS` (1 h). This matches the `FileStateStore` change in 2.1.5.

## [2.1.6] - 2026-09-24

- **Change**: `hooks/hook_state.py`'s `BASE` now follows agent-isdd's recorded sdd-memory location (`<agent-isdd data dir>/sdd-memory-location.json`, which is its `shared_memory_root` when configured) before falling back to the symlink/registry coordination.
- **Fix**: `_ensure_sdd_memory_coordination()` had a function-local `import json`, so its `except (OSError, json.JSONDecodeError)` could raise `UnboundLocalError`. It now uses the module-level import.
- **Chore**: `hooks/path_resolution.py` synced with `shared/` (shared memory root helpers).

## [2.1.5] - 2026-09-24

- **Fix**: checkpoint snapshots could still carry derived orchestration history, which is what inflated `workflow-state.json` to 18 GB per file on 2026-09-24. `CheckpointManager` now excludes both `orchestration.checkpoints` and `orchestration.handoff_history` from every `state_snapshot` (`SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS`). `restore_checkpoint()` copies both over from the current state, so saving a restored state no longer drops the checkpoint list or audit log. `prune_old_checkpoints()` also strips nested history from snapshots written by older versions, so an already-bloated file shrinks at its next checkpoint.
- **Fix**: `orchestration.handoff_history` is now capped at `MAX_HANDOFF_HISTORY` (200, oldest dropped). The cap applies to all three writers: `CheckpointManager.record_handoff`, `ErrorHandler.log_error` and `subagent_stop._log_handoff`. The checkpoint limit is now the `MAX_CHECKPOINTS` constant (10).
- **Fix**: `FileStateStore.save()` now always removes its temp file in a `finally` block. After a successful write it also deletes this workflow's `.<id>-*.tmp` files that are older than `STALE_TMP_SECONDS` (1 h). Those files are left behind when a process is killed mid-write; 21 of them had used 54 GB.

## [2.1.4] - 2026-09-24

- **Fix (behaviour change)**: no more guessed data-dir fallback. `hooks/path_resolution.py`'s `get_plugin_data_dir()` now raises `PluginDataDirUnavailable` when `CLAUDE_PLUGIN_DATA` is unset instead of guessing `~/.claude/plugins/data/<plugin>/` (which can point at the wrong install identity). Scripts run from skills/commands/agents now pass `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"` and use `${CLAUDE_PLUGIN_ROOT}` paths; tests get a temp `CLAUDE_PLUGIN_DATA` via `conftest.py`.
- **Chore**: moved `first_class.declared_absent` out of `.claude-plugin/plugin.json` into `.claude-plugin/first-class.json` — `claude plugin validate --strict` rejects unknown manifest fields.
- **Change**: `hooks/bootstrap-plugins.sh` and `CapabilityMap()` default to `${CLAUDE_PLUGINS_DIR}`, else `${CLAUDE_PLUGIN_DATA}/claude-plugins` (was a hardcoded `~/.claude/plugins/claude-plugins`); the silent fallback to test fixtures is gone. First session after upgrading re-clones into the plugin's own data dir.
- **Fix**: `get_sibling_plugin_data_dir()` returned plugin-harness's own dir when its data-dir name had an unexpected shape; it now raises.
- **Fix**: `orchestrator/interop_parser.py` rebuilt cached maps against a hardcoded `/Users/.../plugins/claude` base dir; it now uses the live map's base.

## [2.1.3] - 2026-09-24

- **Docs**: `hooks/before_continue.py` and three `orchestrator/` docstrings cited the legacy bare
  `~/.claude/sdd-memory/` path in illustrative examples — the real resolution (`get_plugin_data_dir`/
  `get_legacy_subdir_path` in `path_resolution.py`) never had a bare-path fallback at all, only
  `${CLAUDE_PLUGIN_DATA}/sdd-memory/...`. No behavior change; illustrative examples corrected.

## [2.1.2] - 2026-09-22

- **Fix**: the hard-coded `agent-cache-plugin` capability in `interop_parser.py`,
  `schema_extractor.py`, and `interop_drift_validator.py` was `phase_state_cache`, an HTTP
  write/invalidate/read contract that was never implemented on either side (no server ever ran
  on the assumed port; agent-isdd 0.1.49/0.1.50 removed its half). Replaced with
  `agent_output_cache`, the plugin's real automatic `Agent`-tool hook contract as now documented
  in `agent-cache-plugin/STRUCTURE.md` 2.1.0. `test_smoke_e2e.py` asserts the new capability's
  schema and that the old one is no longer advertised.
- **Fix**: `interop_drift_validator.py`'s "is `interop_parser.py` also staged?" check tested
  exact list membership against `git diff --cached --name-only` output, which is repo-relative
  (`plugin-harness/orchestrator/interop_parser.py`), so it could never pass and every genuine
  schema change was blocked even when the parser was updated in the same commit. Now matches on
  basename. Regression test added.

## [2.1.1] - 2026-09-22

- **Docs**: added a `## Quickstart` section at the top of `README.md` (install one-liner +
  `claude mcp list` verification + pointer to the existing detailed local-dev section).
- **Fix**: `.claude-plugin/plugin.json`'s `license` field said `MIT`, diverging from every other
  plugin in this collection (all-rights-reserved); `LICENSE`'s content unified to match.
- **Chore**: `.claude-plugin/plugin.json` now declares `commands`, `skills`, and `agents` absent
  via `first_class.declared_absent` — this plugin's entire content is `hooks/` + `mcp_server/` +
  `orchestrator/`, a routing/MCP-server plugin, not an agent-toolkit.

## [2.1.0] - 2026-09-22

- **Breaking**: removed the `PLUGIN_ORCHESTRATOR_TELEMETRY` one-release
  compatibility fallback (and its stderr deprecation notice) introduced in
  2.0.0's plugin-orchestrator -> plugin-harness rename. `PLUGIN_HARNESS_TELEMETRY`
  is now the only supported name; anyone still setting the old var must
  switch.
- **Resolved**: the nested `plugin-harness/.claude-plugin/marketplace.json`
  disposition (open question from 2.0.0) — kept, since `renfordn/claude-plugins`
  is a monorepo and this file is the only supported standalone-install path
  for `plugin-harness` on its own. `README.md`'s install instructions and
  `plugin.json`'s `homepage` were corrected to point at the monorepo
  (`renfordn/claude-plugins`) instead of a non-existent standalone
  `renfordn/plugin-harness` repo.

## [2.0.0] - 2026-09-22

- **Breaking**: renamed `plugin-orchestrator` to `plugin-harness` across the entire monorepo
  (directory, `.claude-plugin/plugin.json` id/name, marketplace listing, and every reference in
  sibling plugins' `INTEROP.md`/`CHANGELOG.md`, root `README.md`/`marketplace.json`, CI, and
  `Dockerfile`). **This is a breaking rename — existing installs must reinstall under the new
  name.** Migration: uninstall `plugin-orchestrator`, then install `plugin-harness`
  (`/plugin marketplace add renfordn/plugin-harness` / `/plugin install plugin-harness`). A
  caller still referencing the old `plugin-orchestrator` name after this release is not
  supported — reinstalling under the new name is required, there is no compatibility shim for
  the plugin name itself.
- **New**: `plugin-harness` now works fully standalone, with no `agent-isdd` SDD workflow
  active and no `workflow-state.json` present — reversing this README's prior "not a
  standalone, general-purpose harness" scope statement. `get_spawn_context` and hook telemetry
  both function usefully with zero prior SDD activity for a project, backed by a new
  project-scoped `HarnessContextCache` (independent of `workflow-state.json`). SDD-workflow-active
  behavior (Tier 2 context, handoff routing, contract validation) is unchanged.
- **New**: telemetry captures a `"standalone_context_requested"` event type for standalone
  usage, in addition to existing SDD workflow event types (`hook_invoked`, `hook_completed`,
  `hook_error`, etc.).
- **Compatibility note**: the `PLUGIN_ORCHESTRATOR_TELEMETRY` env var is still honored as a
  one-release fallback for `PLUGIN_HARNESS_TELEMETRY` (with a one-line stderr deprecation
  notice) so CI/test suppression relying on the old name isn't silently broken mid-migration.
  Tracked for removal in the release after this one.
- **Follow-up (non-blocking)**: disposition of the nested, single-plugin
  `plugin-harness/.claude-plugin/marketplace.json` (kept vs. removed) is still an open question
  — it was renamed along with everything else, but whether it's still actively used separately
  from the root marketplace is unconfirmed.
- **Fix**: `orchestrator/hooks/subagent_stop.py`'s `validate_in_order` referenced `HookErrorType` (from `orchestrator.error`) in its return-type annotation and two return statements, but never imported it — a `NameError` the instant the module loads. Invisible on Python 3.14 (PEP 649 makes annotations lazy there) but fatal on Python 3.11 (this repo's CI runner), confirmed breaking the actual GitHub Actions run. Added the missing import.
- **Fix**: `tests/test_mcp_spawn_context_server.py`'s `test_no_active_workflow_returns_plain_message` asserted the stale `"No active SDD workflow"` string; `_build_standalone_response` intentionally returns the same `"No spawn context cached yet"` message as the workflow-exists-but-empty case when standalone mode has no cache either. Updated the assertion to match.

## [1.3.1] - 2026-09-21

- **Fix**: `hooks/bootstrap-plugins.sh` (SessionStart) treated `agent-isdd`/`agent-tdd`/`code-reviewer` as hard dependencies and called `exit 1` if the `claude-plugins` clone/update failed or any of those three directories were missing, aborting the whole SessionStart hook. Now warns and continues for hard and soft dependencies alike, matching this plugin's own soft-dependency design intent; only a missing `python3` prerequisite still hard-fails. Updated `.claude/CLAUDE.md`'s "Cloud Session Bootstrap" section to match.

## [1.3.0] - 2026-09-21

- **Fix**: `CheckpointManager.create_checkpoint` deep-copied the whole `workflow_state`, including its own `orchestration.checkpoints` array, so each checkpoint's snapshot recursively embedded every prior checkpoint's snapshot — `workflow-state.json` doubled in size on every `Agent` spawn (one real project's file had grown to 389 MB). Snapshots now exclude the prior checkpoints array, and `prune_old_checkpoints` now runs automatically after every append (default cap: 10).
- **Fix**: `hooks/hook_state.py`'s `_ensure_sdd_memory_coordination` resolved `agent-isdd`'s data directory via `get_plugin_data_dir("agent-isdd")`, which ignores its argument whenever `${CLAUDE_PLUGIN_DATA}` is set and returns *this plugin's own* directory instead — in every real marketplace install, plugin-orchestrator's hooks were silently reading/writing their own empty `sdd-memory/` rather than agent-isdd's, so `before_continue`/`subagent_stop` always saw "no active SDD workflow." Added `path_resolution.py`'s `get_sibling_plugin_data_dir()` to resolve a sibling plugin's real directory instead.
- **New**: `CapabilityMap` no longer depends solely on the separately-maintained `~/.claude/plugins/claude-plugins` git clone (which `hooks/bootstrap-plugins.sh` can leave silently stale — a failed `git pull` there is swallowed) — it now discovers each sibling plugin's actual installed root from `${CLAUDE_PLUGIN_ROOT}` (`_discover_sibling_plugin_roots`), which is always exactly the version currently running, and prefers it over the flat clone-based lookup.

## [1.2.9] - 2026-09-20

- **Docs**: promote unpromoted Unreleased CHANGELOG section to versioned [1.2.8] entry.

## [1.2.8] - 2026-09-20

- **Release**: bump version for public release pass.

## [1.2.5] - 2026-09-20

- **Pre-commit hook**: wire `InteropDriftValidator` to `.githooks/pre-commit` (tracked) + `scripts/setup-hooks.sh` for new-checkout setup; add `interop-drift` CI job to `.github/workflows/tests.yml`.

## [1.2.4] - 2026-09-20

- **Consistency pass**: fix `SchemaExtractor` section-awareness (`CAPABILITY_SECTION_KEYWORDS`), filter `get_capability_consumes()` to required fields only, remove `code-reviewer` from `EXPECTED_CAPABILITIES`; update agent-ux fixture fields to match real contract.

## [1.2.3] - 2026-09-20

- **Escalation re-spawn**: record escalation re-spawn outcomes in workflow state.
