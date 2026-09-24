<!-- TDD-SKIP -->
# Agent Nelly

A general-purpose, project-aware memory orchestration plugin for Claude Code — goal-aware briefs, cross-project promotion, staleness detection, and consolidation, independent of any other plugin.

## Quickstart

```bash
claude plugin marketplace add renfordn/claude-plugins
claude plugin install agent-nelly@renfordn-plugins
```

Verify it loaded:

```bash
claude --print "Use the agent-nelly:agent-nelly subagent to fetch the project Intent. Just print the Intent line."
```

Expected: a short response naming the project Intent (or "not yet captured" on a fresh
project — that's correct). See
[docs/install-and-verify.md](../docs/install-and-verify.md) in this repo for the full
multi-plugin install/verify guide.

## Storage

Agent Nelly stores project and cross-project memory in the Claude Code plugin data directory:

```
${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/
├── <project-slug>/
│   ├── MEMORY.md              # Project memory index
│   ├── entries/               # Per-entry memory files
│   └── archive/               # Archived memory entries
└── global/
    ├── GLOBAL-MEMORY.md       # Cross-project memory index
    └── entries/               # Global memory files
```

Where `${CLAUDE_PLUGIN_DATA}` resolves to `~/.claude/plugins/data/agent-nelly/` when running in Claude Code.

### Sharing memory across machines and installs

`${CLAUDE_PLUGIN_DATA}` is local disk, separate for every plugin identity (`@inline` vs. a marketplace
install) and for every machine. Set the optional **`shared_memory_root`** plugin option (via `/config`)
to a directory every machine can see, ideally a git repo you pull and push. agent-nelly then keeps
`agent-nelly-memory/` there instead. Set the same value for agent-isdd. `hotspots.json` stays local,
and `nelly-index.json` is rebuilt from `entries/` at SessionStart. See
[`docs/shared-memory-root.md`](../docs/shared-memory-root.md) for setup, sync, and migrating existing
memory with `scripts/merge_plugin_data.py`.

## Using Agent Nelly from another plugin

Agent Nelly isn't specific to any one consumer — see [`INTEROP.md`](INTEROP.md) for the full
integration contract if you're building a different plugin and want to use its memory
subsystem.
