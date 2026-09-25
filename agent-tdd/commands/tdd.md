---
description: Implement one behavior test-first with agent-TDD — failing test, minimal fix, independent review, refactor — with Red/Green verified by script
argument-hint: <behavior to add or bug to fix>
---

Implement `$ARGUMENTS` test-first.

1. **Slice Spec.** Use the `agent-tdd:slice-spec` skill to build a Slice Spec from `$ARGUMENTS`
   and the conversation. Ask the user only for what's genuinely missing — usually the acceptance
   criteria ("what observable behavior should a test pin down?"). One behavior per slice; if the
   request holds several, list them and do the first unless the user picks another.
2. **High-risk?** If the Risk Tier is `high-risk`, spawn `agent-tdd:test-author` first and pass
   its test file(s) and failure confirmation into the next spawn, per the slice-spec skill.
3. **Implement.** Spawn `agent-tdd:agent-TDD` with the Slice Spec. It stops at `green_pause`.
4. **Review.** Run an independent review of the files in its Review Request, per code-reviewer's
   INTEROP.md "Independent review" (spawn `code-reviewer:code-reviewer`, else
   `scripts/review_headless.sh`). Then resume agent-TDD with `SendMessage`, passing the verdict
   and findings. If no independent reviewer is available, say so and resume with the label
   `self-reviewed`.
5. **Report** to the user in a few lines: what changed, the SubagentStop line's
   `red=… green=…` evidence (say plainly if either isn't `verified`), the review outcome, and any
   follow-ups agent-TDD listed.
