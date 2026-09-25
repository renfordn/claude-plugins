---
name: code-reviewer
description: Review code for bugs and risks before it's merged, shipped, or committed. Use whenever the user wants code checked, however they phrase it — "look over this", "any bugs in this?", "is this safe to ship/merge?", "sanity-check my change", "review this file/diff/PR/branch/function" — including a pasted snippet, a yes/no "can this go out?" question, and cases where the problem looks obvious, since the finding still needs a tier and a decision. For a PR or branch, use it rather than reviewing directly: it also finds callers of changed code across the repo, behavior changes no test covers, and gives a cleanup/consolidation plan. Also at pre-commit and TDD review gates. Gives each finding an evidence tier and a decision (accept/flag/block), reported via ReportFindings. Not for explaining how code works; use code-brief for that.
---

# Code Reviewer

Claude-native review skill. Tools: `Bash`, `Read`, `Grep`, `Glob`, `Write` (findings.json only), `ReportFindings`, `Artifact`, `Agent` (delegation only). Invocable directly, mid-TDD, or pre-commit. No hard dependency on any plugin — standalone-capable with an optional review-state location.

## Start Here

Before reading any code, size the change (Review Pipeline step 1). On a `large` diff (>400
changed lines or >10 files) one pass is not enough, and you must run the sweep in step 6: a
single read of a long diff skims the repetitive parts, and which defect slips through changes
from pass to pass (a handler missing its siblings' guard, a one-character loop bound in a
refactor). Then follow the Review Pipeline in order.

## Use This Skill When

- The user explicitly asks for a code review (`direct-review`).
- An implementer agent reaches a mandatory pre-refactor review boundary — the orchestrating skill runs this review before resuming the agent (`review-improve`).
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
decision.

### `pre-commit`

Triggered immediately before a commit, by whatever mechanism the calling workflow uses to gate
commits, or by explicit user request. Scope: the full staged diff. Any `tier-1`/`tier-2` finding
with `workflow_action: block_commit` prevents the commit until resolved or explicitly overridden.

## Review Pipeline

Most real defects in a PR sit where the diff meets code it didn't touch: a caller still using the
old signature, an import of something that moved, logic that already exists elsewhere, behavior
that changed with no test watching it. Reading the diff alone misses all of them, and on a large
PR one context can't hold everything anyway. So every review at `Standard` or above runs these
steps (`Quick` does 1, 5 and 7–9 only):

1. **Plan.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review_plan.py" plan [--base <ref>]`
   (`--diff-file <path>` for a saved diff). It prints files ranked by risk, symbols that changed
   signature, were removed, or are new, candidate tests per source file, `test_gaps`, review
   `groups`, and whether the diff is `large` (>400 changed lines or >10 files, docs/lockfiles
   excluded). No shell? Derive the same by reading the diff: changed files, `def`/`class`/
   `function` lines added, removed or altered, and the test files beside each source file. Treat
   the diff as `large` on the same thresholds (count `+`/`-` lines and files), and group files by
   directory, riskiest first.
2. **Context step.** For every changed signature and removed symbol, search the *whole repo*
   (`Grep` for the name) for callers and importers, including files the diff never touched, and
   read each call site. A caller left on the old shape is a `correctness` finding at tier-1/2,
   since you read both sides. Read the candidate tests for each reviewed file too.
3. **Fan out when `large`.** Spawn one `code-reviewer:code-reviewer` agent per group, all in one
   message so they run in parallel; brief each with its group's files, the plan entries for those
   files, and `review_level`. Then spawn `code-reviewer:cross-file-reviewer` with the full plan and
   each group's finding titles; it owns steps 2 and 8 across groups. Not large: one reviewer does
   everything. If agents can't be spawned, review the groups in sequence yourself, riskiest first.
4. **Test gaps.** Go function by function through every changed function (all of `test_gaps`,
   or every touched function if you had no plan): what behavior is new, and which test exercises
   that new behavior, not just the old path? Read the tests to answer. No such test → one
   `category: test-coverage`, `workflow_action: require_test` finding *for that function*, naming
   the concrete case to add (e.g. `parse_date("")` now raises ValueError instead of returning None). One
   finding per function, never a single catch-all "coverage is thin" remark — that is the version
   nobody acts on. Pure renames/refactors need no finding.
5. **Merge and dedupe** across reviewers per the anti-blur rules; rank most-severe first.
6. **Sweep until dry** (`large` diffs, and any `Deep`/`Ultra` review). Go back over the diff one
   file at a time — every changed hunk, especially the ones that looked mechanical — asking only
   "what here haven't I reported?". Best done by a fresh `code-reviewer:code-reviewer` agent
   briefed with the scope plus the titles of the findings so far and told to report only new
   ones; otherwise do it yourself, file by file, without skipping. Repeat while a sweep adds a
   finding, at most 3 sweeps. Say in one line how many sweeps ran and what each added.
7. **Verify** every gating finding and every `high`/`critical` one (INTEROP.md, "Verify pass").
8. **Cleanup plan.** Turn duplicate-logic and design findings into ordered refactor/
   consolidation steps. Before proposing a new shared helper, search for an existing one that
   already does the job and consolidate onto it. Each item becomes a `followups` entry in
   findings.json and a numbered **Cleanup plan** in your reply.
9. **Write findings.json** (below), then render.

## findings.json

The machine-readable record of a pass, for whatever acts on it next (a follow-up queue, CI, a
later review). Path: `review_plan.py findings-path [--state-dir <review-state dir>]` — the
review-state directory if one was supplied, else `<git dir>/code-review/findings.json` (never
committed). Overwrite it each pass, then check it with `review_plan.py validate <path>`.

```json
{"scope": "main...HEAD", "level": "Standard", "generated_at": "2026-09-25T10:00:00Z",
 "findings": [{"id": "F1", "file": "app/reports.py", "line": 7, "title": "Caller not updated",
   "summary": "…", "failure_scenario": "…", "category": "correctness", "severity": "high",
   "evidence_tier": "tier-1", "decision": "block", "workflow_action": "block_commit",
   "confidence": "high", "verdict": "CONFIRMED", "evidence": "read users.py:1 and reports.py:7"}],
 "followups": [{"kind": "consolidation", "title": "Use validation.normalize_email everywhere",
   "files": ["app/invites.py", "app/newsletter.py"], "why": "…",
   "steps": ["Replace _clean_email with normalize_email", "Delete sanitize_address"]}]}
```

`kind` is `refactor`, `consolidation`, or `deferred-defect` (a real defect deliberately left out
of this PR). No 32-finding cap here: `ReportFindings` gets the top 32, the file keeps everything.
No git repo and no review-state directory, or no `Write` tool: skip the file and say so in one line.

## Parameters

### `review_level`

**Type**: enum (`Quick | Standard | Deep | Ultra`) — optional; defaults to `Standard`. Controls depth of analysis and checks performed.

### Review Levels

Each level defines checks performed, skipped checks, and output style, ordered by scope and depth:

#### **Level 1: Quick (Fact-Finding)**

- **Alias**: Fact-Finding
- **Purpose**: Brief understanding of code purpose and structure; minimal essential feedback
- **Checks Performed**:
  - Basic syntax correctness
  - Function/variable naming clarity
  - Function signature coherence
  - Obvious logic errors (null checks, type mismatches)
  - Import/export completeness (at file level)
- **Skipped Checks**: Impact analysis, design patterns, security implications, performance analysis, cross-file impact
- **Output Style**: Minimal findings, high signal-to-noise ratio; focus on clarity and correctness issues only

#### **Level 2: Standard (Impact/Research) — Default**

- **Alias**: Impact/Research Analysis
- **Purpose**: Comprehensive within scope; understand code usage and cross-file impact
- **Checks Performed**:
  - All Quick level checks
  - Import/export correctness and contract consistency
  - API contract consistency
  - Naming conventions (variable, function, class)
  - Basic design coherence (functions not doing too many things)
  - SOLID-principle violations (Single Responsibility, Open/Closed, Liskov Substitution,
    Interface Segregation, Dependency Inversion) — named explicitly, not folded into generic
    "design coherence"
  - Separation of concerns problems, as their own named check
  - Duplicated logic that should be consolidated into a shared function, method, or class —
    within the diff, and against existing helpers the context step turns up
  - Callers and importers of changed or removed symbols (Review Pipeline step 2)
  - Sibling consistency: a new or changed function that lacks what its neighbours in the same
    file or module all have — an auth/permission decorator, input validation, a transaction or
    lock, error handling, a unit conversion — is a finding; copy-paste additions miss these most
  - Obvious bugs and edge cases
  - Test gaps (Review Pipeline step 4)
- **Skipped Checks**: Security vulnerabilities, performance profiling, regression risk analysis, module-wide coherence, and broader refactoring suggestions beyond the narrow duplicate-consolidation check above (those stay a Level 3/Deep concern)
- **Output Style**: Organized by finding type (correctness, naming, design); severity-tiered; typical current behavior

#### **Level 3: Deep (Coherence/Sanity)**

- **Alias**: Coherence/Sanity Checks
- **Purpose**: Validate function/class definitions and design consistency; thorough design validation
- **Checks Performed**:
  - All Standard level checks
  - Design pattern alignment (does implementation match intended patterns?)
  - Single Responsibility Principle (SRP) validation, extended beyond Standard's SOLID check into
    cross-method judgment calls a diff-scoped pass can't make
  - Interface coherence (methods group logically, no leaky abstractions)
  - Class-level design consistency
  - Module-wide coherence (do related functions form a cohesive unit?)
  - Edge case and error handling comprehensiveness
  - Refactoring suggestions (improve clarity, reduce complexity)
- **Skipped Checks**: Security-specific vulnerabilities, performance profiling, multi-module regression analysis
- **Output Style**: Design-level findings grouped by concern (SRP, interface, patterns); refactoring suggestions included; context-rich evidence

#### **Level 4: Ultra (Deep Analysis + Security)**

- **Alias**: Deep Analysis + Security/Regression Focus
- **Purpose**: Comprehensive analysis including security, performance, and regression risk; final vetting for critical code
- **Checks Performed**:
  - All Deep level checks
  - Security vulnerabilities (injection, authorization, data exposure, crypto, etc.)
  - Regression risk (could changes break existing code outside modified files?)
  - Duplicate detection (code duplication across project scope — distinct from Standard's
    diff/file-scoped duplicate-consolidation check above)
  - Performance implications (memory, I/O, CPU complexity)
  - Refactoring opportunities at whole-system scale
- **Skipped Checks**: None (comprehensive)
- **Output Style**: Full spectrum of findings, severity-tiered; separate security findings; regression risks highlighted; performance notes included

### Auto-Detection Rules

When `review_level` is not explicitly specified, the skill infers level from context using this priority order:

1. **Explicit request** (highest priority): If caller explicitly states a level, use it
2. **ISDD workflow phase** (if available in caller context) — *What to review* per phase:
   - Requirements → `Standard` (EARS formatting, scope, non-goal conflicts)
   - Design → `Deep` (patterns, file touchpoints, slice feasibility)
   - Tasks → `Standard` (phrasing, Depends-On graph, validation steps)
   - Impl per-slice (Red) → `Quick` (test intent, acceptance criteria)
   - Impl per-slice (Green) → `Standard`; `Deep` if `risk_tier: high_risk`
   - Impl post-slices (Coherence) → `Deep`; `Ultra` if majority high-risk slices and multi-agent available
3. **File scope** (if available):
   - Single function → `Quick`
   - Single file → `Standard`
   - Multiple files → `Deep`
   - Entire module/subsystem → `Ultra`
4. **Prior context** (if reviewing same code multiple times):
   - Escalate by one level: `Quick` → `Standard` → `Deep` → `Ultra`
   - User can override by explicit re-request
5. **Fallback** (lowest priority): `Standard` (balanced, comprehensive-within-scope, existing behavior)

### Graceful Degradation

If a level is unavailable (e.g., `Ultra` without multi-agent): degrade to next-lower, notify caller. Never block or auto-upgrade. User always gets some review.

## Visual Review

- **Default**: report findings through the `ReportFindings` tool — host-native structured
  rendering, no HTML to author, the cheapest option and the default for every mode/size.
- **Above threshold**: when a pass has more than 5 findings or touches more than one file, open a
  redeployable review-dashboard (findings as resolvable cards next to their diff hunks). This is
  what makes the review something the user resolves *with* the agent, turn by turn, instead of
  reading a static list: as findings get discussed and resolved in the conversation, redeploy the
  same dashboard in place to reflect the current state, rather than reposting it. Open it directly with the `Artifact` tool. **This is the
  canonical definition of the 5-finding/1-file threshold** — `agent-isdd`'s
  `doc-consistency-auditor/SKILL.md` cites it only to explicitly opt out (always
  `ReportFindings`-only); if it changes here, update that note to match.
- Below the threshold, `ReportFindings` alone is sufficient visual structure — do not open a
  dashboard just for its own sake; that's exactly the token cost the
  threshold exists to avoid.
- If review turns up something concrete but genuinely outside the diff's scope (dead code, a
  stale doc, a confirmed TODO unrelated to this change) — not a finding against the change
  itself — flag it. Only for issues you've already confirmed are real and out of scope; never for
  a low-confidence hunch. Call `spawn_task` directly.
  - If a review-state directory was supplied, append a row to that directory's
    `TODO-LEDGER.md` (`references/TODO-LEDGER.md.template`) immediately after the call returns
    its `task_id` — `code-reviewer` is the only writer of this file. No review-state directory:
    skip the ledger, same ephemeral-pass discipline as `REVIEW-STATE.md`.
  - If a later pass finds a ledger row's item stale, superseded, or already handled: call
    `dismiss_task` with its `task_id`, then flip that row's `Status` to `dismissed` in place
    (never delete the row).

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
  `performance` | `documentation`. SOLID-principle, separation-of-concerns, and
  duplicate-consolidation findings (Standard level and above) map to `category: architecture` —
  no new enum value.
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

## Output Shape (per finding)

Internally, each finding carries: `id`, `title`, `locations`, `evidence_tier`,
`decision`/`severity`/`category`/`workflow_action`/`confidence`, `evidence` (what was read or run
to support the tier), `resolution_note`. These are the *review record* — they live in the
dashboard, `REVIEW-STATE.md`, and your reasoning. They are **not** `ReportFindings` fields.

## ReportFindings Payload (the handover)

`ReportFindings` validates its input with a strict schema and rejects the **entire** call if one
field is over its limit — the user then sees "Failed to report review findings" and nothing
renders. The model builds this JSON by hand, so there is no validator to lean on: budget each
field as you write it.

Accepted fields per finding — anything else is dropped or rejected:

| Field | Limit | Put here |
|---|---|---|
| `file` (required) | repo-relative path | first entry of `locations` |
| `line` | integer | first line of that location |
| `short_summary` | **≤ 60 chars, hard** | the claim alone, ~8 words. No rationale, no tier/severity tags, no file path |
| `summary` (required) | one sentence, aim ≤ 200 chars | `[severity · tier-N · decision] ` prefix, then the defect in one sentence |
| `failure_scenario` (required) | 1–2 sentences | concrete input/state → wrong output/crash; for non-bug findings, the concrete cost |
| `category` | ≤ 40 chars, kebab-case | the Decision Model `category` |
| `verdict` | `CONFIRMED` \| `PLAUSIBLE` | Only after a verify pass (INTEROP.md, "Verify pass"): `CONFIRMED` if upheld, else `PLAUSIBLE`. Omit when no verify pass ran |

Top-level: `findings` (ranked most-severe first, **max 32**), and `level` mapped from
`review_level` — Quick→`low`, Standard→`medium`, Deep→`high`, Ultra→`xhigh`.

Everything else (`evidence`, `workflow_action`, `confidence`, `resolution_note`, extra
locations) stays out of the payload. If it matters to the user, it goes in the dashboard or one
line of follow-up text — not stuffed into `summary`.

Example of a well-formed finding (after a verify pass upheld it):

```json
{"file": "src/cache.py", "line": 88, "category": "correctness", "verdict": "CONFIRMED",
 "short_summary": "TTL check uses < so entries expire one tick late",
 "summary": "[high · tier-1 · block] Expiry compares now < ttl instead of now <= ttl, keeping stale entries alive.",
 "failure_scenario": "Entry with ttl=100 read at t=100 returns stale data instead of a miss."}
```

Before calling:

1. Count every `short_summary` — if any is over 60, rewrite it shorter (don't just chop mid-word).
2. More than 32 findings? Merge `nit`/`low` items per the anti-blur rules, and move the rest to
   the dashboard (which the >5-finding threshold already requires); findings.json keeps all.
3. If the call still fails with a validation error, read the `path` in the error (e.g.
   `findings.1.short_summary`), fix that field, and call again. Don't give up and dump findings
   as prose — a failed handover means the caller gets nothing structured.

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
