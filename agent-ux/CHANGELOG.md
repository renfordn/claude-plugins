<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.1] - 2026-08-16

- Doc-and-model-accuracy pass, cross-checked directly against `agent-tdd`'s and `code-reviewer`'s
  own repos rather than carrying over unverified assumptions from `agent-isdd`'s docs:
  - `README.md`: replaced the stale "no event contract yet" paragraph (left over from before
    `INTEROP.md` was written in this same 0.1.0 release) with an accurate statement — the
    envelope contract is defined, `agent-isdd` is the one live caller, `agent-tdd`/`code-reviewer`
    are named as prospective callers but don't integrate yet.
  - `INTEROP.md`'s "`caller`-keyed rendering rules": corrected the TDD-stage exclusion to
    `agent-tdd`'s real six stages (Plan → Red → Green → Review → Refactor → Validate, read from
    `agent-tdd/agents/agent-TDD.md`) instead of the previously-assumed, confirmed-incomplete
    three-stage set. Deeper fix: the exclusion was keyed on `caller: agent-tdd`, which can never
    be a real value — `agent-TDD` (the subagent) has no `Agent` tool and can never be the literal
    sender of a `ux-agent` envelope (per `agent-tdd`'s own "harness constraint" section). Re-keyed
    the exclusion on `phase_state` matching `TDD:<stage>` instead, and removed `agent-tdd` from
    the `caller` type in the envelope-shape table with an explanatory note. `agents/ux-agent.md`'s
    dispatch logic and the `tdd-stage-exclusion.md`/`EXPECTED-OUTPUTS.md` fixtures updated to
    match (fixture's `caller` changed from the impossible `agent-tdd` to `agent-isdd`, the
    orchestrator that would actually send it). `agent-tdd/INTEROP.md` gained a new section
    documenting this recipe for whichever orchestrator wants to adopt it.
  - `references/ux-conventions.md`'s "Review dashboard (Artifact)" section: corrected the false
    claim that the dashboard is "used only by `doc-consistency-auditor`" (that skill's own
    `SKILL.md` explicitly opts out of it) and marked the 5-finding/1-file threshold as
    intentionally mirroring `code-reviewer`'s own canonical definition rather than an
    independently-chosen value.
  - `agents/ux-agent.md`: cross-referenced the same threshold back to its canonical source instead
    of stating it as this plugin's own independent choice.
- `INTEROP.md`'s `code-reviewer` entry flipped from "no integration today" to real, optional
  integration: `code-reviewer` (its own new `[Unreleased]` release) now delegates its
  review-dashboard rendering to a `review_threshold` envelope when a caller supplies a
  `phase_state` and `agent-ux:ux-agent` is installed, falling back to its own direct Artifact
  otherwise. No changes needed on this plugin's side — `code-reviewer` was always a valid
  `caller`, unlike `agent-tdd`.

## [0.1.0] - 2026-08-13

- Extracted from `agent-isdd`'s `ux-agent` into a standalone plugin, no behavior change. Ports
  `agents/ux-agent.md` and `references/ux-conventions.md` verbatim aside from the
  plugin-qualified agent name and description-scope wording.
- No event contract yet — this release is pure packaging; the cross-plugin envelope
  (`INTEROP.md`) is a follow-up phase.
