# Tasks: agent-ux plugin extraction

## Phase Status

- Current Phase: Tasks
- State: Ready For Implementation (Phases 1-5, scoped to `agent-ux` and `agent-isdd`'s own
  adoption) — Design's Open Question on agent-tdd/code-reviewer adoption is reclassified as a
  sibling-plugin follow-up (see below), not a blocker on this plan. Design's semver-policy
  Open Question is resolved inline in Phase 2, step 4.
- Last Updated: 2026-08-12

## Execution Rules

- Preserve approved requirements and design intent (pull-over-push envelope; soft dependency;
  checkpoint-only gating; haiku-pinned model).
- Keep slices to one behavior change and/or one file or module touched if possible.
- Tests first where implementation follows — for a prompt-defined plugin, "test" means a recorded
  example envelope plus a manual walkthrough that produces the expected output lines, not code
  unit tests.
- Refactor only after green.
- Pause on ambiguity, conflicting constraints, weak testability, high-risk migration, or oversized
  tasks.
- Tag each task's Risk Tier (`standard` or `high-risk`) per design.md's Risks And Tradeoffs
  section.

## Phase 1: Scaffold the agent-ux plugin repo

### Objective

Stand up a new `agent-ux` repo with the plugin skeleton and a verbatim port of the existing
rendering logic, with no behavior change yet — this phase is pure extraction, not redesign.

### Risk Tier

- `standard` — mechanical port, no new logic, no cross-plugin contract yet.

### Prerequisites

- None. Independent of the two Design-phase Open Questions — this phase does not require
  agent-tdd/code-reviewer buy-in to exist.

### Ordered Steps

1. Create `agent-ux` repo with `.claude-plugin/plugin.json`, `LICENSE`, `README.md`,
   `CHANGELOG.md` (0.1.0 entry: "extracted from agent-isdd's ux-agent, no behavior change").
2. Port `agent-isdd/agents/ux-agent.md` into `agent-ux/agents/ux-agent.md` unchanged except the
   plugin-qualified name (`agent-ux:ux-agent`) and any `agent-isdd`-specific wording in its
   description.
3. Port `agent-isdd/references/ux-conventions.md` into `agent-ux/references/ux-conventions.md`
   unchanged.
4. Write `agent-ux/README.md` stating scope: rendering mechanics only, consumed by sibling
   plugins via the event contract defined in Phase 2.

### Test Intent

- Add or update:
  - None (no envelope contract exists yet — this phase's correctness is "diff against source is
    a pure rename/copy").
- Expected failing behavior:
  - N/A — nothing consumes this repo yet, so there is no "red" state to define.

### Validation Target

- Command:
  - Manual diff: `diff agent-isdd/agents/ux-agent.md agent-ux/agents/ux-agent.md` shows only the
    plugin-qualifier and description-scope edits, nothing else.
- Evidence:
  - Zero unintended behavioral drift from the source file.

### Unlocks

- Enables:
  - Phase 2 (event contract) has a concrete agent definition to shape the envelope schema
    against.

### Blockers Or Escalation

- [ ] None.

## Phase 2: Define and document the event envelope contract

### Objective

Write `agent-ux/INTEROP.md` defining the versioned event envelope (`caller`, `event_type`,
`phase_state`, `delta`, `artifact_path`) and the per-`event_type` delta shapes from design.md,
including the pull-over-push invariant and the unavailability/fallback contract every caller will
reference.

### Risk Tier

- `high-risk` — this is the core cross-plugin contract; a mistake here is expensive to change
  once `agent-tdd`/`code-reviewer` adopt it (design.md's stated risk: "three callers drift on
  what checkpoint means").

### Prerequisites

- Phase 1 complete (concrete `ux-agent.md` to validate the schema against).

### Ordered Steps

1. Write the envelope schema and the five `event_type` delta shapes verbatim from design.md's
   Data Contracts And Interfaces section.
2. Write the unavailability/fallback contract once, generically (not `agent-isdd`-specific), so
   every caller's own `INTEROP.md` can reference it by name rather than restate it.
3. Write the `caller`-keyed rule for TDD-stage chapter exclusion explicitly, flagged as "carried
   over from `agent-isdd`'s prior documentation of `agent-tdd`'s behavior, not independently
   confirmed" — matches design.md's Research Basis caveat.
4. State the contract's semver policy (resolves Design's second Open Question) or explicitly
   defer it with a stated interim policy (e.g. "unversioned, breaking changes require updating
   all known callers in the same change") if semver is deferred.

### Test Intent

- Add or update:
  - `agent-ux/references/example-envelopes/` — one recorded example per `event_type`, mirroring
    `agent-isdd/references/example-feature/`'s pattern.
- Expected failing behavior:
  - Before this phase, no machine- or human-checkable definition of "delta" exists, so a reviewer
    cannot currently catch a caller passing a full artifact instead of a delta.

### Validation Target

- Command:
  - Manual review: each recorded example envelope's `delta` field checked against the schema by
    hand (no schema validator planned — this is a prompt contract, not code).
- Evidence:
  - All 5 example envelopes conform; the `breadcrumb_only` example is confirmed to carry no
    fields beyond `phase_state`.

### Unlocks

- Enables:
  - Phase 3 (wire `ux-agent.md` to read the envelope fields) and Phase 5 (token-cost validation)
    both depend on this schema being fixed.

### Blockers Or Escalation

- [ ] Design's Open Question on semver policy must be explicitly resolved (even if the
      resolution is "defer, unversioned") before this phase can close — it cannot be silently
      skipped.

## Phase 3: Update ux-agent.md to consume the envelope

### Objective

Modify `agent-ux/agents/ux-agent.md` so its instructions are keyed off the envelope fields
(`caller`, `event_type`, `delta`, `artifact_path`) defined in Phase 2, replacing the current
inline-narrated-by-caller instruction style with an explicit per-`event_type` dispatch, including
the "read `artifact_path` on demand" pull behavior for `review_threshold`.

### Risk Tier

- `high-risk` — behavior-affecting change to the agent that must not regress any of the four
  existing gating thresholds (checkpoint-only artifact publishing, >5-findings/>1-file dashboard
  threshold, phase-transition-only chapter marking, confirmed-out-of-scope-only task spawning).

### Prerequisites

- Phase 2 complete.

### Ordered Steps

1. Add per-`event_type` dispatch section to `ux-agent.md`, one subsection per type, each stating
   which envelope fields it reads and which existing gating rule still applies unchanged.
2. Implement the `review_threshold` pull behavior explicitly: agent-ux reads `artifact_path`
   itself for finding evidence/diffs only after confirming the >5/>1-file threshold from the
   delta's `finding_count`/`files_touched` — never before.
3. Implement the envelope-misuse guardrail: if `delta` exceeds the expected shape for its
   `event_type` (e.g. a full document body where only `section_body` for one named section is
   expected), truncate and report the mismatch in one line rather than rendering it.
4. Update the "Return to the caller" section to confirm output lines are unchanged in shape from
   today's baseline (breadcrumb always first, one line per action taken).

### Test Intent

- Add or update:
  - Manual walkthrough script (not committed code) exercising all 5 event types against the
    Phase 2 example envelopes.
- Expected failing behavior:
  - Before this phase, `ux-agent.md` has no defined behavior for a `caller` field or a
    malformed/misused `delta` — passing either today has undefined behavior.

### Validation Target

- Command:
  - Manual: run each Phase 2 example envelope through the updated `ux-agent.md` instructions
    (by hand or via a real subagent call) and confirm output matches the expected lines.
- Evidence:
  - All 4 existing gating thresholds still hold under the new dispatch; `review_threshold`
    confirmed to defer artifact_path reads until after the threshold check.

### Unlocks

- Enables:
  - Phase 5 (token-cost validation, which needs a working `ux-agent.md` to measure against).

### Blockers Or Escalation

- [ ] None beyond Phase 2's dependency.

## Phase 4: Wire agent-isdd to delegate to agent-ux

### Objective

Update this repo (`agent-isdd`) to delegate to `agent-ux:ux-agent` instead of its local
`ux-agent.md`, behind the same soft-dependency pattern already used for
`agent-nelly:nelly-orchestrator`, and remove the local copy once delegation is confirmed working.

### Risk Tier

- `high-risk` — touches every calling skill (`spec-driven-development`, `workflow-manager`,
  `requirements-agent`, `design-author`, `tdd-planner`) and removes a file those skills currently
  depend on; a mistake here regresses `agent-isdd`'s own UX, not just the new plugin's.

### Prerequisites

- Phase 3 complete and validated.
- Whether `agent-tdd`/`code-reviewer` maintainers want this extraction is out of scope for this
  phase — it's a sibling-plugin follow-up (see "Follow-Up For Sibling Plugins" below), not a
  prerequisite. `agent-isdd` adopts `agent-ux` on its own regardless of whether siblings ever do.

### Ordered Steps

1. Add "→ agent-ux (UX rendering)" section to `agent-isdd/INTEROP.md`, referencing `agent-ux`'s
   own unavailability contract rather than restating it (per design.md's Risks mitigation).
2. Update each calling skill's ux-agent invocation to construct the envelope shape (`caller:
   agent-isdd`, `event_type`, `phase_state`, `delta`, `artifact_path`) and target
   `agent-ux:ux-agent` instead of the in-process agent.
3. Add the one-plain-notice-per-session fallback when `agent-ux` is unavailable, mirroring the
   existing `agent-nelly` unavailability handling already documented in `INTEROP.md`.
4. Run a full Requirements→Design→Tasks→handoff cycle in a live session using `agent-ux` in
   place of the in-process agent; confirm output shape matches the pre-extraction baseline.
5. Delete `agent-isdd/agents/ux-agent.md` and `agent-isdd/references/ux-conventions.md` (per
   design.md's Refactor Opportunity: no fallback fork kept).
6. Bump `CHANGELOG.md` and `.claude-plugin/plugin.json` version.

### Test Intent

- Add or update:
  - None new — this phase's correctness is validated by the full-cycle walkthrough in step 4.
- Expected failing behavior:
  - Before this phase, `agent-isdd` still calls its local `ux-agent.md`; after, that file no
    longer exists, so any remaining reference to it (missed callsite) is the red condition this
    phase must catch.

### Validation Target

- Command:
  - `grep -rn "ux-agent" agent-isdd/` after step 5 — should show zero hits outside
    `INTEROP.md`'s new section and `CHANGELOG.md`'s historical entries.
- Evidence:
  - No dangling reference to the removed local agent; full-cycle walkthrough output matches
    baseline.

### Unlocks

- Enables:
  - Phase 5's token-cost comparison can now measure the real cross-plugin path, not a simulated
    one.

### Blockers Or Escalation

- [ ] None for `agent-isdd` itself. This phase does not close the sibling-plugin follow-up
      (agent-tdd/code-reviewer adoption) — that stays open for those maintainers regardless of
      `agent-isdd`'s own adoption here.

## Phase 5: Token-cost validation (the acceptance gate)

### Objective

Measure prompt tokens for the 3 representative events (`phase_transition`, `section_checkpoint`,
`review_threshold`) under the new cross-plugin path versus the pre-extraction in-process
baseline, and confirm the design's stated success criterion ("equal or smaller") actually holds.

### Risk Tier

- `standard` — measurement only, no further behavior change; failure here means returning to
  Phase 3's envelope design, not a rollout risk in itself.

### Prerequisites

- Phase 4 complete (real cross-plugin path exists to measure).

### Ordered Steps

1. Capture token counts for the pre-extraction in-process `ux-agent` call for each of the 3
   representative events (from git history / a checked-out pre-Phase-4 commit).
2. Capture token counts for the same 3 events under the new cross-plugin envelope path.
3. Compare; if any event type regresses (new > old), return to Phase 3 to trim that envelope's
   `delta` shape rather than accepting the regression.
4. Record the comparison result in this repo's `CHANGELOG.md` entry for the Phase 4 change.

### Test Intent

- Add or update:
  - None (measurement task, not a code/doc change beyond the CHANGELOG record).
- Expected failing behavior:
  - A `review_threshold` regression is the most likely failure mode, since it's the richest
    payload — watch it first.

### Validation Target

- Command:
  - Manual token count comparison (no automated harness planned given this is prompt-based, not
    code).
- Evidence:
  - All 3 representative events at or below their pre-extraction baseline.

### Unlocks

- Enables:
  - Closes out the extraction's stated success criteria; nothing further depends on this phase.

### Blockers Or Escalation

- [ ] If `review_threshold` (or any event) cannot be brought under baseline without losing
      needed rendering fidelity, escalate back to a Design revision rather than accepting the
      regression silently.

## Follow-Up For Sibling Plugins (not a task of this plan)

- [ ] **Whether `agent-tdd`/`code-reviewer` actually want this extraction** is not something
      `agent-isdd`'s own tasks can resolve or block on — it's handed off as a follow-up item for
      those plugins' own maintainers to pick up, in their own repos, on their own timeline.
      `agent-ux` (Phases 1-3) and `agent-isdd`'s adoption of it (Phase 4) proceed independently
      of this answer either way. Tracked in `agent-ux/INTEROP.md` (Phase 2, step 3's `caller`-keyed
      rules note) as an explicit "not yet confirmed with agent-tdd" caveat, and should be restated
      there as an open item for those maintainers to close, not carried as an `agent-isdd`
      blocker past this point.

## Task Readiness Checklist

- [x] At least one concrete implementation phase exists
- [x] Each phase has explicit objective, Risk Tier, steps, test intent, and validation target
- [x] Slices are safe for TDD-equivalent (example-envelope-first) execution
- [x] No unresolved blocker requires confirmation before implementation — the one open item
      (agent-tdd/code-reviewer adoption) is reclassified above as a sibling-plugin follow-up, not
      a blocker on this plan; nothing in Phases 1-5 waits on it.
- [x] State can be marked `Ready For Implementation` — for Phases 1-5 as scoped to `agent-ux` and
      `agent-isdd`'s own adoption. The plugin's "shared across all three siblings" success
      criterion remains open until the follow-up above is picked up elsewhere, but that no longer
      gates this plan's readiness.
