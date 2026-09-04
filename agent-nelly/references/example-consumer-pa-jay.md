<!-- TDD-SKIP -->
# Worked Example: `claude-pa`'s `money-check` Skill As An Agent Nelly Consumer

> **This is illustrative only.** Nothing here is wired up. No file in `claude-pa`'s actual
> repo (`~/.claude/plugins/claude-pa`) is created, modified, or referenced by any code in this
> repo. This document exists purely to stress-test [`INTEROP.md`](../INTEROP.md)'s contract
> against a plugin shaped nothing like spec-driven-development: `claude-pa` has independent,
> stateless skills (`money-check`, `morning-brief`, `task-control`, `media-find`, `pa-dispatch`,
> `work-hours`) and its own MCP servers, with no workflow, phase, or feature-slug concept
> anywhere.

## Trigger context

Jay asks his assistant "how much did I spend today?" — `claude-pa`'s `money-check` skill
(`~/.claude/plugins/claude-pa/skills/money-check/SKILL.md`) is invoked. As documented in that
skill's real behavior, it would call the `monzo` MCP server's `list_accounts()`, then
`get_balance(account_id)` for each account, formatting pence as `£X.XX`.

A single, stateless, one-turn skill invocation — nothing about it resembles SDD's
requirements/design/tasks phases.

## A concrete request to `nelly-orchestrator`

Before (or while) answering, `money-check` could ask `nelly-orchestrator` for a brief:

```
cwd: ~/.claude/plugins/claude-pa   (illustrative — see "Assumption" below)
task description: "checking Monzo balance and recent spending for Jay"
surface relevant memory: true
```

`surface relevant memory` is passed here because the skill wants to know about any
previously-recorded facts relevant to a Monzo/spending query before it answers — e.g. a
standing note about needing to re-authorize.

## A plausible brief response

Following the real four-section contract from `agents/nelly-orchestrator.md`, exactly as
`INTEROP.md` describes it:

```
Intent: not yet captured

Relevant entries:
- monzo-reauth-needed-periodically — Monzo MCP requires periodic re-authorization; run
  `uv run python monzo_oauth.py` from `servers/monzo-mcp/` when a tool call returns
  `{"error": "auth_required"}`.

Intent alignment: not applicable — no Intent captured yet.

Written: none
```

This demonstrates the contract holding for a caller with **zero** phase/goal/feature-slug
vocabulary: `Intent alignment` degrades gracefully to "not applicable" rather than requiring a
personal-assistant plugin to have ever defined a project-level Intent, and `Relevant entries`
surfaces a plain, skill-relevant fact with no SDD concepts anywhere in it.

## A concrete `new fact` example

Grounded in `money-check/SKILL.md`'s actual documented graceful-degradation convention: if a
Monzo tool call returns `{"error": "auth_required", ...}`, that's a fact worth remembering
across sessions, not just handling once and forgetting. `money-check` could record it:

```
new fact: "Monzo MCP requires periodic re-authorization; run `uv run python monzo_oauth.py`
from `servers/monzo-mcp/` when a tool call returns {"error": "auth_required"}."
```

`nelly-orchestrator` would write this as a new entry (e.g.
`entries/monzo-reauth-needed-periodically.md`), add it to `MEMORY.md`'s index, and run the
promotion judgment on it — this is Bucket 2 (clearly project-specific: it names a specific
script path and a specific MCP server), so it stays local to `claude-pa`'s own memory tier, no
promotion to the cross-project `global/` store.

## Assumption

`money-check/SKILL.md` doesn't declare an explicit project root for subagent calls it might
make — skills don't carry their own `cwd` field. This example assumes `cwd` would resolve to
`claude-pa`'s plugin root (`~/.claude/plugins/claude-pa`) or the user's active session
directory at invocation time. This is a labeled assumption for the purpose of this
illustration, not an observed fact about how `claude-pa` actually resolves paths today — a real
integration would need to pin this down explicitly.

## What this proves, and what it doesn't

This shows the brief contract, the `Intent`/`Relevant entries`/`Intent alignment`/`Written`
shape, and the promotion judgment all working correctly for a caller shaped nothing like SDD.
It does **not** mean `money-check` actually calls `nelly-orchestrator` today, and building that
real integration is explicitly out of scope for this document — see this feature's
`requirements.md` Non-Goals.
