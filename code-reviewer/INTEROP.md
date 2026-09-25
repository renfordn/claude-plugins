<!-- TDD-SKIP -->
# Interoperability: Integrating Code Reviewer Into Another Plugin

Code Reviewer is a general-purpose review skill for Claude Code. It is not specific to
spec-driven-development (SDD) or to `agent-tdd` — SDD is simply its first real consumer. This
document is the contract for any *other* plugin author (or orchestrating skill) who wants to use
it.

## How to invoke it

For a user asking for a review of their own work, invoke the `code-reviewer` skill directly.
To review code an agent just wrote, use the independent review below instead, so the reviewer is
not the author. Either way, pass:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Mode | string | yes | `direct-review`, `review-improve`, or `pre-commit` (see SKILL.md's Invocation Modes) |
| Scope | string/array | yes | File set or diff to review. For `review-improve`, files named in pre-refactor handoff. |
| review_level | string | no | `Quick | Standard | Deep | Ultra` (default: `Standard`). Controls depth of analysis. See SKILL.md "Parameters / Review Levels" for definitions, use cases, token budgets. If omitted, auto-detected from context (phase, file scope, prior context) using SKILL.md "Auto-Detection Rules" |
| review_state_directory | string | no | Path where `REVIEW-STATE.md` / `REVIEW-HISTORY.md` persist across passes. Omit for single ephemeral pass. See SKILL.md "Review State" for details |

## Pairing with an implementer agent (e.g. `agent-tdd`)

If your implementer agent stops for a mandatory review pause (as `agent-tdd`'s `agent-TDD`
does), you are the one driving both sides — no subagent in this harness can invoke another
subagent, so the calling skill in the main thread must run this review and then resume the
implementer itself:

1. Run an **independent review** (next section) in `review-improve` mode, scoped to the files
   the implementer named. Render the returned payload with `ReportFindings` (and the dashboard
   above its threshold) yourself.
2. If a finding's `workflow_action` is `pause_for_review`, resolve the reviewer's single
   clarifying question with the user yourself before proceeding.
3. Do not resume the implementer into Refactor while any finding is `needs_detailed_review` in
   your review-state directory's `REVIEW-STATE.md` (if you supplied one), or otherwise unresolved
   for this pass.
4. Resume the implementer once clear, passing along whether/what review found.

## Independent review (reviewer ≠ author)

The context that wrote a change must not be the one that judges it. Only the main thread can
start a reviewer (subagents can't spawn subagents), so the orchestrating caller runs this, trying
each path in order and stopping at the first that returns a `<!--CODE-REVIEWER-REPORT-->` report:

1. **Spawn** the `code-reviewer:code-reviewer` agent (`agents/code-reviewer.md`). Brief it with
   mode, `review_level`, scope and acceptance criteria only — never the implementer's reasoning
   or handoff narrative.
2. **Headless**, when the `Agent` call fails at the tool-call layer (agent type not found, or the
   2026-09-15 PreToolUse schema error described in `agent-isdd/INTEROP.md`'s "Fallback — Direct
   Implementation"): run `scripts/review_headless.sh "<same brief>"` via `Bash` with a long
   timeout (Deep/Ultra can take minutes). It starts a fresh `claude -p` process with read-only
   tools, so it doesn't depend on the `Agent` tool at all. Requires the `claude` CLI on `PATH`.
3. **Self-review**, only when both fail: run the skill in your own context, and label the result
   `self-reviewed (no independent reviewer available: <reason>)` wherever the review outcome is
   reported — the handoff, `REVIEW-HISTORY.md`, and the implementer's resume message. Never let
   a self-review pass as independent.

**Large diffs** (`review_plan.py plan` reports `large`) and `Deep`/`Ultra`: run
`scripts/review_loop.py` instead of a single reviewer. It repeats fresh headless reviewer passes,
each briefed with the findings so far, until one adds nothing (max 3), and prints the merged
payload — see SKILL.md's "Review Pipeline" step 3.

The reviewer returns the `ReportFindings` payload as JSON; the caller renders it, because
`ReportFindings` and the dashboard Artifact belong to the main thread (README's "Why this is a
skill, not an agent").

### Verify pass (before rendering)

A second context tries to disprove the findings that matter, so false positives don't block work.

**When**: the review has any finding with `decision: block`, `workflow_action` of
`block_commit` / `pause_for_review`, or `severity` of `high` / `critical`, or `review_level` is
`Ultra`. Verify those findings (every finding at `Ultra`). Otherwise skip it.

**How**: same path order as the review. Spawn `code-reviewer:finding-verifier`
(`agents/finding-verifier.md`), else run `scripts/review_headless.sh --agent finding-verifier
"<brief>"`. Brief it with the scope and, per finding, its `id`, `file`, `line`, `summary`,
`failure_scenario`, and tier. No self-verification: if both paths fail, skip the pass and say
so, rather than having the reviewer's or implementer's context check its own findings.

**Apply** each result, then render:

| Outcome | What the caller does |
|---|---|
| `upheld` | `verdict: CONFIRMED` |
| `refuted` | Drop the finding from the payload. Say how many were refuted in one line, and log them in `REVIEW-HISTORY.md` if a review-state directory was supplied |
| `downgraded` | Apply the new tier/severity, `verdict: PLAUSIBLE`, and re-derive `decision`/`workflow_action` — a finding downgraded to tier-3 or lower can't `block` on its own |

Findings the pass didn't cover get `verdict: PLAUSIBLE`. If no verify pass ran, leave `verdict`
off every finding — `ReportFindings` reserves it for verified reviews.

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

This pattern follows existing `agent-tdd` capability-gating practices (check once,
degrade, notify, proceed).

## Strategic Review Placement by ISDD Phase

When invoked within an ISDD (Integrated Spec-Driven Development) workflow, code-reviewer is placed
at specific points, using specific review levels, to validate different aspects of the pipeline.
This section documents the strategic placement pattern and the reasoning behind level selection
at each phase.

**Strategic Review Placement Table:**

| ISDD Phase | Review Level | Purpose | What to Review | When | Invoked By |
|------------|--------------|---------|---|---|---|
| **Design** | Deep | Coherence validation | Design patterns, file touchpoints, slice feasibility | After design complete, before Tasks | design-author (agent-isdd skill) |
| **Tasks** | Standard | Clarity validation | Task phrasing, Depends-On graph, validation steps | After task slicing, before implementation | task-slicer (agent-tdd internal skill) |
| **Impl: Per-Slice (Green)** | Standard or Deep | Implementation check | Code correctness, design alignment (Deep for high-risk) | After slice passes tests | agent-tdd |
| **Impl: Post-Slices (Coherence)** | Deep or Ultra | Cross-slice validation | Cross-slice interactions, duplicates, module boundaries, regressions | After all slices complete Green + Refactor | agent-tdd |

**Rationale:**

- **Design (Deep)**: Design decisions have architectural impact; thorough validation prevents rework
- **Tasks (Standard)**: Early feedback on clarity; full depth not needed until design is complete
- **Per-Slice Green (Standard/Deep)**: Standard for normal slices; Deep for high-risk to catch edge cases early
- **Coherence Review (Deep/Ultra)**: Ultra when majority of slices are high-risk; captures cross-slice interactions that per-slice reviews miss

*Note: Requirements-phase review and Per-Slice Red reviews are not currently implemented; integration at those points is aspirational. The table above reflects current invocation points.*

**Ralph Loops Integration:**

Review-level findings feed into ralph loops validation:
- **Design-phase Deep findings** → Traceability validation (are all design touchpoints covered in research?)
- **Per-slice Standard findings** → Per-slice correctness validation
- **Coherence Deep/Ultra findings** → Cross-slice regression detection and duplicate detection

See `agent-tdd/INTEROP.md` Design Spec Mode for Ralph Loops integration details.

**Cross-references:**

- **Phase-by-Phase Guidance**: **corrected 2026-09-24** — `code-reviewer/skills/code-reviewer/
  SKILL.md`'s §Auto-Detection Rules (auto-detection rules and per-ISDD-phase examples); this
  used to cite a nonexistent top-level `code-reviewer/SKILL.md` and a nonexistent
  §ISDD Phase Context heading
- **Per-Slice Strategy**: `agent-tdd/SKILL.md` §Review-Level Strategy (per-slice checkpoints)
- **Ralph Loops Integration**: `agent-tdd/SKILL.md` §Finding Flow to Ralph Loops
- **Design Rationale**: **corrected 2026-09-24** — no `design.md` exists in this repo (it was
  the original SDD design doc this plugin was built from, which lives under
  `~/.claude/sdd-memory/`, not the repo); see `agent-isdd/INTEROP.md`'s "Strategic Review
  Placement via Review Levels" section for the live reasoning instead

## Explaining code: the `code-brief` skill

Explaining how existing code works is a separate skill, `code-brief`
(`skills/code-brief/SKILL.md`, `/code-reviewer:code-brief`), not a mode of this one. It returns a
single Artifact for a human reader — no `findings` array, no `ReportFindings` call, nothing
persisted to `REVIEW-STATE.md`, `REVIEW-HISTORY.md`, or `TODO-LEDGER.md`, and no
`workflow_action` to gate on. Don't route its output into a consumer expecting the Decision
Model's fields.

## What you get back

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| findings | array (ReportFindings) | yes | All review findings with full details |
| review_dashboard | Artifact | no | Visual dashboard rendered by the skill; present above 5-finding/1-file threshold |
| findings.json | file | no | Every finding (no 32 cap) plus `followups` (refactor / consolidation / deferred-defect items), at `review_plan.py findings-path`. Schema: SKILL.md "findings.json". agent-isdd's SessionStart ingests `followups` into its follow-up queue (its INTEROP.md "← code-reviewer") |

**Finding fields:**
- `evidence_tier` (integer 1-5): Verification confidence for each finding
- `review_level` (string, optional): Analysis depth (Quick/Standard/Deep/Ultra)

See "Evidence Tier Model (Orthogonal to Review Level)" above for how both axes interact. findings.json is the machine-readable summary; `review_plan.py validate` checks it.

## Out-of-scope items (`TODO-LEDGER.md`)

If you supplied a review-state directory, `code-reviewer` also maintains a `TODO-LEDGER.md`
there (`references/TODO-LEDGER.md.template`) — one row per out-of-scope item it flags during a
pass, independent of `REVIEW-STATE.md`/`REVIEW-HISTORY.md`. `code-reviewer` is this file's only
writer.

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

The skill enforces these itself — see SKILL.md §"ReportFindings Payload (the handover)" for the
full field mapping from the internal review record to the tool schema. Callers building their
own `ReportFindings` payload from Python can use `shared/findings_validator.py`
(`shared/FINDINGS_VALIDATOR_USAGE.md`), but the skill doesn't depend on it: the model writes the
tool-call JSON directly and can't run a Python helper from inside it.
