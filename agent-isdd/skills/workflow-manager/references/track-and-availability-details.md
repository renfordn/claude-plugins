# Track Field Contract & Availability Check — full details

## Track Field Contract

- Source of truth: `workflow-state.md`'s `Track` field (`Fast | Standard`), mirrored to
  `workflow-state.json`'s `track`. Absent/unset means `Standard` — no migration needed for
  features started before this field existed.
- Set once, at Start, by `spec-driven-development`'s Fast Track classification (see its own
  SKILL.md) — `workflow-manager` never sets or classifies `Track` itself, only scaffolds and
  persists whatever `spec-driven-development` decided, same division of responsibility as the
  `Goal` field.
- Can flip `Fast` → `Standard` mid-flight via the Fast Track escape hatch (`requirements-agent`
  or `design-author` reporting the change is bigger than assumed); never the reverse — a
  workflow that started `Standard` stays `Standard`.
- `Track: Fast` means no `tasks/tasks.md` is ever scaffolded or written for this feature (see
  Scaffolding in the main SKILL.md) and the Implementation Handoff sends a Slice Spec, not a
  Design Spec — this changes what `spec-driven-development` does at handoff, not anything
  `workflow-manager` itself evaluates in Phase Pass/Fail Rules (Requirements and Design gates are
  identical either way).

## Availability Check — self-healing on a stale cache

**Self-healing on a stale cache (2026-09-16).** The agent-types listing (checked at
`before-requirements` and `before-continue` — see the main SKILL.md's "Availability Check") is a
point-in-time snapshot captured at session start — it can be stale relative to the actual
installed plugin (a plugin updated or removed after this session began still shows its old
state). A hook cannot backstop this: `agent-nelly:agent-nelly` failing to spawn because the type
doesn't actually resolve is a routing failure that occurs before the model's tool call is even
considered an invocation attempt, so no `PreToolUse`/`PostToolUse`/`PostToolUseFailure` hook ever
fires for it (confirmed against Claude Code's own hooks documentation and live-tested — see the
removed `hooks/nelly_spawn_failure.py`, which was built as exactly this backstop and never once
fired). The only place that genuinely sees this failure is the calling skill itself, in the same
turn it attempted the spawn — the tool call returns an "Agent type not found" error directly into
this skill's own context. When that happens for `agent-nelly:agent-nelly` specifically,
immediately correct `agent_nelly_available` to `false` in `workflow-state.json` before
proceeding, rather than leaving the stale cached `true` for a later step to trust and fail
against again.
