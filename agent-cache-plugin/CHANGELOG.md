<!-- TDD-SKIP -->
## [Unreleased]

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
