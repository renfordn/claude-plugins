# plugin-harness

Caching-first workflow router that coordinates the `agent-isdd` → `agent-tdd` →
`code-reviewer` handoff chain, distributes the `agent-nelly` memory brief once,
and validates handoff payloads against `INTEROP.md` capability contracts.

## Quickstart

```bash
claude plugin marketplace add renfordn/claude-plugins
claude plugin install plugin-harness@renfordn-plugins
```

The MCP server (`spawn-context`) starts automatically on session launch. Confirm it's running:

```bash
claude mcp list
```

Expected: `spawn-context` listed as an active MCP server. `plugin-harness` works best alongside
its sibling plugins (`agent-isdd`, `agent-tdd`, `code-reviewer`, and the optional
`agent-nelly`/`agent-ux`) — see [docs/install-and-verify.md](../docs/install-and-verify.md) in
this repo for the full multi-plugin install/verify guide. The rest of this section covers using
this repo directly rather than via the marketplace (e.g. for local development).

## Using this on other projects (incl. cloud sessions)

This repo doubles as a Claude Code plugin (`.claude-plugin/`). Installing it
into any other project via the marketplace is what makes it portable — no
per-project `.claude/settings.json` copying required. `plugin-harness` lives
in the `renfordn/claude-plugins` monorepo (there is no separate
`renfordn/plugin-harness` repo), so install it from there:

```
/plugin marketplace add renfordn/claude-plugins
/plugin install plugin-harness@renfordn-plugins
```

Once installed, the plugin's own `SessionStart` hook
([hooks/bootstrap-plugins.sh](hooks/bootstrap-plugins.sh)) clones/updates
`renfordn/claude-plugins` into its own `${CLAUDE_PLUGIN_DATA}/claude-plugins`,
and `CapabilityMap()` defaults to that path when `CLAUDE_PLUGINS_DIR` isn't
set — so a fresh cloud session (phone, web, wherever) bootstraps the same
`agent-isdd` / `agent-tdd` / `code-reviewer` / `agent-nelly` / `agent-ux`
dependency set with zero host-project configuration.

## Scope: standalone-capable harness, with deeper integration when an SDD workflow is active

`plugin-harness` is a general-purpose harness usable by any plugin in the
suite, independent of whether an `agent-isdd` SDD workflow is active — no
plugin's absence, and no absent SDD workflow, ever blocks another plugin's
own standalone operation.

**Standalone mode (no `agent-isdd` SDD workflow active, no
`workflow-state.json` required):** `hooks/before_continue.py` routes into
`handle_standalone_spawn()`, which builds a capability map (pure filesystem
read of `INTEROP.md` files, same as the SDD-active path) plus a
project-scoped nelly-brief lookup, both cached in a new `HarnessContextCache`
(`${CLAUDE_PLUGIN_DATA}/plugin-harness/<project-slug>/context-cache.json`) —
independent of `workflow-state.json`'s existence. `get_spawn_context` reads
that same cache and returns a `source: "standalone"`-shaped response.
Telemetry emits a `"standalone_context_requested"` event to a
project-scoped `telemetry.jsonl`, instead of silently no-op'ing. This is
tested (see `tests/test_standalone_spawn.py`, `tests/test_spawn_context.py`,
`tests/test_hook_telemetry.py`) and is a supported activation mode, not
experimental.

**SDD-workflow-active mode (unchanged):** when an `agent-isdd` SDD workflow
IS active, `plugin-harness` reads and mutates the same per-feature
`workflow-state.json` that `agent-isdd` scaffolds and `agent-tdd`/`agent-nelly`
also read, and additionally provides Tier 2 (design spec) context, handoff
routing, and `INTEROP.md` contract validation — none of which standalone mode
attempts to replicate, since those genuinely require an SDD workflow's
design spec and phase state to exist.

This is a deliberate shared-state convention across the plugin family for the
SDD-workflow-active path, not an oversight local to this repo:

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

**When no `agent-isdd` workflow is active** for the current project,
`hooks/before_continue.py` and `hooks/subagent_stop.py` no longer simply
no-op (`workflow_state_path()` returning `None` used to mean "exit
immediately") — `before_continue.py` now takes the standalone path described
above; `subagent_stop.py`'s SDD-specific handoff logging/validation still has
nothing to do without an active workflow, since there's no handoff to log.

## Storage

Plugin-harness shares workflow-state access with agent-isdd via symlink coordination:

```
${CLAUDE_PLUGIN_DATA}/sdd-memory/
└── <project-slug>/
    └── spec/
        └── <feature-slug>/
            └── workflow-state.json     # Shared state (symlinked to agent-isdd)
```

**Coordination mechanism:**
- If agent-isdd's sdd-memory already exists: plugin-harness creates a symlink to it
- If symlink creation fails (e.g., Windows): plugin-harness creates a registry file with metadata
- Both plugins transparently access the same workflow state

Where `${CLAUDE_PLUGIN_DATA}` resolves to `~/.claude/plugins/data/plugin-harness/` when running in Claude Code.

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
