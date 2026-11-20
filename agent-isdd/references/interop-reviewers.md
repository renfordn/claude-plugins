# Interop: agent-isdd ↔ code-reviewer (rollback, review gate, review placement)

Moved verbatim from `INTEROP.md` (split to keep the index short), plus the current review-tracking notes at the end.

## ← agent-tdd / code-reviewer (rollback request)

Sometimes `agent-tdd`'s Green→Refactor review pause (or `code-reviewer`) discovers that the
*task* itself — not just the implementation — was wrong. There is no cross-plugin IPC to build
a live push channel for this, so the return path is a documented marker convention plus a
check `agent-isdd` performs on its own re-entry, not agent-isdd reaching into `agent-tdd`'s
active loop. Two genuinely different marker formats feed two different paths below — this used
to be documented as one marker with two delivery paths, which was wrong: `agent-tdd` never emits
SDD-specific vocabulary (see its own `INTEROP.md`), so it cannot literally emit the human-relay
marker below itself. That was a real gap, not just a documentation gap — closed by giving
`agent-tdd` its own generic marker instead of assuming it would speak agent-isdd's.

**Automatic path** (agent-tdd's own generic signal): `agent-tdd`'s **Plan Validity Flag** (see
`agent-tdd/INTEROP.md`'s section of the same name) is a caller-agnostic marker —
`<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` — with no target phase, since `agent-tdd` has no
concept of agent-isdd's phase vocabulary. When `agent-tdd:agent-TDD`'s spawn report contains it,
`hooks/subagent_report.py`'s `SubagentStop` handler recognizes it (independently of its normal
narrative-report capture, which excludes implementation-phase reports otherwise), defaults the
rewind target to `Requirements` (policy and rationale: `references/rollback-guide.md`'s "Which
target phase to name"), and writes `rollback_pending` to `workflow-state.json` plus a
`Pending Rollback Request` line to `workflow-state.md`, with the reason text tagged so a later
reader (or `workflow-manager`'s "Rollback Request Intake," which can re-target forward) knows
`Requirements` was defaulted, not derived from the reason. The next `before-continue` hook checks for it first, surfaces the request and asks the user to
run `/isdd-rewind <target>` (user-run; the model does not invoke it). A reason starting `rescope (design):` comes from agent-TDD's Red-Phase Rescope: implementation
found a prerequisite fix/refactor that changes a design contract. Re-target it to `Design`, fold
the mini re-spec into `design.md`'s `Prerequisite Fixes & Refactors`, then re-slice.

**Human-relay path** (agent-isdd's own vocabulary, for a human relaying a finding): a human (or
whichever context is driving) who already knows agent-isdd's phase names can paste this marker
directly into a message re-entering agent-isdd:

```
<!--SDD-ROLLBACK-REQUEST: target=<Requirements|Design|Tasks> reason="..."-->
```

`before-continue` recognizes it in user input the same way, when present — this is the path for
`code-reviewer`'s findings, or any `agent-tdd` resume happening via `SendMessage` in a session
agent-isdd isn't part of, since neither has an automatic hook of its own. For step-by-step
instructions on both paths, see [`rollback-guide.md`](rollback-guide.md).

Do not treat either path as a fully automatic guarantee on its own: the automatic path only
fires when `agent-tdd` actually raises a Plan Validity Flag on its *initial* spawn report (not
on a later `SendMessage` resume, which this hook does not observe), and only ever targets
`Requirements` by default — human-relay remains the only path with an explicit target, and the
only path for `code-reviewer` altogether.

## → code-reviewer (review gate)

Hooks never invoke `code-reviewer` (they cannot spawn agents). `design-author` requests the design
review (see Strategic Review Placement below). For implementation, in a serial run it is agent-tdd's
Green pause; in a parallel run the agent-isdd thread, as tdd-parallel lead, spawns `code-reviewer`
per slice and `review_tracking` records it.

## ← code-reviewer (review follow-ups)

code-reviewer writes refactor / consolidation / deferred-defect items as `followups` in its
findings.json (default `<git dir>/code-review/findings.json`; schema in code-reviewer's SKILL.md
"findings.json"). agent-isdd's SessionStart ingests them into
`<sdd memory>/<project>/followups/<id>.md` (one file each, frontmatter `kind`, `status:
open|picked|done|dismissed`, `nelly_recorded`, `files`), lists the open ones, and hands
unrecorded ones to agent-nelly as `file-relevance` entries, so editing one of those files later
surfaces the item. `hooks/followups.py` moves items through their states; the Start Protocol offers
open items as feature candidates. Neither plugin imports the other: findings.json is the contract.


## Strategic Review Placement via Review Levels (Current Approach)

The tiered review-level feature (Quick/Standard/Deep/Ultra) provides the design pattern for 
strategic review placement across ISDD phases. Rather than hooks managing invocation, 
callers (agent-tdd, spec-driven-development skills) invoke `/code-reviewer` directly at the 
appropriate level for each phase context. This is simpler, debuggable, and respects the 
harness constraint that hooks cannot invoke skills.

The per-phase table (which level, when, and who invokes it) lives once, in
`skills/spec-driven-development/references/review-levels.md`. In short: `design-author` requests
one Deep review of the design before handoff; agent-tdd requests Standard (Deep if high-risk) at
each slice's Green pause and one Deep coherence review after all slices, which the caller may
raise to Ultra when most slices are high-risk. Requirements and Tasks reviews are not
implemented.

### Ralph Loops Integration

Review findings feed into ralph loops validation at multiple checkpoints:

- **Design-phase Deep review** → Traceability validation input: does design.md touch the right files?
- **Tasks-phase Standard review** → not implemented (see `skills/spec-driven-development/references/review-levels.md`)
- **Per-slice Standard review** → Per-slice correctness: implementation matches slice requirements
- **Coherence review (Deep/Ultra)** → Cross-slice Traceability validation: did all slices co-evolve correctly?

Each review level produces findings appropriate to its scope; ralph loops' Traceability validation 
then confirms that design-level decisions were respected through implementation.

### Auto-Detection Rules

When a caller does not pass `review_level`, `code-reviewer` infers it from context (explicit
request, then ISDD workflow phase, risk tier / file scope, prior context, fallback `Standard`).
`code-reviewer/skills/code-reviewer/references/parameters.md`'s "Auto-Detection Rules" section is the
authoritative definition, and `code-reviewer/INTEROP.md` relies on it. Callers (agent-tdd,
design-author) still pass an explicit level where the table above names one, since an explicit
request takes priority.

## Review tracking and user-run commands (current behavior)

- `review_tracking` is the sole writer of the `reviewed` map in `workflow-state.json`
  (SubagentStop via `subagent_dispatch` -> `high_risk_reviewer.main` -> `review_tracking.evaluate`).
  A review counts for slice N only when the `code-reviewer` stop's report carries both
  `<!--CODE-REVIEWER-REPORT-->` and `<!--REVIEW-SCOPE: slice=N-->`; code-reviewer emits them when its
  prompt contains `Review scope: slice=N`.
- `complete_guard` blocks `Workflow Status: Complete` while high-risk slices lack a review; with feature-level `Risk: high`
  every slice needs a review (or the fallback `all`). The only
  fallback is the exact form `Accepted via AskUserQuestion: <slice ids | all>: <reason>`, which clears
  only the named slices.
- `/isdd-rewind` and `/isdd-board-sync` are user-run commands (`disable-model-invocation: true`); the
  model never invokes them. A rollback request (`rollback_pending`, `SDD-ROLLBACK-REQUEST`) is
  surfaced to the user, who runs `/isdd-rewind`.
- Release 4 reports (`code-reviewer/INTEROP.md` "Release 4 skills and report markers"): a finding
  re-check `<!--FINDING-RECHECK-REPORT-->` is not a slice review and is never recorded in the `reviewed` map.
  A skipped pre-push review (`pre-push.json` status `declined`) and a finding with
  `resolution: declined` (a fix the user turned down) are separate records; neither is ever a
  Review Fallback, `decision: accept` or a `deferred-defect` follow-up. The pre-push review (`<!--PRE-PUSH-REVIEW-->`) counts as an unscoped review
  (it emits `<!--CODE-REVIEWER-REPORT-->` with no `REVIEW-SCOPE`), so it never satisfies a slice.
