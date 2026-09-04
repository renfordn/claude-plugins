---
name: code-reviewer
description: Review code changes against evidence tiers and a required decision model, rendering findings visually via ReportFindings (and an optional review dashboard for larger passes). Per-file review state persists to a caller-supplied location if given, or stays ephemeral for a single pass otherwise. Invoked directly by the user, mid-TDD-loop by an orchestrating skill, or pre-commit. Independent of any other plugin.
---

# Code Reviewer

Claude-native review skill, invoked as a plain skill (not a Task-tool subagent) so its findings
can be rendered directly with `ReportFindings` in the same turn. Tool references use Claude-
native tools: `Bash`, `Read`, `Edit`, `ReportFindings`, `Artifact`, and (only for the optional
`agent-ux:ux-agent` delegation described in "Visual Review" below) `Agent`.

This skill is not specific to any planning workflow or implementer agent. It has no hard
dependency on `spec-driven-development`, `agent-tdd`, `agent-ux`, or any other plugin — anything
that can invoke a skill and optionally supply a review-state location (and, separately, a
`phase_state`) can use it, and it works fully standalone with none of them installed.

## Use This Skill When

- The user explicitly asks for a code review (`direct-review`).
- An implementer agent (e.g. `agent-tdd`'s `agent-TDD`) reaches a mandatory pre-refactor review
  boundary — triggered by the orchestrating skill (main thread) that spawned that agent, not by
  the agent itself, since a subagent cannot invoke a skill from its own isolated context; the
  agent stops at that boundary and the orchestrating skill runs this review before resuming it
  (`review-improve`).
- A commit is about to be created and the calling workflow wants a final pass (`pre-commit`).

## Invocation Modes

### `direct-review`

Triggered explicitly by the user. Scope: whatever file set or diff the user names, or the
working tree diff if unspecified. Output: findings persisted per *Review State* below (if a
location was supplied), rendered per "Visual Review" below.

### `review-improve`

Triggered by the caller immediately after an implementer agent reports a Green test run and
stops at its review checkpoint, before that agent is resumed into Refactor. Scope: the files
touched to make the just-passed test go green. Output: same as `direct-review`, plus a gate
decision the caller acts on: resume the implementer into Refactor, or first pause on the resume
contract with the user if a finding requires detailed review. Never blocks silently — every
invocation returns a decision.

### `pre-commit`

Triggered immediately before a commit, by whatever mechanism the calling workflow uses to gate
commits, or by explicit user request. Scope: the full staged diff. Any `tier-1`/`tier-2` finding
with `workflow_action: block_commit` prevents the commit until resolved or explicitly overridden.

## Visual Review

- **Default**: report findings through the `ReportFindings` tool — host-native structured
  rendering, no HTML to author, the cheapest option and the default for every mode/size.
- **Above threshold**: when a pass has more than 5 findings or touches more than one file, open a
  redeployable review-dashboard (findings as resolvable cards next to their diff hunks). This is
  what makes the review something the user resolves *with* the agent, turn by turn, instead of
  reading a static list: as findings get discussed and resolved in the conversation, redeploy the
  same dashboard in place to reflect the current state, rather than reposting it. **This is the
  canonical definition of the 5-finding/1-file threshold** — `agent-ux`
  (`references/ux-conventions.md`'s "Review dashboard (Artifact)" section, and
  `agents/ux-agent.md`'s `review_threshold` dispatch) and `agent-isdd`
  (`doc-consistency-auditor/SKILL.md`'s documented override) both mirror this exact value rather
  than choosing their own; if it changes here, update those to match.
  - **Delegate to `agent-ux:ux-agent` when both hold**: the caller supplied a `phase_state`
    (see `INTEROP.md`'s "How to invoke it" — only present when this pass runs inside a larger
    workflow that has one; a standalone or pre-commit pass never supplies it), and
    `agent-ux:ux-agent` is available this session (checked once per pass — scan the session's
    agent-types listing for `agent-ux:ux-agent`, the same Availability Check pattern used
    throughout this ecosystem). Construct a `review_threshold` envelope (`caller:
    code-reviewer`, `phase_state`, `delta: {finding_count, files_touched, findings}`,
    `artifact_path`) instead of opening the Artifact directly — see `agent-ux`'s own `INTEROP.md`
    for the envelope contract. `findings` entries carry `{id, title, tier, severity}` only, no
    diff hunks — `agent-ux` reads those from `artifact_path` itself once it has confirmed the
    threshold independently, never trust a caller-pushed evidence payload.
  - **Otherwise, open the Artifact directly**, exactly as before. This is not a degraded
    fallback — it's the correct behavior for a genuinely standalone pass, which is most of them.
    `code-reviewer` never blocks, delays, or changes its findings on `agent-ux`'s absence; the
    only thing that changes is which tool renders the same dashboard content.
- Below the threshold, `ReportFindings` alone is sufficient visual structure — do not open a
  dashboard (directly or via `agent-ux`) just for its own sake; that's exactly the token cost the
  threshold exists to avoid.
- If review turns up something concrete but genuinely outside the diff's scope (dead code, a
  stale doc, a confirmed TODO unrelated to this change) — not a finding against the change
  itself — flag it via `spawn_task` directly instead of folding it into `ReportFindings`. Only
  for issues you've already confirmed are real and out of scope; never for a low-confidence
  hunch.

## Evidence Tier Model

Every finding is assigned exactly one evidence tier, reflecting how directly it was verified —
not how severe it is. Tier and severity are independent axes.

- **tier-1** — Directly observed and reproducible (a command run, or the exact code path read)
  and the defect is mechanically verifiable. No inference required.
- **tier-2** — Directly observed in the diff/file content, but confirmation required light
  reasoning grounded in read code, no assumption about unseen code.
- **tier-3** — Inferred from a partial view of the system; plausible and grounded in what was
  read, but depends on an assumption about code not directly inspected.
- **tier-4** — Pattern-based or convention-based concern; no direct reproduction.
- **tier-5** — Speculative or needs-human; cannot be verified or disproven with available
  tools/context. Always paired with `confidence: low` and typically `workflow_action:
  pause_for_review` or `defer`.

### Downgrade Logic (explicit)

A finding's tier is downgraded (never silently upgraded) when:

- **tier-1 → tier-3**: the reproduction/read was scoped to a single file, but the defect's
  actual impact depends on an uninspected caller/consumer.
- **tier-1 → tier-2**: the observation is mechanically true but nothing was executed to confirm
  exploitability or runtime effect.
- **tier-2 → tier-4**: the reasoning chain requires assuming a third-party/unread module's
  behavior rather than reading it directly.
- **any tier → tier-5**: the persisted review-state row (see *Review State* below) for the
  touched file is `stale` or `needs_detailed_review` (diff fingerprint mismatch) at review time.
- **tier-3 or lower → never auto-resolved**: must never be marked `decision: resolved` without
  explicit user confirmation captured in the resume contract.

## Decision Model

Every finding populates these five fields — no exceptions; if a field can't be honestly
populated, downgrade the tier rather than omitting the field.

- **`decision`** — `accept` | `flag` | `block` | `defer`.
- **`severity`** — `critical` | `high` | `medium` | `low` | `nit`.
- **`category`** — `correctness` | `security` | `test-coverage` | `style` | `architecture` |
  `performance` | `documentation`.
- **`workflow_action`** — `proceed` | `pause_for_review` | `block_commit` | `require_test` |
  `log_only`.
- **`confidence`** — `high` | `medium` | `low`. Tracks how sure the reviewer is the finding is
  correctly characterized (distinct from tier, which tracks how directly it was verified).

Valid field-value combinations are not otherwise restricted.

## Combined Findings And Anti-Blur Rules

**Merge** when observations share the same root cause, or are the same category/severity where
fixing one resolves all. **Never merge** (always split) when: `category` differs, `workflow_action`
differs, evidence tiers differ unless the higher strictly subsumes the lower, or merging would
let a low-confidence observation borrow credibility from a `tier-1` one riding alongside it. A
combined finding's tier is always the lowest among its merged observations, never the highest.

## Review State (optional persistence)

This skill has no memory location of its own. If the caller supplies a **review state
directory** (a path) when invoking this skill, persist per-file state there using the templates
in `references/`:

- `REVIEW-STATE.md` — one row per reviewed file (`references/REVIEW-STATE.md.template`). Update
  in place on re-review; a `decision: block` or unresolved tier-3-or-lower finding sets the row
  to `needs_detailed_review`, never `passed`.
- `REVIEW-HISTORY.md` — append-only log, one entry per pass
  (`references/REVIEW-HISTORY.md.template`). Never edit or remove prior entries.

**Staleness check**: before trusting an existing `REVIEW-STATE.md` row as `passed`, recompute the
file's diff fingerprint and compare. A mismatch always downgrades that row to
`needs_detailed_review` before any new pass begins — this skill owns that check itself; it does
not defer to any other plugin's state-repair logic.

**If the caller supplies no review-state directory**, stay ephemeral: apply every rule above
within this single pass and render findings normally, but there is nothing to read staleness
against and nothing to write — say so plainly rather than implying persistence happened. Do not
invent a location or write outside a directory the caller explicitly gave you.

**If the caller's ecosystem has separate cross-project or cross-feature memory** (e.g. a memory
plugin), never write per-file review status or per-pass history there — that tier is for
durable, higher-level facts (a recurring convention violation worth remembering across features),
never for this skill's per-file/per-pass records, which belong only in the review-state
directory above.

## Resume Contract

When a finding's `workflow_action` is `pause_for_review`, stop and ask **exactly one clarifying
question** — never a list, never open-ended back-and-forth.

1. Identify the single most decision-relevant unknown blocking a `decision`.
2. Present that one question plus the finding's current best-guess field assignment.
3. If a review-state directory was supplied, record the paused finding in `REVIEW-STATE.md` as
   `needs_detailed_review` immediately, so the pause is durable even across a session end.
4. On the next turn, resume from exactly that finding using the user's answer to finalize
   `decision` and update `confidence` to `high`. Do not re-ask. If more ambiguity remains,
   downgrade tier and record a new, separate `defer`-decision finding for a future pass instead
   of extending the dialogue.
5. If invoked from `review-improve`, the caller does not resume the implementer agent into
   Refactor until this single question is answered; other findings in the same pass that don't
   require pause are processed and written normally.

## Output Shape (per finding)

`id`, `title`, `locations`, `evidence_tier`, `decision`/`severity`/`category`/`workflow_action`/
`confidence`, `evidence` (what was read or run to support the tier), `resolution_note`.

## Guardrails

- Never leave a `decision`, `severity`, `category`, `workflow_action`, or `confidence` field
  blank or implied — downgrade tier instead.
- Never mark a `REVIEW-STATE.md` row `passed` while any finding on that file remains
  `decision: block` or unresolved at `tier-3` or lower.
- Never ask more than one clarifying question per paused finding per turn.
- Never write per-file review state anywhere but the caller-supplied review-state directory, and
  never write it into any cross-project/cross-feature memory tier.
- Never silently trust a `stale` or `needs_detailed_review` row; re-derive tier per the
  downgrade rules before reusing it.
- Never open a review-dashboard Artifact below the 5-finding/1-file threshold.
- Never claim persistence happened when no review-state directory was supplied.
