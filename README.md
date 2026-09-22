# claude-plugins

Monorepo for Renford Nelson's personal Claude Code plugins, used together by
[plugin-harness](./plugin-harness):

- `agent-isdd/` — spec-driven design agent (hard dependency)
- `agent-tdd/` — test-driven implementation agent (hard dependency)
- `code-reviewer/` — code review skill (hard dependency)
- `agent-nelly/` — memory system (soft dependency)
- `agent-ux/` — UI rendering (soft dependency)
- `agent-cache-plugin/` — prompt-caching and context-deduplication (soft dependency)

Each subdirectory is a standalone plugin (own `.claude-plugin/plugin.json`,
`INTEROP.md`, etc.) migrated here as a fresh snapshot — commit history prior
to the migration lives in the original per-plugin repos:
[agent-isdd](https://github.com/renfordn/agent-isdd),
[agent-tdd](https://github.com/renfordn/agent-tdd),
[code-reviewer](https://github.com/renfordn/code-reviewer),
[agent-nelly](https://github.com/renfordn/agent-nelly),
[agent-ux](https://github.com/renfordn/agent-ux) (archived),
[agent-cache-plugin](https://github.com/renfordn/agent-cache-plugin).

## Installing the plugins

See [`docs/install-and-verify.md`](./docs/install-and-verify.md) for the full
install, verification, and troubleshooting walkthrough covering all 7 plugins
in the `renfordn-plugins` marketplace.

## Why one repo

plugin-harness's `CapabilityMap` reads all 6 plugins from a single base
directory (`CLAUDE_PLUGINS_DIR`, one subdirectory per plugin). In a fresh
Claude Code cloud session, getting a private repo's content requires an
explicit `add_repo` approval per repo — six separate repos meant six
approvals every time. This repo collapses that to one `add_repo` + one
`git clone`.

## Running tests

Several plugins ship a private, identically-named `hooks/path_resolution.py`
(and `plugin-harness` also has `hooks/hook_state.py`) as bare modules, not
packages. Running `pytest` across multiple plugins in one invocation lets
`sys.modules` caching from one plugin's copy silently satisfy another
plugin's import of the same bare name, which breaks once the copies diverge.
Always run each plugin's tests in its own `pytest` invocation, the way CI's
`matrix.plugin` strategy does (`.github/workflows/tests.yml`):

```
python3 -m pytest agent-isdd
python3 -m pytest plugin-harness
# ...one plugin per invocation, never `pytest .` from the repo root.
```
