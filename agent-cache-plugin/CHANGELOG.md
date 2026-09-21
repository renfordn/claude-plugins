<!-- TDD-SKIP -->
## [Unreleased]

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
