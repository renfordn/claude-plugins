# agent-isdd

An intent spec-driven development workflow for Claude Code and Claude Desktop. It owns the
**Planning** side: EARS-based **Requirements** and research-backed **Design**. Task slicing
and implementation are owned by separate sibling plugins:

- **[agent-tdd](https://github.com/renfordn/agent-tdd)** — task slicing (validate research,
  slice into TDD-sized phases, assign Risk Tiers), then strict Red-Green-Refactor TDD execution.
- **[code-reviewer](https://github.com/renfordn/code-reviewer)** — the mandatory review gate,
  invoked by whichever caller drives implementation.
- **[agent-nelly](https://github.com/renfordn/agent-nelly)** — goal-aware memory, briefs,
  cross-feature file-level caching, and cross-project promotion.

`agent-isdd` never drives task slicing, never drives the TDD loop, never invokes the review
gate, and never owns a memory subsystem beyond its own per-feature `spec/` artifacts. It produces
a **Design Spec** at the Design → Implementation boundary and stops.

## Quickstart

```bash
claude plugin marketplace add renfordn/claude-plugins
claude plugin install agent-isdd@renfordn-plugins
```

Then, in a Claude Code session in your project:

```
/isdd Your feature description here
```

This starts (or continues) an EARS-requirements → design workflow, interviewing you where the
input is ambiguous. `/isdd-status` shows the current phase without starting anything. See
[docs/install-and-verify.md](../docs/install-and-verify.md) in this repo for the full
multi-plugin install/verify guide, including installing `agent-tdd`/`code-reviewer` so a Design
Spec has somewhere to hand off to.

## Why this plugin exists

`agent-isdd` is the successor to the `sdd` plugin, which originally bundled requirements,
design, tasks, TDD implementation, code review, and memory into a single, oversized plugin.
Implementation, review, and memory were extracted first (`agent-tdd`, `code-reviewer`,
`agent-nelly`); this plugin is the last piece — the planning-only remainder of `sdd`, trimmed of
everything the siblings now own. See `CHANGELOG.md` for the full port/trim/drop breakdown.

## Workflow

Phase-gated, always in order: `Requirements` → `Design` → `Implementation` (task slicing +
Red-Green-Refactor, owned by agent-tdd). Each phase has a hard completion checklist (EARS format,
no unresolved ambiguity, explicit interfaces/touchpoints, research validated) before handoff.
State lives in `${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/spec/<feature-slug>/` (see Storage section below).

**Intent:** Explicit, durable artifact (markdown). Captured at start, hash-validated on resume.
Drives Requirements, grounds Design, referenced by task slices.

**Research:** Unified pass during Design via `research-consolidator` (one pass, dual output for
Design + Tasks). Cached in `research/cache.md`. Agent-tdd reuses cache, skips re-research unless
invalid. Cross-feature file caching via agent-nelly for 70-80% cache hit rate on related features.

## Commands

- `/isdd` — start or continue the workflow for a feature.
- `/isdd-status` — show current phase, status, blockers, next action (read-only).
- `/isdd-continue` — force-continue from the current phase.
- `/isdd-rewind` — rewind to an earlier phase (Requirements | Design).
- `/isdd-init` — first-run onboarding for a new project.
- `/isdd-memory` — view or migrate this project's central memory (redirects to `agent-nelly`).

## Storage

Agent-isdd stores per-feature spec artifacts (requirements, design, tasks) in the Claude Code plugin data directory:

```
${CLAUDE_PLUGIN_DATA}/sdd-memory/
└── <project-slug>/
    └── spec/
        └── <feature-slug>/
            ├── workflow-state.md       # Phase, status, blockers
            ├── workflow-state.json     # Machine-readable state
            ├── requirements/           # Approved requirements
            ├── design/                 # Design + research basis
            ├── tasks/                  # TDD-sized task slices
            └── recap/                  # Summary, risks, handoff
```

**Note:** sdd-memory is shared between agent-isdd and plugin-harness via symlink coordination for workflow state access.

Where `${CLAUDE_PLUGIN_DATA}` resolves to `~/.claude/plugins/data/agent-isdd/` when running in Claude Code
under a single plugin identity. Claude Code can load the same plugin under more than one identity in
the same install — e.g. a monorepo checkout as `agent-isdd@inline` alongside a marketplace install as
`agent-isdd@<marketplace>` — and each identity gets its own `${CLAUDE_PLUGIN_DATA}` (e.g.
`.../data/agent-isdd-inline/` vs. `.../data/agent-isdd/`). See `hooks/path_resolution.py`'s docstring
for the full writeup.

### Debugging: never invoke `hooks/*.py` directly

Do not run any `hooks/*.py` script by hand from a plain shell, or via a Bash tool call, during
interactive session work (e.g. `python3 hooks/sdd_memory.py --spec-path ...` to "just check
where state lives"). `${CLAUDE_PLUGIN_DATA}` is only injected into subprocesses Claude Code
itself spawns for a *registered* hook — a manual invocation never gets it, so every such script
silently falls back to a guessed, non-suffixed path (`~/.claude/plugins/data/agent-isdd/...`)
that may not match whichever plugin identity's hooks are actually registered this session. Any
state scaffolded or read that way can silently diverge from what the real hooks — including the
gates in `hooks/commit_audit_gate.py` and `hooks/design_spec_gate.py` — see, and a
discovery-based gate hook that finds nothing at its resolved path falls through as "no active
workflow" rather than erroring, which for `design_spec_gate.py` means a spawn silently proceeds
ungated rather than being denied.

If you need to inspect or repair this project's actual SDD state, do it through a real hook
invocation (e.g. `/isdd-status`, which reads state the same way `hooks/session_start.py` does)
or a skill that only ever calls into these hooks the way `hooks.json` does — never a bare
interactive call to a script under `hooks/`.

## Handoff contract

At the end of Design, once Design is approved and implementation is requested, `agent-isdd`
builds a **Design Spec** from `requirements.md`, `design.md`, `research/cache.md`, and
pre-fetched file summaries, then spawns `agent-tdd` for research validation, task slicing,
and implementation. This is a one-directional handoff — `agent-isdd` does not resume or drive
`agent-tdd` past the initial spawn. See `INTEROP.md` for the exact Design Spec contract and
agent-tdd's new responsibilities (research validation, slicing, Ralph Loops).
