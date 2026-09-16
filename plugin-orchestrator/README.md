# plugin-orchestrator

Caching-first workflow router that coordinates the `agent-isdd` → `agent-tdd` →
`code-reviewer` handoff chain, distributes the `agent-nelly` memory brief once,
and validates handoff payloads against `INTEROP.md` capability contracts.

## Using this on other projects (incl. cloud sessions)

This repo doubles as a Claude Code plugin (`.claude-plugin/`). Installing it
into any other project via the marketplace is what makes it portable — no
per-project `.claude/settings.json` copying required:

```
/plugin marketplace add renfordn/plugin-orchestrator
/plugin install plugin-orchestrator
```

Once installed, the plugin's own `SessionStart` hook
([hooks/bootstrap-plugins.sh](hooks/bootstrap-plugins.sh)) clones/updates
`renfordn/claude-plugins` into `~/.claude/plugins/claude-plugins` on its own,
and `CapabilityMap()` defaults to that path when `CLAUDE_PLUGINS_DIR` isn't
set — so a fresh cloud session (phone, web, wherever) bootstraps the same
`agent-isdd` / `agent-tdd` / `code-reviewer` / `agent-nelly` / `agent-ux`
dependency set with zero host-project configuration.

## Scope: this is not a standalone, general-purpose harness

`plugin-orchestrator` only activates *inside an active `agent-isdd` SDD
workflow*. It does not scaffold or own its own state — it reads and mutates
the same per-feature `workflow-state.json` that `agent-isdd` scaffolds and
`agent-tdd`/`agent-nelly` also read.

This is a deliberate shared-state convention across the plugin family, not an
oversight local to this repo:

- The file lives at `${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/spec/<feature>/workflow-state.json`.
- `agent-isdd` creates it when an SDD workflow starts.
- `agent-tdd`, `agent-nelly`, and this plugin each keep a small,
  dependency-free copy of the locator logic
  (`project_slug()` / `memory_dir()` / `workflow_state_path()` — see
  [hooks/hook_state.py](hooks/hook_state.py)) rather than importing a shared
  library, because each plugin's `CLAUDE_PLUGIN_ROOT` is a separate directory
  tree at install time.
- This plugin coordinates access to the shared sdd-memory via symlink or registry
  (see Storage section below).

**Consequence:** if no `agent-isdd` workflow is active for the current
project, `hooks/before_continue.py` and `hooks/subagent_stop.py` both no-op
(`workflow_state_path()` returns `None`). This plugin does not currently
coordinate ad hoc agent chains outside that specific pipeline. If that's ever
needed, it requires either a fallback state format of its own or a genuine
shared-state library extracted out of the four plugins that duplicate this
logic today — not a change local to this repo alone.

## Storage

Plugin-orchestrator shares workflow-state access with agent-isdd via symlink coordination:

```
${CLAUDE_PLUGIN_DATA}/sdd-memory/
└── <project-slug>/
    └── spec/
        └── <feature-slug>/
            └── workflow-state.json     # Shared state (symlinked to agent-isdd)
```

**Coordination mechanism:**
- If agent-isdd's sdd-memory already exists: plugin-orchestrator creates a symlink to it
- If symlink creation fails (e.g., Windows): plugin-orchestrator creates a registry file with metadata
- Both plugins transparently access the same workflow state

Where `${CLAUDE_PLUGIN_DATA}` resolves to `~/.claude/plugins/data/plugin-orchestrator/` when running in Claude Code.

## What it actually does

- **`hooks/before_continue.py`** (`PreToolUse`, matcher `Agent`): before an
  `Agent` tool call, caches context and creates checkpoints in `workflow-state.json`,
  surfaces rollback alerts via `systemMessage`, and exits cleanly without modifying
  tool input (`agent-isdd` pattern, avoiding harness schema validation errors).
- **`hooks/subagent_stop.py`** (`SubagentStop`): on subagent completion, logs
  the handoff and validates its contract via
  `orchestrator.hooks.subagent_stop.handle_agent_completion`.
- **`orchestrator/interop_parser.py`** (`CapabilityMap`): parses each
  dependency plugin's `INTEROP.md`/`STRUCTURE.md` for `## → <plugin>` handoff
  sections and declared capabilities (consumes/produces contracts).
- **`orchestrator/core.py`** (`PluginRouter`): checks plugin availability from
  session context, distinguishes hard vs. soft dependencies, validates
  handoff payloads against `CapabilityMap` contracts, and routes
  `(current_plugin, current_phase) → next_plugin` using
  [`orchestrator/routing_table.json`](orchestrator/routing_table.json) —
  editable without touching `core.py`. Each route is cross-checked against
  the source plugin's `INTEROP.md`-derived `handoff_targets` at load time
  (warns, doesn't fail, since not every phase-specific route has a distinct
  INTEROP section).
- **`orchestrator/cache_strategy.py` / `checkpoint.py` / `error_handler.py` /
  `nelly.py`**: prompt-cache-aware context layout, checkpointing, contract
  error recovery, and single-fetch distribution of the `agent-nelly` memory
  brief across the workflow.

Both hooks degrade to a no-op on any failure (`except Exception: sys.exit(0)`)
so a bug here never blocks a real agent spawn or subagent completion.

## MCP server: `get_spawn_context`

`hooks/before_continue.py` computes the same Tier 1 (capability map + nelly
brief) / Tier 2 (design spec) / error-pattern context on every `Agent`-tool
spawn, but can never inject it into the spawned subagent's prompt — the
harness's `updatedInput` merge for the `Agent` tool is broken (see that
hook's own module docstring and `tests/test_before_continue_cli_contract.py`
for the full history), so today the computed context is simply thrown away.

[`mcp_server/server.py`](mcp_server/server.py) is a small bundled MCP server
(declared in `.claude-plugin/plugin.json`'s `mcpServers` field, started
automatically) exposing one tool, `get_spawn_context(agent_type, cwd)`. A
subagent has no `Agent` tool and can't invoke a skill or hook, but it *can*
call an ordinary MCP tool — so instead of trying (and failing) to push
context into its prompt, it can pull the exact same cached context itself,
read-only, as soon as it's spawned.

Requires `pip install -r mcp_server/requirements.txt` (the `mcp` package) —
the one place in this plugin with a real third-party dependency; the
production hooks themselves stay dependency-free. Tests for it
(`tests/test_mcp_spawn_context_server.py`) skip automatically when `mcp`
isn't installed.

## Dependencies

Declared as `optionalDependencies` in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json):
`agent-isdd`, `agent-tdd`, `code-reviewer` (hard — block workflow routing if
missing), `agent-nelly`, `agent-ux`, `agent-cache-plugin` (soft — logged,
routing continues without them).

## Distributed workflow state (Redis)

`orchestrator.state_store.RedisStateStore` shares workflow state across
machines (`FileStateStore` only covers processes on one host). Configure it
via `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB`/`REDIS_PASSWORD`/`REDIS_KEY_PREFIX`
environment variables, or the matching constructor kwargs, which take
precedence.

To keep Redis off the public internet, run it on a private
[Tailscale](https://tailscale.com) network and point `REDIS_HOST` at the
box's tailnet address — no other setup needed, since a tailnet address
resolves/connects like any other host:

```bash
export REDIS_HOST=redis-box.your-tailnet.ts.net   # MagicDNS name, or
export REDIS_HOST=100.x.y.z                       # tailnet IP directly
```

The orchestrator process just needs to be on the same tailnet (`tailscale up`)
for that address to be reachable.

## Tests

```bash
python3 -m unittest discover -s tests -q
```
