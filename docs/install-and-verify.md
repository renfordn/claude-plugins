# Install and Verify — Claude Plugin Collection

This guide walks through installing all 7 plugins from the `renfordn-plugins` marketplace,
verifying they are working, and troubleshooting common issues. All plugins can be used
standalone or in any combination.

## Prerequisites

- Claude Code (claude CLI) installed and authenticated
- Internet access for plugin download
- For `agent-cache-plugin` only: Node.js ≥ 18 and a working C++ toolchain for native
  `better-sqlite3` compilation (see [Troubleshooting](#troubleshooting) if this step fails)

---

## Install All 7 Plugins

Install in dependency order (the first five are independent; `agent-cache-plugin` and
`plugin-orchestrator` should come last):

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
claude plugin install agent-cache-plugin@renfordn-plugins
```

```bash
claude plugin install plugin-orchestrator@renfordn-plugins
```

---

## Verify Install

After installing, confirm all plugins are present and enabled:

```bash
claude plugin list
```

Expected output: all 7 plugins listed with `Status: ✔ enabled`.

---

## Per-Plugin Smoke Verification

Run these one-liners to confirm each plugin is loading correctly. Each prints a short
confirmation (or exits 0) if the plugin is wired up properly.

### agent-nelly

```bash
claude --print "Use agent-nelly:nelly-orchestrator to fetch the project Intent. Just print the Intent line."
```

Expected: a short response mentioning the project Intent (may be "not yet captured" on a
fresh machine — that is correct).

### agent-ux

```bash
claude --print "/ux-agent help"
```

Expected: a brief description of the agent-ux skill.

### agent-tdd

```bash
claude --print "/tdd help"
```

Expected: a brief description of the TDD workflow.

### agent-isdd

```bash
claude --print "/isdd help"
```

Expected: a brief description of the ISDD / spec-driven-development workflow.

### code-reviewer

```bash
claude --print "/code-review help"
```

Expected: a brief description of the code-reviewer skill with the four review levels.

### agent-cache-plugin

```bash
claude plugin exec agent-cache-plugin -- status
```

Expected: exit code 0 and a status summary (cache may be empty on first run — that is
correct).

### plugin-orchestrator

The plugin-orchestrator MCP server starts automatically on session launch once installed.
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
| Cache agent context | `agent-cache-plugin` |
| Full orchestrated workflow | All 7 |

---

## Combination Usage

The recommended combination for a full design → implement → review workflow:

1. `agent-isdd` — captures requirements, authors design, hands off
2. `agent-tdd` — research validation, task slicing, Red-Green-Refactor
3. `code-reviewer` — automated review at each Green→Refactor pause
4. `agent-nelly` — persistent memory across sessions (optional but improves context)
5. `agent-ux` — live spec canvas Artifacts (optional)
6. `agent-cache-plugin` — context caching for long workflows (optional)
7. `plugin-orchestrator` — routes handoffs between plugins (enhances multi-plugin flows)

Start with: `claude --print "/isdd Your feature description here"`

---

## Troubleshooting

### `agent-cache-plugin` — `better-sqlite3` native build failure

`better-sqlite3` requires a C++ toolchain and Python 3 to compile its native addon.

**macOS:**
```bash
xcode-select --install
```
Then re-install the plugin.

**Ubuntu / Debian:**
```bash
sudo apt-get install -y build-essential python3
```
Then re-install the plugin.

**Verify the build succeeded:**
```bash
claude plugin exec agent-cache-plugin -- status
```

If the build still fails, check that your Node.js version is ≥ 18 (`node --version`) and
that npm can reach the internet to download `better-sqlite3` binaries for your platform.

### `plugin-orchestrator` MCP server not appearing in `claude mcp list`

The MCP server launches via `python3 mcp_server/server.py` from the plugin root. Confirm
Python 3 is on your PATH:

```bash
python3 --version
```

If Python 3 is available but the server still does not appear, reinstall the plugin and
start a new Claude Code session:

```bash
claude plugin update plugin-orchestrator@renfordn-plugins
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

- [ ] All 7 plugins install without errors
- [ ] `claude plugin list` shows all 7 with `Status: ✔ enabled`
- [ ] `agent-nelly` smoke test returns a response (even "not yet captured")
- [ ] `code-reviewer` smoke test returns level descriptions
- [ ] `agent-cache-plugin` status exits 0
- [ ] `plugin-orchestrator` appears in `claude mcp list`
- [ ] `/isdd Your feature` starts an ISDD workflow
- [ ] `/tdd` and `/code-review` respond with help text
