---
description: Redirect to agent-nelly for this project's central memory (view | migrate)
argument-hint: "[view | migrate] (default: view)"
allowed-tools: Bash(python3 *), Read
---

This project's **central** memory (Goal, architecture decisions, conventions, known issues,
active work) has moved to the `agent-nelly` plugin. `/isdd-memory` no longer owns or reads that
store directly — it only redirects, addressed via `agent-nelly:nelly-orchestrator` the same way
that subagent is called elsewhere in this plugin (see `commands/isdd.md`'s Availability Check
reference).

Requested action (default `view`): $ARGUMENTS

- **view** — Tell the user central memory now lives in agent-nelly and the equivalent command is
  `/nelly-memory view`; do not attempt to proxy or wrap it here. If a calling skill/orchestrator
  needs a memory brief programmatically rather than interactively, it should delegate to
  `agent-nelly:nelly-orchestrator` directly (gated by the Availability Check), not through this
  command.

- **migrate** — This project may still have pre-migration sdd-memory content on disk from before
  the memory move (leftover `PROJECT-MEMORY.md`, `MEMORY.md`, `TDD-MEMORY.md`,
  `scholar-memory.md`, `GLOBAL-MEMORY.md`, or similar files). To recover it:
  1. Resolve this project's sdd-memory directory:
     ```
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --path
     ```
  2. Tell the user to run `/nelly-memory import <that-resolved-path>`. `import` creates one
     agent-nelly memory entry per source file found in the directory; it is safe and idempotent
     to re-run without `--force` (existing entries are left alone), and `--force` overwrites
     entries that already exist if the user explicitly wants a refresh.
  3. Report which files (if any) were found at the resolved path so the user knows whether the
     import will do anything.
