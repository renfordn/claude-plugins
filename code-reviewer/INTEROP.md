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
- **`review_level`** (optional) — `Quick | Standard | Deep | Ultra` (default: `Standard`). Controls
  the depth of analysis and checks performed. Allows balancing comprehensiveness with token
  efficiency across different workflows. See SKILL.md's "Parameters / Review Levels" section for
  definitions, use cases, and token budgets. If omitted, skill auto-detects level from context
  (phase, file scope, prior context) using rules documented in SKILL.md's "Auto-Detection Rules".
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

## Evidence Tier Model (Orthogonal to Review Level)

The existing Evidence Tier Model (tier-1..5) and the new Review Level (Quick/Standard/Deep/Ultra)
are **independent axes**, both applied to every finding:

- **Evidence Tier** (tier-1..5) = how directly a finding was verified (mechanically, code-read, 
  inferred, pattern-based, speculative). Reflects verification confidence, not severity.
- **Review Level** (Quick/Standard/Deep/Ultra) = what checks were performed and what scope was 
  analyzed. Reflects analysis depth.

Both fields are always present in findings; callers should interpret them independently. A finding
can be Evidence Tier 3 and Review Level Deep, or tier-1 and Quick, etc. This orthogonality is
intentional and allows flexible interpretation across different workflows.

**No breaking change**: Evidence Tier definitions, downgrade logic, and Decision Model all remain
unchanged. Review Level is added alongside, not replacing Evidence Tier.

## Graceful Degradation for Review Levels

When a requested `review_level` is unavailable (e.g., `Ultra` requested but multi-agent capability
missing):

1. **Degrade to next-lower level**: `Ultra` → `Deep`, `Deep` → `Standard`, etc.
2. **Emit notification**: Inform caller that review is running at lower level.
3. **No auto-upgrade**: If caller requests `Deep` and multi-agent is available, do NOT auto-upgrade
   to `Ultra` without explicit request.
4. **Never block**: User always gets some review; review never fails silently or returns an error.

This pattern follows existing `agent-tdd` and `agent-ux` capability-gating practices (check once,
degrade, notify, proceed).

## Strategic Review Placement by ISDD Phase

When invoked within an ISDD (Integrated Spec-Driven Development) workflow, code-reviewer is placed
at specific points, using specific review levels, to validate different aspects of the pipeline.
This section documents the strategic placement pattern and the reasoning behind level selection
at each phase.

**Strategic Review Placement Table:**

| ISDD Phase | Review Level | Purpose | What to Review | When | Invoked By |
|------------|--------------|---------|---|---|---|
| **Requirements** | Standard | Clarity validation | EARS formatting, scope completeness, non-goal conflicts | After requirements draft, before approval | spec-reviewer |
| **Design** | Deep | Coherence validation | Design patterns, file touchpoints, slice feasibility | After design complete, before Tasks | design-author |
| **Tasks** | Standard | Clarity validation | Task phrasing, Depends-On graph, validation steps | After task slicing, before implementation | task-slicer |
| **Impl: Per-Slice (Red)** | Quick | Test clarity | Test intent, acceptance criteria wording | After test written, before implementation | test-author (high-risk only) |
| **Impl: Per-Slice (Green)** | Standard or Deep | Implementation check | Code correctness, design alignment (Deep for high-risk) | After slice passes tests | agent-tdd |
| **Impl: Post-Slices (Coherence)** | Deep or Ultra | Cross-slice validation | Cross-slice interactions, duplicates, module boundaries, regressions | After all slices complete Green + Refactor | agent-tdd |

**Rationale:**

- **Requirements & Tasks (Standard)**: Early feedback on clarity; full depth not needed until design is complete
- **Design (Deep)**: Design decisions have architectural impact; thorough validation prevents rework
- **Per-Slice Red (Quick)**: Tests should be understandable before implementation; Quick level ensures intent is clear
- **Per-Slice Green (Standard/Deep)**: Standard for normal slices; Deep for high-risk to catch edge cases early
- **Coherence Review (Deep/Ultra)**: Ultra when majority of slices are high-risk; captures cross-slice interactions that per-slice reviews miss

**Ralph Loops Integration:**

Review-level findings feed into ralph loops validation:
- **Design-phase Deep findings** → Traceability validation (are all design touchpoints covered in research?)
- **Per-slice Standard findings** → Per-slice correctness validation
- **Coherence Deep/Ultra findings** → Cross-slice regression detection and duplicate detection

See `agent-tdd/SKILL.md` §Finding Flow to Ralph Loops for detailed integration.

**Capability Detection Note:**

This INTEROP.md is parsed by `plugin-orchestrator` for capability detection. The substring
**"Integrating Code Reviewer"** (present in this document's title and section headings) is required
for auto-detection to succeed. See `plugin-orchestrator/tests/test_smoke_e2e.py` for verification.

**Cross-references:**

- **Phase-by-Phase Guidance**: `code-reviewer/SKILL.md` §ISDD Phase Context (auto-detection rules and examples)
- **Per-Slice Strategy**: `agent-tdd/SKILL.md` §Review-Level Strategy (per-slice checkpoints)
- **Ralph Loops Integration**: `agent-tdd/SKILL.md` §Finding Flow to Ralph Loops
- **Design Rationale**: `design.md` §Strategic Placement (full reasoning for phase selections)

## What you get back

Findings are rendered via `ReportFindings` (always) and, above a 5-finding/1-file threshold, an
additional review-dashboard — an `Artifact` this skill opens directly by default, or one rendered
by `agent-ux:ux-agent` instead when you supplied a `phase_state` and it's installed (see "How to
invoke it" above). Either way it's the same dashboard content; there is no separate report object
to parse beyond what `ReportFindings`/the dashboard already show — `code-reviewer` does not return
a machine-readable summary distinct from its rendered output.

Each finding carries both `evidence_tier` (tier-1..5) and (optionally) `review_level` 
(Quick/Standard/Deep/Ultra) for caller interpretation. See "Evidence Tier Model (Orthogonal to
Review Level)" above for how both axes interact.

## Out-of-scope items (`TODO-LEDGER.md`)

If you supplied a review-state directory, `code-reviewer` also maintains a `TODO-LEDGER.md`
there (`references/TODO-LEDGER.md.template`) — one row per out-of-scope item it flags during a
pass, independent of `REVIEW-STATE.md`/`REVIEW-HISTORY.md`. `code-reviewer` is this file's only
writer. If `agent-ux:ux-agent` is installed, you can ask `code-reviewer` to surface it as a
dashboard: it sends a `todo_digest` envelope (see `agent-ux`'s own `INTEROP.md`) that reads the
ledger and publishes/redeploys it — `agent-ux` never tracks this state itself, only renders what
`code-reviewer` already wrote.

## Cross-project or cross-feature memory

If your ecosystem has a separate memory plugin (e.g. `agent-nelly`) for durable, higher-level
facts, `code-reviewer` will never write its own per-file/per-pass records there — that boundary
is a guardrail in its own SKILL.md, not something you need to enforce from the caller side. A
recurring convention violation worth remembering across features is something *you* decide to
write to that memory tier, separately from this skill's review-state directory.

## Validating findings before ReportFindings

Before calling `ReportFindings`, ensure all findings meet the tool's field constraints:

- `short_summary`: ≤60 characters (required)
- `summary`: ≤200 characters (recommended)

Use the shared `findings_validator` utility to truncate oversized fields and validate input before
calling the tool. See `shared/FINDINGS_VALIDATOR_USAGE.md` for examples and API reference. This
prevents `ReportFindings` call failures when findings contain verbose summaries.
