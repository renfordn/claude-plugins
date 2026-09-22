# Interop: agent-cache-plugin

`agent-cache-plugin` is a soft dependency: a token-efficiency utility other plugins may use, never
one they require to function. It stores and scores reuse of agent outputs/reasoning across a
session. This document is the authoritative description of its actual integration surface, for
this plugin's own maintainers and any sibling plugin's maintainers to cross-check.

> Unlike `agent-isdd`/`agent-tdd`/`agent-nelly`/`agent-ux`/`code-reviewer`, this plugin is a Node
> package, not a Python-hooks-plus-Markdown-skills plugin — its programmatic surface (`skills/*`)
> is only directly callable from JS/Node code, not from another plugin's own hooks or skills
> unless that caller shells out to Node.

## What another plugin can actually integrate with

There is **no network service** (no HTTP server, no MCP server, no listening port) exposed by
this plugin — `package.json` has no `bin` entry and no server script, and no file under
`hooks/`, `skills/`, or `commands/` opens a socket or starts a listener. Every integration point
below is either (a) automatic via Claude Code's own hook dispatch, (b) an explicit `Agent`-tool
subagent spawn, or (c) a CLI command run via `Bash`.

### 1. Automatic — its own hooks (no caller action needed)

Once this plugin is installed alongside another, `hooks/hooks.json` registers three hooks that
fire on Claude Code's own event bus, not on anything a sibling plugin calls directly:

| Event | Hook | Effect |
|---|---|---|
| `PreToolUse` (matcher `Agent`) | `hooks/pre-agent-spawn.js` | Checks for a usable cached result before an agent spawn proceeds. |
| `PostToolUse` (matcher `Agent`) | `hooks/post-agent-completion.js` | Stores the agent's output/reasoning for future reuse. |
| `SessionEnd` | `hooks/cache-invalidation.js` | Invalidates session-scoped entries. |

No sibling plugin needs to invoke anything for this layer — it observes every `Agent` tool call
in the session automatically, including spawns made by `agent-isdd`, `agent-tdd`, and others.

### 2. Explicit — its two subagents

| Subagent | Purpose | Tool access |
|---|---|---|
| `agent-cache-plugin:agent-cache-orchestrator` | Decide cache reuse vs. fresh reasoning for a given task; score relevance | Cache Management skill, Metrics Tracker skill, Read/Grep, Bash |
| `agent-cache-plugin:cache-validator` | Validate cache entries and score their relevance to current tasks | (see `agents/cache-validator/AGENT.md`) |

A sibling plugin's orchestrating skill invokes these the same way it would `agent-nelly:nelly-orchestrator`
— via the `Agent` tool, `subagent_type: agent-cache-plugin:agent-cache-orchestrator` (or
`cache-validator`), gated by an Availability Check against the session's agent-types listing
(same pattern documented in `agent-isdd`'s `workflow-manager/SKILL.md`). Neither subagent talks
to the user; the caller owns surfacing its result.

### 3. Explicit — CLI commands (via Bash)

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/cache-command.js" cache-status [--detailed] [--export json|csv|html]
node "${CLAUDE_PLUGIN_ROOT}/scripts/cache-command.js" cache-clear [--all --yes | --scope <scope>]
node "${CLAUDE_PLUGIN_ROOT}/scripts/cache-command.js" cache-config --set <key> <value>
```

Also exposed as slash commands (`/cache-status`, `/cache-clear`, `/cache-config`,
`/cache-dashboard`) when this plugin is installed directly in the calling session — not something
a sibling plugin can invoke on another plugin's behalf, only relevant when a human is driving the
session this plugin is installed into.

### 4. In-process — skills' JS API (Node callers only)

```javascript
const cacheManagement = require('<path-to-agent-cache-plugin>/skills/cache-management');
const stored = await cacheManagement.store({ prompt, output, metadata: { agentType, ttl } });
const { entry, found } = await cacheManagement.retrieve(stored.entryId);
```

Only usable by a caller that is itself Node/JS code (e.g. a hook script), not by a Python hook or
a Markdown skill — those callers should use option 2 or 3 instead.

## Known non-existent integration path (do not rely on this)

`agent-isdd/hooks/cache_hook.py` (as of this writing) attempts to reach this plugin over HTTP —
`POST http://localhost:7771/cache/write` and `POST http://localhost:7771/cache/invalidate` — on
the assumption of an "MCP interface" this plugin does not implement. This plugin has never run
an HTTP server on port 7771 or any other port; every such request fails with a connection error,
which `cache_hook.py` already catches and treats as graceful degradation (a no-op), so it causes
no visible failure — but it also means `agent-isdd`'s phase-state caching via this path has never
actually worked. Any future caller should use option 2 (subagent) or option 4 (in-process API)
instead; `agent-isdd`'s own hook should be corrected to stop assuming a network interface that
was never built (tracked separately — see the first-class-plugin-collection backlog).

## Graceful degradation

Every integration option above is optional by design. A caller checking availability (per the
Availability Check pattern) should treat this plugin's absence, or a subagent-not-found error, as
non-fatal and continue without caching — exactly how `agent-nelly` and `agent-ux` are already
treated as soft dependencies elsewhere in this collection.
