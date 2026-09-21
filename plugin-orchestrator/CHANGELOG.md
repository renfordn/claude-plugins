<!-- TDD-SKIP -->
## [Unreleased]

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
