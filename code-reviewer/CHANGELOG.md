<!-- TDD-SKIP -->
## [Unreleased]

## [0.2.0] - 2026-09-25

- **Fix**: the skill didn't load for casual review requests. Its description listed internals
  (evidence tiers, decision model) instead of what users ask for. Measured with new
  `evals/trigger-*` cases ("look over this", "any bugs in this?", "is this safe to ship?"), 3
  runs each: the skill loaded 0/9 times before and 9/9 after, and 12/12 on the existing cases
  (was 11/12). Every planted bug was found in every run either way.

- **Feature**: verify pass. New read-only `agents/finding-verifier.md` tries to disprove each
  gating finding (block / block_commit / pause_for_review, or every finding at Ultra) and returns
  upheld / refuted / downgraded. The caller drops refuted findings and sets `verdict` from the
  result. `verdict` is now omitted when no verify pass ran, as `ReportFindings` intends; it used
  to be derived from tier alone. `scripts/review_headless.sh` gains `--agent finding-verifier`
  and rejects path-like agent names. See INTEROP.md's "Verify pass".
- **Feature**: `evals/`, a `claude plugin eval` suite with planted-bug fixtures (off-by-one,
  unchecked `None`, SQL injection at Ultra) and a clean-file false-positive case. Fixtures are
  inline in each prompt with line numbers, because `context.add_dirs` mounted nothing in Claude
  Code 2.1.282. First run (1 run/case, no baseline): every planted bug found at the right line,
  no false positive, but the skill didn't fire on the off-by-one case. CI checks the suite's
  structure (`tests/test_evals_structure.py`); run it with `claude plugin eval ./code-reviewer`.
- **Breaking**: `research-brief` is no longer a mode of the `code-reviewer` skill. It's the
  separate `code-brief` skill (`skills/code-brief/SKILL.md`), which replaces
  `commands/code-brief.md` — `/code-reviewer:code-brief` works as before. `code-reviewer`'s
  SKILL.md drops from 414 to 340 lines.
- **Fix**: `first-class.json` no longer declares `agents` absent.

## [0.1.17] - 2026-09-25

- **Feature**: independent review, so the context that wrote a change never judges it. New
  read-only `agents/code-reviewer.md` agent (spawned by the main-thread caller) and
  `scripts/review_headless.sh` fallback (fresh `claude -p` process, for sessions where `Agent`
  spawns fail). Both apply SKILL.md's rules and return the `ReportFindings` payload as JSON for
  the caller to render. If both fail, the caller self-reviews and must label it `self-reviewed`.
  See INTEROP.md's "Independent review (reviewer ≠ author)". New test:
  `tests/test_independent_review.py`.

## [0.1.16] - 2026-09-25

- **Feature**: new `/code-reviewer:code-brief` command — invokes `research-brief` mode directly
  (`commands/code-brief.md`) instead of requiring a hand-phrased request.
- **Docs**: `research-brief`'s "Research Brief Output" section in SKILL.md now has a "Design bar"
  step — loads `frontend-design` for the Artifact's visual design pass and grounds diagram idiom,
  palette, and type in the subsystem being explained, so the output doesn't default to one
  reused diagram template. README updated to point at the new command.

## [0.1.15] - 2026-09-24

- **Feature**: new `research-brief` invocation mode — triggered explicitly when the user wants to
  understand or be walked through how existing code works, rather than review a change. Produces
  a single visual Artifact (structure and/or timeline diagram plus a narrative walkthrough) for a
  human reader instead of `ReportFindings`. Reuses the Evidence Tier Model for grounding (claims
  still carry tier-1..5) and `review_level` for investigation depth, but has no Decision Model
  and writes nothing to `REVIEW-STATE.md`/`REVIEW-HISTORY.md`/`TODO-LEDGER.md` — there's no
  commit to gate. Owns its Artifact directly (no `agent-ux` dependency), following the same
  precedent as `agent-ux`'s own design-phase-diagrams carve-out. See SKILL.md's "Research Brief
  Output" section, README's "Research briefs: explaining code, not reviewing it", and INTEROP.md's
  "`research-brief` mode: a different contract".

## [0.1.14] - 2026-09-24

- **Chore**: moved `first_class.declared_absent` out of `.claude-plugin/plugin.json` into `.claude-plugin/first-class.json` — `claude plugin validate --strict` rejects unknown manifest fields.
- **Fix**: `ReportFindings` handover failed with `too_big` on `short_summary`. SKILL.md now has a "ReportFindings Payload (the handover)" section mapping the internal review record onto the tool schema (`short_summary` ≤60, `category` ≤40, max 32 findings, `review_level`→`level`), with a valid example and retry-on-validation-error guidance. INTEROP.md no longer points the skill at an uncallable Python validator. New test: `tests/test_skill_report_findings_payload.py`.

## [0.1.13] - 2026-09-24

- **Feature**: `Standard` review level (the default) now explicitly checks SOLID-principle
  violations, separation-of-concerns problems, and duplicated logic that should be consolidated
  into a shared function/method/class — scoped to the diff/file under review. Previously these
  were only implicit (a generic "design coherence" bullet) and gated behind `Deep`/`Ultra`.
  `Deep`'s SRP bullet reworded to make clear it extends Standard's new check rather than
  duplicating it; `Ultra`'s duplicate-detection bullet reworded to state it's project-wide,
  distinct from Standard's new diff/file-scoped check. Decision Model's `category` field
  documented as mapping these findings to `architecture` (no new enum value).
- **Note**: file-size/line-count-ceiling enforcement was explicitly considered and rejected as a
  `code-reviewer` concern — that stays a design-time check owned by `agent-isdd` (see
  `agent-isdd`'s own 0.1.53 changelog entry).

## [0.1.12] - 2026-09-24

- **Docs**: `INTEROP.md`'s cross-reference list cited a nonexistent top-level `code-reviewer/
  SKILL.md` and a nonexistent `§ISDD Phase Context` heading (real path is `skills/code-reviewer/
  SKILL.md`, real content is under `§Auto-Detection Rules`), plus a `design.md` that was never
  part of this repo. Corrected to the live paths.

## [0.1.11] - 2026-09-22

- **Docs**: added a `## Quickstart` section, replacing a stale "will be added once published to a
  marketplace" placeholder (the `renfordn-plugins` marketplace already exists and is documented in
  `docs/install-and-verify.md`); clarifies this plugin's skill is distinct from Claude Code's own
  built-in `/code-review` command.
- **Chore**: `.claude-plugin/plugin.json`'s `first_class.declared_absent` extended to include
  `commands` and `agents` (was just `hooks`) — this plugin is deliberately a skill, not an agent
  (see README's "Why this is a skill, not an agent"), and adding its own slash command would
  collide with Claude Code's built-in `/code-review`.

## [0.1.10] - 2026-09-22

- **Fix**: `tests/test_interop_review_level.py` and `tests/test_skill_review_levels.py` hardcoded an absolute `/Users/jay.nelson/...` path to read `INTEROP.md`/`SKILL.md`, so both failed with `FileNotFoundError` on any other machine — confirmed breaking on GitHub Actions' CI runner. Made both paths relative to `Path(__file__)`.

## [0.1.9] - 2026-09-20

- **Docs**: promote unpromoted Unreleased CHANGELOG section to versioned [0.1.8] entry.

## [0.1.8] - 2026-09-20

- **Release**: bump version for public release pass.

## [0.1.1] - 2026-08-16

- Re-added `agent-ux:ux-agent` delegation for the review-dashboard, this time genuinely optional
  and not SDD-specific scaffolding (0.1.0 removed the prior, SDD-coupled version of this for
  exactly that reason — see its entry below; this doesn't reopen that decision). Delegates only
  when a caller supplies the new optional `phase_state` invocation parameter (a compact phase
  token like `agent-isdd`'s `Design`, or `TDD:green` — this skill has no phase concept of its own
  and never invents one) **and** `agent-ux:ux-agent` is installed this session; otherwise opens
  the Artifact directly, exactly as before, with identical findings and identical threshold logic
  either way. Marked `code-reviewer/skills/code-reviewer/SKILL.md`'s "Visual Review" section as
  the canonical definition of the 5-finding/1-file dashboard threshold that `agent-ux` and
  `agent-isdd`'s `doc-consistency-auditor` both mirror, closing a prior three-way duplication with
  no shared source. Added `Agent` to the skill's tool references, used only for this delegation.

## [0.1.0] - 2026-08-11

- Extracted from `spec-driven-development`'s internal `code-reviewer` skill into a standalone
  plugin, mirroring how `agent-nelly` (memory) and `agent-tdd` (implementer agents) were already
  pulled out of SDD.
- Replaced the hardcoded `~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/` persistence
  path with an optional caller-supplied **review state directory**. When omitted, the skill stays
  ephemeral for a single pass (same tier/decision rules, no persistence) instead of assuming SDD's
  memory tree exists.
- Removed the `ux-agent` delegation for the review-dashboard Artifact and for out-of-scope
  `spawn_task` flags — since this skill runs in the main thread (not an isolated subagent), it
  can call `Artifact`/`spawn_task` directly itself, so the delegation was SDD-specific
  scaffolding, not a hard requirement.
- Replaced the reference to `workflow-manager`'s Review State Repair rules with a self-contained
  staleness check the skill owns itself (diff-fingerprint mismatch → downgrade to
  `needs_detailed_review`), since no `workflow-manager` exists standalone.
- SDD's own internal copy of `code-reviewer` is unchanged for now — this plugin ships standalone
  alongside it rather than replacing it, matching the same migration decision already made for
  `agent-tdd` (full cutover deferred).
