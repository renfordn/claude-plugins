<!-- TDD-SKIP -->
# Interoperability: Integrating Code Reviewer Into Another Plugin

Code Reviewer is a general-purpose review skill for Claude Code. It is not specific to
spec-driven-development (SDD) or to `agent-tdd` — SDD is simply its first real consumer. This
document is the contract for any *other* plugin author (or orchestrating skill) who wants to use
it.

## How to invoke it

Invoke the `code-reviewer` skill directly (it is a skill, not a Task-tool subagent — see
README's "Why this is a skill, not an agent"). Tell it:

- **Mode** — `direct-review`, `review-improve`, or `pre-commit` (see SKILL.md's Invocation
  Modes).
- **Scope** — the file set or diff to review. For `review-improve`, this is the files an
  implementer agent (e.g. `agent-tdd`'s `agent-TDD`) named in its pre-refactor handoff.
- **Review state directory** (optional) — a path where you want `REVIEW-STATE.md` /
  `REVIEW-HISTORY.md` persisted across passes. Omit it for a single ephemeral pass with no
  persistence; see SKILL.md's "Review State" section for exactly what changes when you do.
- **`phase_state`** (optional) — pass this only if your workflow has a compact phase token of its
  own (e.g. `agent-isdd`'s `Design`, or `TDD:green`) to attribute this review pass to. This is the
  one thing that unlocks `agent-ux:ux-agent` delegation for the review dashboard, if it's
  installed — see SKILL.md's "Visual Review" section. Omit it entirely for a standalone or
  pre-commit pass with no surrounding workflow; `code-reviewer` never invents one, and its own
  behavior is identical either way except for which tool renders the above-threshold dashboard.

## Pairing with an implementer agent (e.g. `agent-tdd`)

If your implementer agent stops for a mandatory review pause (as `agent-tdd`'s `agent-TDD`
does), you are the one driving both sides — no subagent in this harness can invoke another
subagent, so the calling skill in the main thread must run this review and then resume the
implementer itself:

1. Run `code-reviewer` in `review-improve` mode, scoped to the files the implementer named.
2. If a finding's `workflow_action` is `pause_for_review`, resolve `code-reviewer`'s single
   clarifying question with the user yourself before proceeding.
3. Do not resume the implementer into Refactor while any finding is `needs_detailed_review` in
   your review-state directory's `REVIEW-STATE.md` (if you supplied one), or otherwise unresolved
   for this pass.
4. Resume the implementer once clear, passing along whether/what review found.

## What you get back

Findings are rendered via `ReportFindings` (always) and, above a 5-finding/1-file threshold, an
additional review-dashboard — an `Artifact` this skill opens directly by default, or one rendered
by `agent-ux:ux-agent` instead when you supplied a `phase_state` and it's installed (see "How to
invoke it" above). Either way it's the same dashboard content; there is no separate report object
to parse beyond what `ReportFindings`/the dashboard already show — `code-reviewer` does not return
a machine-readable summary distinct from its rendered output.

## Cross-project or cross-feature memory

If your ecosystem has a separate memory plugin (e.g. `agent-nelly`) for durable, higher-level
facts, `code-reviewer` will never write its own per-file/per-pass records there — that boundary
is a guardrail in its own SKILL.md, not something you need to enforce from the caller side. A
recurring convention violation worth remembering across features is something *you* decide to
write to that memory tier, separately from this skill's review-state directory.
