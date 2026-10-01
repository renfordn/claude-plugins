<!-- TDD-SKIP -->
# Agent TDD
![Tests](https://github.com/renfordn/claude-plugins/actions/workflows/tests.yml/badge.svg)

A token-efficient Design Spec orchestrator + strict Red-Green-Refactor TDD implementation for Claude Code.

**Accepts two input modes**, both handled by the single `agent-TDD` agent:

- **Design Spec** (full requirements + design + validated research, e.g. from agent-isdd) —
  `agent-TDD` itself performs research validation, task slicing, Ralph Loops validation, Risk
  Tier assignment, and the Readiness Check as its own instructions (see its "Design Spec
  Workflow" section), then executes Red-Green-Refactor per slice — one coordinated spawn, no
  separate orchestration skill or sub-agents.
- **Slice Spec** (a single approved slice) — implements it directly: Plan → Red → Green →
  (mandatory caller-driven review pause) → Refactor → Validate.

**Removed in 0.1.12:** the earlier modular `design-spec` skill (five per-phase subagents). See
[`INTEROP.md`](INTEROP.md)'s "One implementation of this mode" and `CHANGELOG.md`.

## What's in this plugin

- **`/tdd <behavior>`** — the entry point: builds a Slice Spec from the conversation, spawns
  `agent-TDD`, runs an independent review at the Green pause, resumes it, and reports.
- **`scripts/tdd_check.py`** — runs the slice's test command for Red (must fail) and Green (must
  pass after a confirmed Red), logs each run in `<git dir>/agent-tdd/evidence.jsonl`, and prints a
  `TDD-EVIDENCE` token. The SubagentStop hook checks the report's tokens against that log and
  shows `red=verified green=verified`, or a warning when either is missing or invented.

- **`agent-TDD`** — implements a Slice Spec or a Design Spec (see above); Plan → Red → Green →
  (mandatory caller-driven review pause) → Refactor → Validate per slice.
- **`test-author`** — for `high-risk`-tier slices only, writes just the failing Red test from the
  Slice Spec.
- **`slice-spec`** skill — assembles and validates a Slice Spec before spawning either agent.
- **`test-budget`** skill — pre-flight on the target test file before planning new tests: flags bloat, stale tests, consolidation (parametrize) candidates, and unit tests better promoted to regression/e2e.
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

## Quickstart

```bash
claude plugin marketplace add renfordn/claude-plugins
claude plugin install agent-tdd@renfordn-plugins
```

`agent-tdd`'s subagent (`agent-tdd:agent-TDD`) is spawned with a Design Spec or Slice Spec either
by an orchestrating skill or by the plugin's `/tdd <behavior>` command for a single slice (see
"What's in this plugin" above).
The most common way to reach it is via `agent-isdd`'s `/isdd` workflow, which builds and hands
off a Design Spec automatically once Design is approved. Confirm it installed correctly with:

```bash
claude plugin details agent-tdd@renfordn-plugins
```

Expected: a component inventory listing the `agent-TDD` and `test-author` agents, the `/tdd` command, and the
`design-spec-direct` / `slice-spec` / `test-budget` skills. See
[docs/install-and-verify.md](../docs/install-and-verify.md) in this repo for the full
multi-plugin install/verify guide.

## Storage

Agent TDD stores workflow progress and session state in the Claude Code plugin data directory:

```
${CLAUDE_PLUGIN_DATA}/agent-tdd-state/
└── <project-slug>/
    └── tdd-progress.json      # TDD slice tracking and progress
```

`${CLAUDE_PLUGIN_DATA}` is set by Claude Code for hooks (see `hooks/path_resolution.py`); its exact location depends on how the plugin is installed.

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

CI (`.github/workflows/tests.yml`, at the repo root) runs it with `pytest` on every push and pull
request, alongside the other plugins.
# agent-tdd
