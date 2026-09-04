# claude-plugins

Monorepo for Renford Nelson's personal Claude Code plugins, used together by
[plugin-orchestrator](https://github.com/renfordn/plugin-orchestrator):

- `agent-isdd/` — spec-driven design agent (hard dependency)
- `agent-tdd/` — test-driven implementation agent (hard dependency)
- `code-reviewer/` — code review skill (hard dependency)
- `agent-nelly/` — memory system (soft dependency)
- `agent-ux/` — UI rendering (soft dependency)

Each subdirectory is a standalone plugin (own `.claude-plugin/plugin.json`,
`INTEROP.md`, etc.) migrated here as a fresh snapshot — commit history prior
to the migration lives in the original per-plugin repos:
[agent-isdd](https://github.com/renfordn/agent-isdd),
[agent-tdd](https://github.com/renfordn/agent-tdd),
[code-reviewer](https://github.com/renfordn/code-reviewer),
[agent-nelly](https://github.com/renfordn/agent-nelly),
[agent-ux](https://github.com/renfordn/agent-ux) (archived).

## Why one repo

plugin-orchestrator's `CapabilityMap` reads all 5 plugins from a single base
directory (`CLAUDE_PLUGINS_DIR`, one subdirectory per plugin). In a fresh
Claude Code cloud session, getting a private repo's content requires an
explicit `add_repo` approval per repo — five separate repos meant five
approvals every time. This repo collapses that to one `add_repo` + one
`git clone`.
