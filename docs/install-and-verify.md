# Install and Verify — Claude Plugin Collection

This guide walks through installing all 6 plugins from the `renfordn-plugins` marketplace,
verifying they are working, and troubleshooting common issues. All plugins can be used
standalone or in any combination.

## Prerequisites

- Claude Code (claude CLI) installed and authenticated
- Internet access for plugin download

---

## Add the Marketplace

All 6 plugins are published from one marketplace, `renfordn-plugins`, backed by the
`renfordn/claude-plugins` GitHub repo. Add it once, before any `claude plugin install`
below — every `@renfordn-plugins` install fails with an unknown-marketplace error until
this step has run:

```bash
claude plugin marketplace add renfordn/claude-plugins
```

## Install All 6 Plugins

Install in dependency order (`plugin-harness` should come last):

```bash
claude plugin install agent-nelly@renfordn-plugins
```

```bash
claude plugin install agent-ux@renfordn-plugins
```

```bash
claude plugin install agent-tdd@renfordn-plugins
```

```bash
claude plugin install agent-isdd@renfordn-plugins
```

```bash
claude plugin install code-reviewer@renfordn-plugins
```

```bash
claude plugin install plugin-harness@renfordn-plugins
```

---

## Verify Install

After installing, confirm all plugins are present and enabled:

```bash
claude plugin list
```

Expected output: all 6 plugins listed with `Status: ✔ enabled`.

---

## Per-Plugin Smoke Verification

Run these one-liners to confirm each plugin is loading correctly. Each prints a short
confirmation (or exits 0) if the plugin is wired up properly.

### agent-nelly

```bash
claude --print "Use the agent-nelly:agent-nelly subagent to fetch the project Intent. Just print the Intent line."
```

Expected: a short response mentioning the project Intent (may be "not yet captured" on a
fresh machine — that is correct).

### agent-ux

`agent-ux` has no slash command or skill of its own — it's a subagent (`agent-ux:ux-agent`)
that other plugins delegate rendering to. Confirm it installed correctly instead:

```bash
claude plugin details agent-ux@renfordn-plugins
```

Expected: a component inventory listing the `ux-agent` agent.

### agent-tdd

`agent-tdd` is a subagent (`agent-tdd:agent-TDD`) plus two skills (`design-spec-direct`,
`slice-spec`), not a top-level slash command:

```bash
claude plugin details agent-tdd@renfordn-plugins
```

Expected: a component inventory listing the `agent-TDD` and `test-author` agents and the
`design-spec-direct` / `slice-spec` skills.

### agent-isdd

```bash
claude --print "/isdd-status"
```

Expected: a short report of any active spec-driven-development workflow in the current
project (or a message that none is active — that is correct on a fresh project). This is
read-only and won't start a new workflow; use `/isdd <feature description>` for that once
you're ready.

### code-reviewer

```bash
claude --print "Use the code-reviewer skill to list its four evidence tiers."
```

Expected: a brief description naming tier-1 through tier-5 evidence tiers. (Claude Code's
own built-in `/code-review` command is a separate thing — this plugin's skill is
`code-reviewer:code-reviewer`, invoked by name or by asking for a code review.)

### plugin-harness

The plugin-harness MCP server starts automatically on session launch once installed.
Confirm it appears in the MCP server list:

```bash
claude mcp list
```

Expected: `spawn-context` listed as an active MCP server.

---

## Standalone Usage

Each plugin works without the others. Minimal standalone setups:

| Goal | Minimum plugins needed |
|---|---|
| Spec-driven design only | `agent-isdd` |
| TDD implementation only | `agent-tdd` |
| Code review only | `code-reviewer` |
| AI memory across sessions | `agent-nelly` |
| UX rendering for specs | `agent-ux` |
| Full orchestrated workflow | All 6 |

---

## Combination Usage

The recommended combination for a full design → implement → review workflow:

1. `agent-isdd` — captures requirements, authors design, hands off
2. `agent-tdd` — research validation, task slicing, Red-Green-Refactor
3. `code-reviewer` — automated review at each Green→Refactor pause
4. `agent-nelly` — persistent memory across sessions (optional but improves context)
5. `agent-ux` — live spec canvas Artifacts (optional)
6. `plugin-harness` — routes handoffs between plugins (enhances multi-plugin flows)

Start with: `claude --print "/isdd Your feature description here"`

---

## Troubleshooting

### `plugin-harness` MCP server not appearing in `claude mcp list`

The MCP server launches via `python3 mcp_server/server.py` from the plugin root. Confirm
Python 3 is on your PATH:

```bash
python3 --version
```

If Python 3 is available but the server still does not appear, reinstall the plugin and
start a new Claude Code session:

```bash
claude plugin update plugin-harness@renfordn-plugins
```

Then restart (`claude` or reopen the desktop app) and run `claude mcp list` again.

### A plugin shows `Status: ✘ failed to load`

Check the error message from `claude plugin list`. Common causes:

- **Invalid manifest**: re-install the plugin (`claude plugin install <name>@renfordn-plugins`)
- **Missing dependency**: confirm all prerequisite plugins are installed
- **Stale cache**: remove the cached version and reinstall:

```bash
claude plugin update <name>@renfordn-plugins
```

### Re-publish / re-install procedure (1% failure path)

If a plugin install fails mid-way with a network or checksum error:

```bash
claude plugin install <name>@renfordn-plugins
```

The install command is idempotent — re-running it replaces a broken install cleanly.

---

## Human Verification Checklist

Run this checklist on a clean machine before marking the release complete:

- [ ] `claude plugin marketplace add renfordn/claude-plugins` succeeds
- [ ] All 6 plugins install without errors
- [ ] `claude plugin list` shows all 6 with `Status: ✔ enabled`
- [ ] `agent-nelly` smoke test returns a response (even "not yet captured")
- [ ] `agent-ux` and `agent-tdd` `claude plugin details` calls list their agents/skills
- [ ] `code-reviewer` smoke test returns tier descriptions
- [ ] `plugin-harness` appears in `claude mcp list`
- [ ] `/isdd-status` responds (no active workflow, on a fresh project)
- [ ] `/isdd Your feature` starts an ISDD workflow
