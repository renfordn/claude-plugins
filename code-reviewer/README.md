<!-- TDD-SKIP -->
# Code Reviewer

A standalone code review skill for Claude Code — evidence-tiered findings, a required decision
model, combined-findings anti-blur rules, and a single-clarifying-question resume contract,
independent of any other plugin.

It was extracted from `spec-driven-development`'s internal `code-reviewer` skill, the same way
`agent-nelly` was extracted from SDD's memory system and `agent-tdd` was extracted from SDD's
implementation agents. SDD is its first consumer, not its only one.

## Why this is a skill, not an agent

Unlike `agent-tdd`'s `agent-TDD`/`test-author` (Task-tool subagents run in isolated context),
`code-reviewer` is invoked as a plain skill in the main thread. That's deliberate: it needs to
call `ReportFindings` and open a review-dashboard `Artifact` in the *same turn* it runs in, and
those are host-native tools a subagent can't reliably reach the way the calling skill can. It's
also why this plugin doesn't need any `ux-agent`-style delegation for its own dashboard rendering
— it owns that directly.

## Using it with `agent-tdd`

`agent-tdd`'s `agent-TDD` agent always pauses after Green for a mandatory caller-driven review
(see [`agent-tdd`'s INTEROP.md](../agent-tdd/INTEROP.md)). This skill is a natural fit for that
pause — run it in `review-improve` mode, scoped to the files `agent-TDD` named, then resume
`agent-TDD` with the outcome. Neither plugin hard-depends on the other; you can use `agent-tdd`
with a different reviewer, or use this skill with a different (or no) TDD implementer.

## Review state is opt-in

This skill has no memory location of its own. Pass it a review-state directory if you want
per-file state and history persisted across passes (see `references/REVIEW-STATE.md.template`
and `references/REVIEW-HISTORY.md.template`); omit it and the skill stays ephemeral for a single
pass, applying the same evidence-tier and decision rules without writing anywhere.

## Installation

_Installation instructions will be added once the plugin is published to a marketplace._

## Using Code Reviewer from another plugin

See [`INTEROP.md`](INTEROP.md) for the full integration contract if you're building a different
plugin and want to call this skill.
# code-reviewer
