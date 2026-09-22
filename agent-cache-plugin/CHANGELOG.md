<!-- TDD-SKIP -->
## [Unreleased]

## [2.1.0] - 2026-09-22

- **Feat**: `/cache-config --set` now actually works and persists. `CacheManager` gained a
  `config` table with `getConfig()` / `configure()` / `resetConfig()` for the four real settings
  (`maxEntries`, `defaultTTL`, `relevanceThreshold`, `stalenessThreshold`); `maxEntries` and
  `defaultTTL` apply to the live instance, and `agent-cache-orchestrator` reads the two
  thresholds from the persisted config at construction. Retired the never-implemented `maxSize`
  and `evictionPolicy` keys (the SQLite backend is LRU-by-count and does not track bytes).
- **Fix**: `/cache-config --set KEY VALUE` was unreachable — the CLI parsed it as an array the
  command never read. `--reset [KEY]`, `--get KEY`, and combined `--list --validate` now work.
- **Fix**: `/cache-clear` called Map-era APIs (`entry.id`, `entry.metadata.timestamp`,
  `clear().count`, `cacheSize`) that don't exist on the SQLite backend, so every filtered clear
  either deleted nothing or reported NaN. Rewritten on a new `CacheManager.invalidateWhere()`
  (bulk delete sharing `search()`'s filters, which gained `taskSlug`, `olderThan`, `before`,
  `includeExpired`). Supports `--agent`, `--task`, `--older-than`, `--before`, `--pattern`,
  `--id`, `--tags`, and `--all --yes`; `--all` alone asks for confirmation instead of deleting.
- **Fix**: `scripts/cache-command.js` printed `result.output` (never set) and treated
  `status: 'error'` as success — errors now go to stderr with exit 1 and reports print.
- **Tests**: `tests/command-integration.test.js` runs against a temp `CLAUDE_PLUGIN_DATA` (it
  previously ran `clear --all --yes` against the developer's real cache) and asserts real DB
  mutations; new `sqlite-cache` unit tests for config persistence and `invalidateWhere()`.
- **Docs**: `STRUCTURE.md` → "Capabilities" now advertises the plugin's one real cross-plugin
  capability, `agent_output_cache` (the automatic `Agent`-tool hooks), instead of the
  never-built `phase_state_cache` HTTP contract; `commands/cache-config.md` and
  `cache-clear.md` rewritten to match what the commands do; `docs/ROADMAP.md` gained the
  sibling-plugin key/value transport idea.

## [2.0.10] - 2026-09-22

- **Docs**: `STRUCTURE.md`'s `## Capabilities` section extended with this plugin's full real
  integration surface (automatic hooks, the two subagents, CLI commands, in-process JS API) and a
  documented gap — the `phase_state_cache` HTTP transport `agent-isdd/hooks/cache_hook.py` expects
  was never actually implemented here (no server ever ran on the assumed port). Extracted the
  still-open roadmap ideas from the retired `FOLLOW_UP_ITEMS.md` into a new `docs/ROADMAP.md`.
- **Chore**: removed five one-time migration/shipping status docs no longer reflecting current
  state (`FOLLOW_UP_ITEMS.md`, `MARKETPLACE_SUBMISSION.md`, `SHIPPING_CHECKLIST.md`,
  `V1.3_RELEASE_NOTES.md`, `tasks.md`) and fixed `README.md`'s two links that pointed at them.
- **Fix**: `LICENSE` and `package.json`'s `license` field were MIT, diverging from every other
  plugin in this collection (all-rights-reserved); unified to match. `.claude-plugin/plugin.json`
  now declares `INTEROP.md` absent via `first_class.declared_absent` — `STRUCTURE.md` is this
  plugin's real, already-integrated INTEROP equivalent (see
  `plugin-harness/orchestrator/schema_extractor.py`).

## [2.0.9] - 2026-09-21

- **Test**: harden `hook-wiring.test.js` and `manifest.test.js` against the `hooks.json`-location regression fixed in 2.0.8 — assert `.claude-plugin/hooks.json` does not exist and `plugin.json` declares no inline `hooks` array, and validate hook wiring against `hooks/hooks.json` (the file Claude Code actually loads) instead of the old, unloaded path.

## [2.0.8] - 2026-09-21

- **Fix**: `hooks.json` lived at `.claude-plugin/hooks.json`, the one location Claude Code doesn't auto-load hook config from, and `plugin.json` additionally declared its own inline `hooks` array (a shape `claude plugin validate` flags as "unknown hook event; entry ignored at runtime") — so none of this plugin's hooks were ever wired up on install. Relocated to `hooks/hooks.json` to match `agent-isdd`, `agent-tdd`, and `plugin-orchestrator`'s convention, and removed the dead inline array.
- **Docs**: fixed `docs/install-and-verify.md`'s cache-plugin smoke test, which called the nonexistent `cache-status` subcommand instead of the real `status` subcommand, and added the missing `npm install` step (an install doesn't build `better-sqlite3` for you).

## [2.0.7] - 2026-09-21

- **Test**: fix manifest.test.js — assert commands absent, update hook assertions to match SessionEnd and matcher:Agent.

## [2.0.6] - 2026-09-20

- **Fix**: align PostToolUse hooks with hooks.json intent — add `matcher: Agent` to post-agent-completion.js; move cache-invalidation.js to `SessionEnd`.
- **Chore**: add `model: haiku` frontmatter to agent-cache-orchestrator and cache-validator agent definitions.
- **Test**: add current-gen model ID conflict test cases (claude-haiku-4-5-20251001, claude-sonnet-5).

## [2.0.5] - 2026-09-20

- **Fix**: remove unsupported `commands` array from plugin.json — marketplace schema rejects it.
- **Fix**: hook alignment — `post-agent-completion.js` gains `matcher: Agent`; `cache-invalidation.js` moves to `SessionEnd`.
- **Release**: initial CHANGELOG entry for public release pass.
