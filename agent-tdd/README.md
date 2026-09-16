<!-- TDD-SKIP -->
# Agent TDD
![Tests](https://github.com/renfordn/agent-tdd/actions/workflows/tests.yml/badge.svg)

A token-efficient Design Spec orchestrator + strict Red-Green-Refactor TDD implementation for Claude Code.

**Accepts two input modes**, both handled by the single `agent-TDD` agent:

- **Design Spec** (full requirements + design + validated research, e.g. from agent-isdd) —
  `agent-TDD` itself performs research validation, task slicing, Ralph Loops validation, Risk
  Tier assignment, and the Readiness Check as its own instructions (see its "Design Spec
  Workflow" section), then executes Red-Green-Refactor per slice — one coordinated spawn, no
  separate orchestration skill or sub-agents.
- **Slice Spec** (a single approved slice) — implements it directly: Plan → Red → Green →
  (mandatory caller-driven review pause) → Refactor → Validate.

**Removed in 0.1.12:** the earlier modular `design-spec` skill (five separate subagents —
`research-validator`, `task-slicer`, `ralph-loops`, `risk-assign`, `readiness-check` — each
performing one phase) was never the path any real caller used; `agent-isdd` always spawned
`agent-TDD` directly with a Design Spec. It emitted its own incompatible escalation-marker
vocabulary that no caller's hooks recognized, and had drifted out of sync with the inline path it
duplicated. Retired rather than kept as a documented-but-dead alternative — see `CHANGELOG.md`.

## What's in this plugin

- **`agent-TDD`** — implements a Slice Spec or a Design Spec (see above); Plan → Red → Green →
  (mandatory caller-driven review pause) → Refactor → Validate per slice.
- **`test-author`** — for `high-risk`-tier slices only, writes just the failing Red test from the
  Slice Spec.
- **`slice-spec`** skill — assembles and validates a Slice Spec before spawning either agent.
- **`references/slice-spec.schema.json`** — machine-checkable JSON Schema for Slice Spec.

### Build Tools

- **`scripts/bump_version.py`** — moves `CHANGELOG.md`'s `[Unreleased]` entries under a new version heading and updates `.claude-plugin/plugin.json`'s version to match.

## Why not `code-reviewer` too

The mandatory review step between Green and Refactor is real in this plugin — `agent-TDD` always
pauses for it unless the caller explicitly opts out. But `code-reviewer` itself wasn't bundled
in: it's useful as a general-purpose reviewer beyond just gating TDD slices (SDD invokes it
standalone, outside any TDD slice, today). Bundling it here would make callers who just want a
reviewer pull in the whole TDD subsystem. It now ships as its own standalone
[`code-reviewer`](../code-reviewer) plugin that this one and others can depend on, the same way
SDD depends on this one — see that plugin's [`INTEROP.md`](../code-reviewer/INTEROP.md) for
exactly how to pair it with `agent-TDD`'s review pause.

"Caller-driven review" still isn't required to be `code-reviewer` specifically — it can be
anything the caller has available: an agent, a lint/static-analysis pass, or a human.

## Installation

_Installation instructions will be added once the plugin is published to a marketplace._

## Storage

Agent TDD stores workflow progress and session state in the Claude Code plugin data directory:

```
${CLAUDE_PLUGIN_DATA}/agent-tdd-state/
└── <project-slug>/
    ├── tdd-progress.json      # TDD slice tracking and progress
    └── last-stop.json         # Session boundary marker
```

Where `${CLAUDE_PLUGIN_DATA}` resolves to `~/.claude/plugins/data/agent-tdd/` when running in Claude Code.

## Using Agent TDD from another plugin

Agent TDD isn't specific to any one consumer — see [`INTEROP.md`](INTEROP.md) for the full
integration contract if you're building a different plugin and want to use it too.

## Testing this repo

`tests/` holds a stdlib-only Python `unittest` suite (no dependencies beyond Python 3) covering
version sync between `CHANGELOG.md` and `.claude-plugin/plugin.json`, doc consistency between the
agent files and `INTEROP.md`, the Slice Spec JSON Schema, and `scripts/bump_version.py`. Run it
with:

```
python3 -m unittest discover -s tests -p "test_*.py" -v
```

It also runs on every push and pull request, across a Python 3.9-3.12 matrix, via
[`.github/workflows/tests.yml`](.github/workflows/tests.yml).
# agent-tdd
