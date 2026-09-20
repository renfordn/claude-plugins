# Agent Frontmatter: `model:` Field Semantics

This formalizes the meaning of the `model:` field in every agent's YAML frontmatter across all
plugins in this repo. It is additive documentation — it does not require changing any existing
agent's already-shipped frontmatter value. Use it as the reference when writing a *new* agent, or
when deciding whether an existing agent's `model:` value should change (a deliberate choice made
by that agent's own maintainer, not a blanket migration).

## Accepted values

| Value | Meaning |
|-------|---------|
| `inherit` | The agent always runs at whatever model tier the caller/session is already using — it has no fixed opinion of its own. This is the right default for most agents: implementers, reviewers, and any agent whose complexity varies slice-to-slice. |
| `haiku` | The agent always runs at the Haiku tier, regardless of what tier the caller or session is otherwise using. Reserve this for narrowly-scoped, low-complexity agents (e.g. rendering a UI event, formatting output) where stronger reasoning would be pure token waste. |
| `sonnet` | The agent always runs at the Sonnet tier. Typical for agents that need real reasoning but not the deepest tier — plan review, research consolidation, spec review. |
| `opus` | The agent always runs at the Opus tier. Reserve for agents whose entire job is complex, high-stakes reasoning (e.g. a tier-3 reviewer making a final go/no-go call on a risky migration). |
| `fable-5-1` | The agent always runs on the `fable-5-1` model specifically (a named model outside the standard Haiku/Sonnet/Opus tier ladder), for agents pinned to that model's specific behavior. |

## Key property: fixed tiers are always fixed

Every value **other than** `inherit` means the agent **always** uses that model, every time it's
spawned — it does not matter what tier the calling session, caller agent, or workflow orchestrator
is otherwise running at. A `model: haiku` agent runs at Haiku even if it's spawned from an
Opus-tier session; a `model: opus` agent runs at Opus even inside an otherwise Haiku-tier workflow.
This is a *static, per-agent* declaration, not a suggestion the caller can override from outside.

This is distinct from the *per-slice* `modelTier` field in agent-TDD's Slice Spec (see
[`agent-tdd/INTEROP.md`](../agent-tdd/INTEROP.md)) and from `plugin-orchestrator`'s
`modelPreference` capability metadata (`min_tier`/`preferred_tier`) — those are advisory,
per-invocation signals a caller or orchestrator can use to pick a tier at spawn time. The
frontmatter `model:` field, by contrast, is the agent definition's own fixed declaration and takes
precedence for any agent that isn't `inherit`.

## Worked frontmatter examples

A narrowly-scoped rendering agent, fixed at Haiku:

```markdown
---
name: ux-agent
description: Render progress UI events for a workflow phase.
model: haiku
---
```

A general-purpose implementer that should track the caller's own tier:

```markdown
---
name: agent-TDD
description: Standalone TDD implementation agent...
model: inherit
---
```

A deep-reasoning reviewer, fixed at Opus regardless of caller tier:

```markdown
---
name: plan-reviewer-tier3
description: Final-tier plan review for high-risk migrations.
model: opus
tools: [Read, Grep, Glob, Bash]
---
```

## Guidance for new agents

- Default to `inherit` unless there's a specific reason to pin a tier.
- Pin `haiku` only for genuinely narrow, low-complexity agents — pinning it too aggressively to
  "save tokens" on an agent that occasionally needs real reasoning just produces bad output that
  gets escalated anyway (see `agent-tdd/references/escalation-paths.md`'s Model Escalation path).
- Pin `sonnet` or `opus` only when the agent's entire purpose is reasoning-heavy and the cost is
  justified regardless of caller context.
- `fable-5-1` is reserved for agents specifically validated against that model's behavior — don't
  use it as a stand-in for "some other tier."
