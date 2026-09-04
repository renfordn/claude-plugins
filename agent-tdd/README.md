<!-- TDD-SKIP -->
# Agent TDD
![Tests](https://github.com/renfordn/agent-tdd/actions/workflows/tests.yml/badge.svg)

A token-efficient Design Spec orchestrator + strict Red-Green-Refactor TDD implementation for Claude Code.

**New in 0.1.8:** Accepts **Design Spec** (full requirements + design + validated research) from
agent-isdd. Validates research, slices into TDD-sized phases with Ralph Loops, assigns Risk Tiers,
and executes Red-Green-Refactor with optional test-author split for high-risk work — all in one
coordinated flow. Token-efficient: 30-70% reduction via caching, early escalation, and hard iteration
limits.

**Legacy support:** Still accepts **Slice Spec** from any orchestrator via `slice-spec` skill.
Both inputs work independently; neither agent assumes SDD's file formats.

## What's in this plugin

### Design Spec Orchestration (New in 0.1.8)

- **`design-spec`** skill — orchestrates full workflow: Design Spec → research validation → task slicing → Ralph Loops → Risk assignment → Readiness check → Red-Green-Refactor.
  Token-efficient: 18-28K tokens initial, 10-15K on resume (30-70% savings).
- **`research-validator`** agent — validates design.md's file touchpoints against research cache; escalates if gaps or contradictions.
- **`task-slicer`** agent — generates TDD-sized, dependency-ordered tasks.md from EARS behaviors, design touchpoints, and research findings.
- **`ralph-loops`** agent — three autonomous validation loops (slice size, dependency correctness, research traceability) with hard iteration limits (3/loop max).
- **`risk-assign`** agent — assigns Risk Tiers based on design risks, migrations, multi-module complexity, testability, and Ralph findings.
- **`readiness-check`** agent — 10-item deterministic checklist gate before Red-Green-Refactor.
- **`references/design-spec.schema.json`** — strict JSON schema for Design Spec validation.
- **`ORCHESTRATION.md`** — token-efficient orchestration design, caching strategy, resume flow.

### Legacy Slice Spec Support (0.1.7 and earlier)

- **`agent-TDD`** — implements one approved slice: Plan → Red → Green → (mandatory caller-driven review pause) → Refactor → Validate.
- **`test-author`** — for `high-risk`-tier slices only, writes just the failing Red test from the Slice Spec.
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
