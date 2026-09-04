<!-- TDD-SKIP -->
# Manual Validation Runbook — Agent Nelly Phase 9

This is the literal, step-by-step script for the parts of Phase 9 that require a
**live Claude Code session** driving the `nelly-orchestrator` subagent and the
`/nelly-memory` slash command — the promotion-bucket judgment, consolidation,
prune-via-command, and import-via-command fixtures. These cannot be executed by a
sandboxed subagent invoking another subagent; a human or a live top-level session must
run this.

Everything in this runbook was reconstructed from `tasks/tasks.md` (Phase 7/8 Test
Intent), `design.md`'s Validation Strategy, `REVIEW-HISTORY.md`'s fixture references
(Fixture Set 1, Fixture Set 2, Fixture B), and the shipped `agents/nelly-orchestrator.md`
/ `commands/nelly-memory.md` text (which quotes some of the same examples verbatim,
e.g. the bucket 1/2 examples below). The original test-author fixture artifact from
Phase 7/8 was not persisted as a separate file in SDD memory, so this is a
reconstruction faithful to those sources, not a verbatim replay of a saved fixture doc
— note this if a fixture's exact wording matters later.

## Prerequisites

1. Install agent-nelly as a local plugin (per its `.claude-plugin/plugin.json`) in a
   throwaway scratch project directory with **no SDD plugin present**.
2. Confirm `NELLY_GATE` is unset (guardrail hooks active, not bypassed).
3. Have a second, unrelated scratch project directory available for the promotion
   fixtures (Bucket 1 promotion needs at least a "this project" and "global" to
   distinguish from).

---

## Fixture Set — SessionStart / empty project (Phase 9 step 2-3, sanity re-check)

Already executed non-interactively by `agent-TDD` (see handoff report) — re-run only if
the live session's `SessionStart` output looks different from the hook's raw JSON
output, to isolate a plugin-wiring problem from a hook-logic problem.

- **Command:** start a session in the empty scratch project.
- **Pass:** `SessionStart` context shows the memory root path and
  `Intent: not yet captured`, no entries/global sections, no errors.
- Then: `/nelly-memory view`
- **Pass:** replies exactly `No memory recorded yet for this project.` — no error, no
  partial brief, no traceback.

---

## Fixture Set 1 — Promotion buckets A/B/C

Seed each fact via `/nelly-memory` triggering `nelly-orchestrator`'s "Recording a new
fact" path (brief assembly with a `new fact` input), one at a time, then run
`/nelly-memory view` afterward to read `Written`.

### A — Bucket 1, clearly generalizable (expect: promote)

- **Seed fact (verbatim, matches the agent's own worked example):**
  > "A Python subprocess writing to stdout when stdout isn't a tty can buffer and
  > silently delay/drop output unless `flush=True` or `-u` is used."
- **How to trigger:** ask the orchestrator (via whatever caller surface passes `new
  fact` — e.g. a task description like "remember this: <fact>") to record this fact.
- **Pass conditions:**
  - A new entry file appears under `<memory_dir>/entries/<name>.md` in
    `nelly-entry.template.md`'s shape.
  - `global/GLOBAL-MEMORY.md` gains one new frontmatter block for this fact.
  - `global/GLOBAL-PROMOTION-LOG.md` gains exactly one new block:
    `Action: promoted`, `Entry: <name>`, `Source Project(s): <this project's slug>`,
    a `Reason:`, `Trigger: brief-assembly` (or `user request`).
  - `Written` in the brief mentions the promotion.
  - No project name, file path, or person's name appears in the global-tier text (this
    fact has none to begin with — confirms the "clean" case).
- **Fail if:** no promotion happens, `GLOBAL-MEMORY.md` is rewritten/reordered instead
  of appended, or more than one promotion-log block is added.

### B — Bucket 2, clearly project-specific (expect: stays local, no action)

- **Seed fact (verbatim, matches the agent's own worked example):**
  > "The agent-nelly plugin's `nelly_slug_guard.py` denies writes whose path segment
  > doesn't match `project_slug(cwd)` for the active agent-nelly project root at
  > `/path/to/agent-nelly`."
- **Pass conditions:**
  - A new entry file appears under this project's `entries/` as normal.
  - `global/GLOBAL-MEMORY.md` and `global/GLOBAL-PROMOTION-LOG.md` are **byte-for-byte
    unchanged** (diff before/after).
  - `Written` records no promotion action for this entry (or explicitly notes it
    stayed local — no ambiguity).
- **Fail if:** anything is appended to either global-tier file for this entry.

### C — Bucket 3, still identifying after generalization (expect: skip + explain, never leak)

- **Seed fact (construct one that only generalizes down to something that still
  exposes a person or a private path):**
  > "Jay always structures his personal dotfiles repo at
  > `/Users/jay.nelson/dotfiles-private` with a `secrets/` folder that must never be
  > committed — this convention only makes sense because of how his personal machine
  > is set up."
- **Pass conditions:**
  - A new entry file appears under this project's `entries/` as normal (recording
    still happens locally).
  - `global/GLOBAL-MEMORY.md` and `global/GLOBAL-PROMOTION-LOG.md` are unchanged.
  - `Written` explicitly states promotion was considered and skipped, with a
    **category-level** reason (e.g. "tied to a personal authoring convention and
    identifying paths that don't generalize") and contains **none** of: the string
    `Jay`, the string `dotfiles-private`, or the literal home-directory path.
- **Fail if:** `Written`, `GLOBAL-MEMORY.md`, or `GLOBAL-PROMOTION-LOG.md` contains the
  name "Jay", the path `/Users/jay.nelson/...`, or "dotfiles-private" verbatim anywhere.

---

## Fixture Set 2 — Staleness (prune, archive-not-delete)

### Seed

Create this file directly under `<memory_dir>/entries/legacy-cache-invalidation-note.md`
(matches `nelly-entry.template.md`'s shape, backdated `last_referenced`):

```markdown
---
name: legacy-cache-invalidation-note
description: Old note about a cache-invalidation quirk in a since-removed subsystem.
metadata:
  type: project
  last_referenced: 2020-01-01
---

Why: kept around from an earlier investigation; likely no longer relevant.
How to apply: n/a — candidate for staleness sweep.
```

### Command

```
/nelly-memory prune --threshold-days 0
```

### Pass conditions

- `legacy-cache-invalidation-note.md` **no longer exists** under `entries/`
  (`list_entries(cwd)` / `ls entries/` confirms).
- `legacy-cache-invalidation-note.md` **does exist**, byte-identical in content, under
  `archive/`.
- The project's `MEMORY.md` index no longer lists this entry's line; all other index
  lines untouched.
- Command reply names the archived entry, the threshold, and states explicitly it was
  moved (not deleted) and is recoverable.
- **Recoverability check:** manually `mv archive/legacy-cache-invalidation-note.md
  entries/` and confirm `list_entries()` sees it again — proves it's a real, reversible
  move, not a destructive operation.

### Fail if

Any hard delete is observed (file gone from both `entries/` and `archive/`), or the
file's content differs from the original at its new path.

---

## Fixture Set — Consolidation (two overlapping entries → one merge + 2 archived + 1 log line)

### Seed

Create these two files directly under `<memory_dir>/entries/`:

`retry-on-flaky-network-calls.md`:
```markdown
---
name: retry-on-flaky-network-calls
description: Retry flaky network calls rather than failing immediately.
metadata:
  type: project
  last_referenced: 2026-08-01
---

Why: transient network failures shouldn't fail the whole operation.
How to apply: wrap flaky calls in a retry loop with a small fixed delay.
```

`backoff-strategy-for-http-timeouts.md`:
```markdown
---
name: backoff-strategy-for-http-timeouts
description: Use exponential backoff when HTTP calls time out.
metadata:
  type: project
  last_referenced: 2026-08-01
---

Why: naive fixed-delay retries can thundering-herd a recovering service.
How to apply: back off exponentially between retries on HTTP timeout.
```

### Command

```
/nelly-memory consolidate
```

### Pass conditions

- Exactly **one new entry** appears under `entries/` with a **new** name (not reusing
  either original filename), reconciling both facts (retry + exponential backoff for
  transient/timeout failures) into one coherent body.
- Both `retry-on-flaky-network-calls.md` and `backoff-strategy-for-http-timeouts.md` no
  longer exist under `entries/`, but **do** exist, unmodified, under `archive/`.
- `<memory_dir>/CONSOLIDATION-LOG.md` exists (created from
  `GLOBAL-CONSOLIDATION-LOG.md.template`'s shape) and has **exactly one new block**:
  `Action: consolidated`, `Merged Entries: retry-on-flaky-network-calls,
  backoff-strategy-for-http-timeouts` (either order), `Result Entry: <new-name>`,
  `Reason:`, `Trigger: user request via /nelly-memory consolidate`.
- `MEMORY.md` index: one new line for the merged entry, the two originals' lines
  removed, all other lines untouched.
- Command reply names both originals, the new merged name, and states the
  archive-not-delete + logging guarantee explicitly.

### Fail if

More than one merged entry is produced, either original is missing from `archive/`, or
more than one log block is appended.

---

## Fixture Set — Intent alignment A/B

### A — Aligned

- Pre-seed `MEMORY.md`'s `Intent:` line (or whatever this project's index currently
  has) to something concrete, e.g.:
  `Intent: build a CLI that converts CSV exports into normalized JSON for a downstream billing pipeline.`
- Run `/nelly-memory view "add input validation to the CSV parsing step"`.
- **Pass:** `Intent alignment` is one short affirmative sentence with no manufactured
  caveats (e.g. "Aligned: this task fits within the stored Intent's scope.").

### B — Diverges

- Same stored Intent as above.
- Run `/nelly-memory view "add a real-time WebSocket chat feature to the dashboard"`.
- **Pass:** `Intent alignment` names **both** subjects (the CSV/billing Intent and the
  WebSocket chat task) joined by an explicit contrast connector ("diverges because…",
  "no connection to…", "outside the scope of…") — not a bare "not aligned".

### Fail if

Either case produces a bare yes/no with no subject-naming, or the divergent case
invents an alignment that doesn't exist.

---

## Fixture — `nelly-memory view` (empty and populated)

- **Empty:** covered above (Prerequisites' fresh scratch project) — pass condition:
  exact string `No memory recorded yet for this project.`
- **Populated:** after any of the above seeds exist, run bare `/nelly-memory view` (no
  task description).
  - **Pass:** `Relevant entries: none requested this call` (no task description was
    given, so the surface-relevant-memory flag must NOT be set); `Intent` and `Intent
    alignment` still populate normally; command never prints raw entry-file contents
    (spot-check: none of the seeded entries' full body text appears verbatim in the
    reply, only name/description-level summaries).
  - Then run `/nelly-memory view "working on retry logic"` (with a task description).
    - **Pass:** `Relevant entries` now surfaces the consolidated retry/backoff entry
      (or original entries if consolidation fixture wasn't run first) with a condensed
      `name — description` line, and that entry's `metadata.last_referenced` is
      updated to today's date (confirm by re-reading the entry file directly after the
      call).

---

## Fixture — `nelly-memory import` (with and without `--force`)

### Seed

Create a scratch source directory (not under the memory root) with two plain markdown
files:

`import-source/docker-compose-local-dev-setup.md`:
```markdown
Run `docker compose up -d db redis` before starting the app locally. The app expects
Postgres on 5432 and Redis on 6379; both are defined in `docker-compose.yml` at the
repo root.
```

`import-source/pre-commit-hook-notes.md`:
```markdown
The pre-commit hook runs `ruff check` and `mypy` on staged Python files only. If it's
slow, it's usually mypy re-checking the whole package instead of just staged files —
check the hook's `files:` filter first.
```

### Command (first pass, no `--force`)

```
/nelly-memory import import-source
```

### Pass conditions (first pass)

- Exactly **two** new entry files appear under `entries/`:
  `docker-compose-local-dev-setup.md` and `pre-commit-hook-notes.md` (name derived from
  filename, extension stripped).
  Alternatively, if consolidation/promotion already created entries with those exact
  names, note the collision and adjust file names for this fixture run.
- Each entry's `description` is a real, specific summary of that file's actual content
  (not a generic "Imported from `<filename>`" placeholder) — spot-check by reading both
  new entry files.
- `metadata.last_referenced` is today's date on both.
- Reply reports both as created.

### Command (second pass, re-import same dir, no `--force`)

```
/nelly-memory import import-source
```

- **Pass:** both files reported as **skipped** ("already exists; use `--force` to
  overwrite"); both existing entries are byte-for-byte unchanged (diff before/after).

### Command (third pass, with `--force`)

Edit `import-source/pre-commit-hook-notes.md` to change its content, then:

```
/nelly-memory import import-source --force
```

- **Pass:** `docker-compose-local-dev-setup.md`'s entry is also overwritten (or
  reported overwritten — confirm both entries actually got reported, not silently
  skipped since `--force` applies to all colliding files this pass) with a freshly
  synthesized `description`/`last_referenced`; reply reports both as overwritten.

### Fail if

Entry count doesn't match source file count 1:1, a skip silently modifies the existing
entry, or `--force` doesn't actually change content/timestamp.

---

## Fixture Set — Batch fact write-back (`new facts`, in-batch dedup)

Added for the 0.1.5 batch write-back extension (`new facts`, plural) — not yet run live;
this fixture set follows the same convention as the others above and should be executed
the same way (a live session, or an `EnterWorktree`-provided real scratch cwd).

### G — Three facts, one duplicate pair, one singleton (expect: 2 entries written, not 3)

- **Seed (pass as a single `New facts:` block, three items):**
  1. "The `orders` table's `status` column migration to an enum type is owned by the
     billing-service folder, not the checkout-service folder."
  2. "Ownership of the `orders.status` enum migration lives in billing-service, not
     checkout-service — checkout-service only reads it."
  3. "The `/health` endpoint has no test coverage at all currently."
- **How to trigger:** one `nelly-orchestrator` call with a `New facts:` block listing all
  three items verbatim (not three separate calls).
- **Pass conditions:**
  - Items 1 and 2 are judged an in-batch duplicate pair (same underlying fact — ownership
    of the `orders.status` migration — from two different phrasings) and result in
    **exactly one** merged entry, not two.
  - Item 3 is a singleton and results in its own separate entry.
  - **Exactly two** new entry files total appear under `entries/` (not three).
  - `Written` names the merge explicitly (e.g. "Merged 2 in-batch duplicate facts into
    `<name>`.") and separately reports the singleton entry.
  - The merged entry's body reconciles both phrasings' content (folder ownership +
    directionality) rather than just keeping one phrasing and discarding the other.
  - Promotion judgment still ran independently on each of the two final entries (both are
    Bucket 2 here — project-specific folder ownership — so neither should promote; confirm
    `global/GLOBAL-MEMORY.md` and `global/GLOBAL-PROMOTION-LOG.md` are unchanged).
- **Fail if:** three entries are written instead of two, the merge silently drops one
  phrasing's content instead of reconciling both, or promotion runs once for the whole
  batch instead of once per final entry.

### H — Batch with no duplicates (expect: N singletons, no merge)

- **Seed:** two facts about clearly unrelated subjects (e.g. one about a build-script
  quirk, one about a naming convention in an unrelated module).
- **Pass:** two separate entries, no merge language in `Written`, each promoted/skipped
  independently on its own Bucket judgment.

### I — Partial failure independence

- **Seed:** a batch of two facts where one item's write can be made to fail after its
  retry (e.g. simulate by revoking write permission on `entries/` mid-batch, or another
  reliable failure injection available in the live session).
- **Pass:** the failing item is reported as failed in `Written` with the entry it would
  have been; the other item is still written and promoted normally — the whole batch does
  not abort because one item failed.

### Fail if (whole set)

Any single-call batch produces the same result as N separate single-fact calls would have
(no dedup ever triggers even when items are clear duplicates), or a batch is processed
as all-writes-then-all-promotions instead of per-entry write-then-promote.

---

## Fixture Set — Index-line pre-filter for "Relevant entries" step 1 (Phase 4, token-efficiency, high-risk)

Written by `test-author` per the `2026-08-10-agent-nelly-token-efficiency` feature's Phase 4
Test Intent, **before** step 1's prose is changed. This is a Red fixture set: run today,
against the shipped `agents/nelly-orchestrator.md`, none of J/K/L/M can pass for the intended
reason, because current step 1 (lines 163-165 as of this writing) reads:

> "Read the project's `entries/` directory (`Glob`/`Grep` over `entries/*.md` frontmatter) and
> compare each entry's `description` field against the caller's task description for topical
> overlap."

This has **zero** reference to `MEMORY.md` or its index-line fields anywhere in step 1 — every
candidate entry's file is opened unconditionally today. That is confirmed by static read of the
current file, not a live run (this is prose consumed by an LLM subagent, not executable code —
per this agent's own instructions, "Red" here means the fixture cannot currently be satisfied
for the right reason, not a pytest failure). Fixtures J and L below note a specific nuance:
their **final surfaced output** already matches today's baseline (today opens every file
unconditionally, which is a superset of what these fixtures require) — see each fixture's own
"Why this is still Red today" note for how the assertion is scoped to avoid a false pass.

Once Phase 4's prose change lands, re-run this set live (same worktree-harness pattern as every
other set in this file) as this feature's Task 4 Validation Target, then update Status below.

### Prerequisites (same as top of file, restated for this set)

- A real, distinct working directory (`EnterWorktree`), since `hooks/nelly_slug_guard.py`
  recomputes `project_slug()` from the real invocation cwd.
- Phase 2 and Phase 3 of this feature complete first (`write_index_line()` exists and
  `agents/nelly-orchestrator.md`'s write-back paths already produce field-annotated lines) —
  otherwise there is no field-annotated `MEMORY.md` content to seed these fixtures with.
- Seed entries and `MEMORY.md` lines directly on disk (matching `nelly-entry.template.md`'s
  shape and `write_index_line()`'s documented line format
  `` - [Title](entries/<name>.md) — <hook> `[type:<t> confidence:<c> files:<f>]` ``), rather than
  via a live write-back call, so each fixture's index line can be set to a precise, deliberately
  chosen (including deliberately stale, for fixture M) value.

### J — Old-format index line, no field block (expect: fallback opens the file, unchanged behavior)

- **Seed entry** `entries/config-loader-mode-quirk.md`:
  ```markdown
  ---
  name: config-loader-mode-quirk
  description: The legacy widget config loader silently ignores the enabled flag when mode is unset.
  metadata:
    type: project
    last_referenced: 2026-07-01
  ---
  ```
- **Seed `MEMORY.md` line (old format, no trailing field block):**
  `- [Config Loader Mode Quirk](entries/config-loader-mode-quirk.md) — legacy widget config loader ignores enabled flag when mode unset`
- **Trigger:** `surface relevant memory: true`, `task description`: "investigate why the widget
  config's enabled flag isn't being respected".
- **Pass conditions (post-implementation only):**
  - The entry surfaces in `Relevant entries` as `Config Loader Mode Quirk — <description>`, and
    `metadata.last_referenced` is updated to today.
  - The transcript/tool-call trace shows the agent explicitly reading `MEMORY.md`'s line for this
    entry, finding no trailing field block, and treating that absence as the reason it opened
    `entries/config-loader-mode-quirk.md` unconditionally — i.e. the fallback is a deliberate,
    traceable branch, not an accident of "we open everything anyway."
- **Why this is still Red today:** today's step 1 never consults `MEMORY.md` at all, so it
  cannot produce the second Pass condition's trace (there is no instruction to check the index
  line's field block, so no reasoning step exists for "found no field block, therefore..."). The
  final surfaced text would look identical today only because today's Glob/Grep opens every
  entry unconditionally regardless of any index line — that coincidence is exactly why this
  fixture's assertion is scoped to the trace, not just the final output, to avoid a false pass.

### K — New-format index line, definite non-candidate by `type` field alone (expect: skip without opening the file)

- **Seed entry** `entries/personal-terminal-theme-preference.md`:
  ```markdown
  ---
  name: personal-terminal-theme-preference
  description: Jay prefers a solarized-dark terminal theme with a 14pt monospace font.
  metadata:
    type: user
    last_referenced: 2026-07-15
  ---
  ```
- **Seed `MEMORY.md` line (new format):**
  `` - [Personal Terminal Theme Preference](entries/personal-terminal-theme-preference.md) — Jay's terminal theme preference `[type:user]` ``
- **Trigger:** `handoff surfacing: true` (no `surface relevant memory`), `task description`:
  "review the file-relevance context for the config-loader refactor handoff".
- **Pass conditions (post-implementation only):**
  - Under `handoff surfacing`'s existing type restriction (only `file-relevance` and
    `explicit`-confidence `error-prevention` entries are eligible — unchanged by this task), a
    `type: user` entry is a definite non-candidate.
  - The transcript/tool-call trace shows this determined **from the `MEMORY.md` index line's
    `type:user` field alone** — `entries/personal-terminal-theme-preference.md` is never opened
    (no `Read`/`Grep` tool call against that path appears in the trace).
  - `Relevant entries` does not mention this entry's name or description anywhere.
- **Why this is still Red today:** today's step 1/2 determine `metadata.type` eligibility only
  by opening the entry file's frontmatter (Glob/Grep over `entries/*.md` frontmatter, per the
  current prose quoted above) — there is no code path today that can rule an entry out from the
  index line alone, so a trace showing zero `Read`/`Grep` calls against this entry's file is
  currently impossible to produce; today's trace would show the file opened.

### L — New-format index line, plausible candidate (expect: file opened, exclusion gate runs exactly as before)

- **Seed entry** `entries/flaky-integration-test-retries.md`:
  ```markdown
  ---
  name: flaky-integration-test-retries
  description: Retrying a flaky integration test without isolating the shared test-db fixture just reproduces the same failure.
  metadata:
    type: error-prevention
    confidence: explicit
    last_referenced: 2026-07-20
  ---
  ```
- **Seed `MEMORY.md` line (new format):**
  `` - [Flaky Integration Test Retries](entries/flaky-integration-test-retries.md) — flaky integration test retry pitfall `[type:error-prevention confidence:explicit]` ``
- **Trigger:** `surface relevant memory: true`, `task description`: "the integration test suite
  keeps failing intermittently, need to fix the flakiness".
- **Pass conditions (post-implementation only):**
  - The index line's fields (`type:error-prevention confidence:explicit`) do not make this a
    definite non-candidate, so `entries/flaky-integration-test-retries.md` is opened (a
    `Read`/`Grep` call against that path appears in the trace).
  - Step 6's exclusion gate runs against the **file's own** `metadata.confidence` (not the index
    line's `confidence:explicit` field taken on faith) — trace shows the gate check reading the
    opened file's frontmatter, confirms `explicit`, and the entry surfaces normally as
    `Flaky Integration Test Retries — <description>`.
- **Why this is still Red today:** today's step 1 already opens every file unconditionally, so
  the file-open half of this fixture trivially "passes" today for the wrong reason (no
  index-based decision was made — everything is always opened). What cannot be produced today is
  any trace evidence that the index line's fields were consulted at all before that open; today
  there is no such consultation step to trace.

### M — New-format index line with drifted/missing `confidence` field, real frontmatter is `inferred` (expect: gate excludes via the real file, index never trusted as a shortcut)

This is the fixture that directly targets design.md's named Risk 1 ("index-line fields could
drift out of sync with actual entry-file frontmatter if a write-back path is missed") and this
task's explicit guardrail: the index field must never be used to award false confidence that an
entry is safe to surface without step 6's gate actually running against real content.

- **Seed entry** `entries/network-retry-masks-outage.md` (deliberately **not** yet confirmed —
  still `inferred`):
  ```markdown
  ---
  name: network-retry-masks-outage
  description: Retrying a flaky network call without exponential backoff can mask a real outage as a transient failure.
  metadata:
    type: error-prevention
    confidence: inferred
    last_referenced: 2026-08-01
  ---
  ```
- **Seed `MEMORY.md` line (new format, deliberately drifted — `type` present, `confidence`
  fragment missing, simulating a write-back path that didn't pass the entry's real confidence
  through to `write_index_line()`):**
  `` - [Network Retry Masks Outage](entries/network-retry-masks-outage.md) — network retry masking pitfall `[type:error-prevention]` ``
- **Trigger:** `surface relevant memory: true`, `task description`: "should we add retry logic to
  the network client, and what should the backoff look like".
- **Pass conditions (post-implementation only):**
  - The index line's fields do **not** rule this entry out as a definite non-candidate on their
    own (`type:error-prevention` alone, with no `confidence` fragment, is exactly the "unknown,
    must open to decide" case, matching an old-format line's treatment for this specific field —
    not "known safe to surface").
  - `entries/network-retry-masks-outage.md` **is** opened (trace shows a `Read`/`Grep` call).
  - Step 6's exclusion gate reads the opened file's real `metadata.confidence: inferred` and
    excludes the entry: no line for it appears in `Relevant entries`, its name is never
    mentioned, `metadata.last_referenced` is not updated.
- **Fail if:** the entry is skipped (or surfaced) purely on the index line's absent `confidence`
  field without the file ever being opened and step 6's gate actually running against the real
  frontmatter — either outcome reached that way would prove the pre-filter was used as an
  authority substitute for the gate rather than a hint, which is the exact failure mode this
  fixture exists to catch.
- **Why this is still Red today:** today's step 1 has no index-line consultation of any kind, so
  there is no mechanism today that could even attempt the wrong shortcut this fixture guards
  against — the fixture cannot be run meaningfully against today's prose at all (there is no
  "index says X, file says Y" comparison for today's behavior to get right or wrong, since today
  never reads the index's field block). This fixture only becomes runnable, and only becomes a
  real safety check, once Phase 4's prose exists.

### Fail if (whole set)

Step 1's changed prose ever surfaces an entry, or ever excludes/skips an entry whose exclusion
depends on `metadata.confidence`, based on the `MEMORY.md` index line's fields alone without the
real entry file being opened and step 6's gate running against its actual frontmatter. The index
line may only ever be used to skip opening a file for a **type-eligibility** determination
(fixture K) or an **unknown/must-open** determination (fixtures J and M) — never to certify an
`error-prevention` entry as confidence-safe to surface without the gate.

### Status

- [x] Executed live 2026-08-11, worktree `token-efficiency-validation`, installed plugin v0.2.1.
      Results per fixture:
  - **J (old-format fallback):** Pass. Entry surfaced correctly, `last_referenced` updated.
    Final output matches spec; the fine-grained "explicit index-consultation-then-fallback"
    trace element in the pass condition could not be independently confirmed from the returned
    transcript (only the final report + tool-use count were visible, not a full tool-call log).
  - **K (definite non-candidate skip via type):** **Did not demonstrate the intended skip.**
    `Relevant entries` correctly stayed empty (safety-equivalent outcome), but the agent's own
    explanation stated it opened `personal-terminal-theme-preference.md` despite that entry's
    index line carrying `` `[type:user]` `` — exactly the case step 1 specifies should be skipped
    without a file open. 6 tool uses were recorded, consistent with every entry being opened
    rather than one being skipped. Re-run against the pre-Phase-4 (0.2.0) orchestrator on the
    same seeded store for comparison: 5 tool uses, 37524 tokens, vs. 6 tool uses / 38069 tokens
    on 0.2.1 — no measurable improvement, and if anything a slightly larger cost, in this single
    small-scale run. **No safety violation occurred** (nothing ineligible was ever surfaced), but
    the token-savings mechanism this fixture targets did not reliably trigger in this live run.
  - **L (plausible candidate):** Pass. File opened, gate read the real file's `confidence:
    explicit`, entry surfaced correctly.
  - **M (drifted index, real gate must still exclude):** Pass, cleanly. The entry was opened
    despite its index line omitting `confidence`, and step 6's gate correctly excluded it using
    the real frontmatter (`confidence: inferred`) — the index was never trusted as a shortcut.
    This is the fixture that most directly protects the feature's core safety constraint, and it
    held.
  - **Whole-set Fail-if:** not triggered in any run — no entry was ever surfaced or excluded
    based on the index's `confidence` field alone.

---

### Before/after token comparison (same session, see Outstanding section below for full context)

Ran Fixture K's exact scenario against both the pre-Phase-4 (0.2.0, commit `50d257c`) and
post-Phase-4 (0.2.1) `nelly-orchestrator.md`, same seeded 4-entry memory store, same
`handoff surfacing` trigger:

| Version | Tokens | Tool uses |
| --- | --- | --- |
| 0.2.0 (before) | 37524 | 5 |
| 0.2.1 (after) | 38069 | 6 |

No measurable reduction — a slight increase, within likely run-to-run noise for a single sample
each, but not the improvement the design targeted. Two likely contributing factors, both honest
findings rather than noise to explain away:

1. **The orchestrator prompt file did not shrink overall.** Phase 1 removed ~23 lines, but
   Phase 2/3/4's additions (new field-block documentation, four rewritten write-back sections,
   the rewritten step 1) added more lines back than Phase 1 removed — 963 lines pre-feature vs.
   985 lines post-feature. The prompt-size lever (Lever 1) was real but got fully offset by the
   other levers' own documentation overhead at this feature's current scope.
2. **The file-skip mechanism didn't reliably fire in this run** (see Fixture K above) — with
   only one skippable entry in a 4-entry store, even a working skip would only save one file open,
   which is a small fraction of total call cost dominated by the (now slightly larger) system
   prompt itself.

Implication for future work: this feature's real payoff is likely visible only at larger memory-
store scale (many entries, most ineligible under `handoff surfacing`) where the file-skip savings
outweigh the roughly-flat prompt size — not confirmed in this small-scale live run. The
`agent-nelly-token-efficiency-scope-decision` entry in `PROJECT-MEMORY.md` should be read
alongside this result before any future feature builds further on this mechanism.

---

## Fixture F — Cross-cutting delegation grep-check (static, already run by `agent-TDD`)

Already executed mechanically (see handoff report) — re-run only to reconfirm after any
future edit to `commands/nelly-memory.md`:

```
python3 - <<'EOF'
import re
with open("commands/nelly-memory.md") as f:
    text = f.read()
# Every sentence describing a mutation (write/move/archive/overwrite/delete/create/
# update/append) must name "nelly-orchestrator" as the actor in the same sentence,
# the immediately preceding sentence, or the same list's introductory sentence.
EOF
```

- **Pass:** manual review confirms no sentence instructs the *command file itself* to
  perform a mutation without nelly-orchestrator as the named actor (report-string
  examples that quote an already-delegated action, e.g. "Report... 'Archived
  `<name>`...'", are not instructions to the command and are exempt).
- **Fail if:** any sentence tells the command to `Write`/`Edit`/move/archive/overwrite
  a memory file directly, with no nelly-orchestrator delegation stated anywhere nearby.

---

## Final sign-off

- [x] All Fixture Set 1 buckets (A/B/C) produced the expected outcome, with Bucket C
      confirmed leak-free by literal string search.
- [x] Fixture Set 2 (staleness) confirmed archive-not-delete + recoverability.
- [x] Consolidation fixture confirmed 2-in-1-out + archive + single log line.
- [x] Intent alignment A and B both produced correctly shaped output.
- [x] `view` empty and populated cases both passed.
- [x] `import` create/skip/overwrite all confirmed.
- [x] Zero hard-deletes observed anywhere in this runbook.
- [x] Zero identifying-detail leaks observed in `global/` files.
- [x] Batch fact write-back (Fixture Set G/H/I) — added in 0.1.5, run 2026-08-10.

Record actual outcomes (pass/fail per fixture, and any prompt-iteration needed on
`nelly-orchestrator.md` per Phase 9's Blockers Or Escalation note) directly in this
file or in a dated addendum once executed.

---

## Addendum — 2026-08-09 partial run

Run from a live top-level session whose actual working directory is the
`agent-nelly` repo itself (not a throwaway scratch project — see finding below).

- **SessionStart / empty project, `/nelly-memory view` (bare):** ✅ PASS. This
  repo's own Agent Nelly memory was genuinely empty (`Intent: not yet captured`,
  no entries). Bare `view` returned exactly `No memory recorded yet for this
  project.` — no error, no partial brief.
- **Fixture F (delegation grep-check):** ✅ PASS on manual review of
  `commands/nelly-memory.md` as shipped — every mutation-describing sentence
  (import/prune/consolidate write-backs) names `nelly-orchestrator` as the actor
  in the same or an immediately preceding sentence; the only bare
  Write/Edit/move/archive/overwrite mentions are either report-string examples
  (exempt) or the Cross-cutting Rules' explicit negation. No violation found.
- **Structural finding (blocks the remaining fixtures from this session):**
  attempted Fixture 1A by asking `nelly-orchestrator` to treat a scratch-project
  path as its `cwd`. The plugin's own `hooks/nelly_slug_guard.py` **correctly
  denied the write** — it recomputes `project_slug()` from the tool call's real
  invocation cwd (this session's actual cwd, the `agent-nelly` repo), not from
  any path a subagent is told to pretend is the project root. This is the guard
  behaving exactly as designed, and it also confirms the runbook's own caveat:
  these fixtures cannot be executed by a subagent role-playing a different cwd;
  they require a live session whose **real** working directory is the scratch
  project (a separate terminal/session `cd`'d into a throwaway dir, per
  Prerequisites).
- **Not yet run** (need that separate scratch-directory session): Fixture Set 1
  Buckets A/B/C, Fixture Set 2 (staleness/prune), Consolidation, Intent
  alignment A/B, `view` populated case, `import` create/skip/overwrite.

## Addendum — 2026-08-09 full run (worktree session)

Resolved the prior blocker using `EnterWorktree`, which switches the session's
*actual* working directory (not a role-played one) to a fresh git worktree —
giving `nelly_slug_guard.py` a genuinely different, empty `project_slug()` to
enforce against. All remaining fixtures ran for real from that worktree cwd.

- **Fixture 1A (Bucket 1, promote):** ✅ PASS. Entry created in the expected
  shape; `GLOBAL-MEMORY.md` gained exactly one new frontmatter block;
  `GLOBAL-PROMOTION-LOG.md` gained exactly one `Action: promoted` block with
  `Trigger: brief-assembly`; no project-identifying text in the global body.
- **Fixture 1B (Bucket 2, stays local):** ✅ PASS. Entry created locally;
  `GLOBAL-MEMORY.md` and `GLOBAL-PROMOTION-LOG.md` confirmed byte-for-byte
  unchanged by diff before/after.
- **Fixture 1C (Bucket 3, skip + explain, no leak):** ✅ PASS. Entry recorded
  locally as normal; global files unchanged (diff-confirmed — zero new bytes);
  `Written` and bucket-judgment explanation used only category-level language,
  no literal name/path/repo string. (A naive case-insensitive grep for "Jay"
  against `GLOBAL-PROMOTION-LOG.md` incidentally matches the *unrelated*
  Fixture-1A promotion's `Source Project(s)` field, which contains this
  machine's real username fragment `jay-nelson` as part of the project slug —
  not a leak from Bucket C's content; the diff-based check is the correct one
  and it passed clean.)
- **Fixture Set 2 (staleness/prune):** ✅ PASS. `prune --threshold-days 0`
  moved the seeded stale entry (and, correctly per a literal 0-day threshold,
  every other entry in the project — every `last_referenced` date is "at or
  beyond 0 days old") from `entries/` to `archive/`, byte-identical, with
  `MEMORY.md` index lines removed. Manually moving the file back to
  `entries/` and re-running `list_entries()` confirmed it was recoverable.
- **Consolidation fixture:** ✅ PASS. The two seeded overlapping entries
  (`retry-on-flaky-network-calls`, `backoff-strategy-for-http-timeouts`) were
  merged into one new entry (`retry-with-exponential-backoff-for-transient-failures`,
  a new name), both originals moved to `archive/` byte-identical, `MEMORY.md`
  updated (2 lines removed, 1 added), and exactly one block appended to a
  newly-created `CONSOLIDATION-LOG.md`. An unrelated third entry present in
  the same project was correctly left untouched.
- **Intent alignment A (aligned):** ✅ PASS. One affirmative sentence, no
  manufactured caveats.
- **Intent alignment B (diverges):** ✅ PASS. Named both subjects (stored
  Intent vs. the WebSocket-chat task) joined by an explicit contrast
  connector ("no connection to").
- **`view` empty case:** ✅ PASS (see prior addendum).
- **`view` populated, bare call:** ✅ PASS. Reported
  `Relevant entries: none requested this call`; `Intent`/`Intent alignment`
  still populated; no raw entry-file body text appeared, only name/path
  references.
- **`view` populated, with task description:** ✅ PASS. Surfaced the
  consolidated retry/backoff entry as a condensed `name — description` line;
  `metadata.last_referenced` was confirmed already `today` (it had just been
  set by the consolidation fixture moments earlier), satisfying the
  "updated to today" condition without a redundant edit.
- **`import`, first pass (create):** ✅ PASS. Exactly 2 new entries, 1:1 with
  source files; each `description` was a real, specific summary of that
  file's content (not a generic placeholder); `last_referenced` = today.
- **`import`, second pass (no `--force`, re-import same dir):** ✅ PASS. Both
  files reported skipped with the exact expected message; both entries
  confirmed unchanged (content matched the first pass verbatim).
- **`import`, third pass (`--force`, one source file edited):** ✅ PASS. Both
  entries reported overwritten (not just the changed one); the changed file's
  entry reflected the new content; `last_referenced` refreshed to today.

**Cleanup performed after the run:** the worktree's own Agent Nelly memory
directory (`~/.claude/agent-nelly-memory/users-...-worktrees-nelly-validation-scratch/`)
was deleted, and the worktree itself was removed via `ExitWorktree`
(`action: remove`, discarding the untracked `import-source/` scratch fixture
files). Two facts legitimately promoted into the shared
`global/GLOBAL-MEMORY.md` during Fixture 1A and the `import` fixture
(Python subprocess stdout buffering; mypy pre-commit full-package rescans)
were kept, on the user's decision, as accurate and generically useful facts
rather than reverted as test artifacts.

**Overall result: all fixtures in this runbook have now been executed and
passed**, across the two addenda above (empty-project + Fixture F from the
repo's real cwd; everything else from an `EnterWorktree`-provided real
scratch cwd). No hard deletes were observed anywhere in either run; every
archive/prune/consolidate operation was verified content-preserving and
reversible by direct filesystem inspection, not just by trusting
`nelly-orchestrator`'s self-report.

## Addendum — 2026-08-10 targeted re-validation of the entries/ write-back fix

Scope: not a full Phase 9 re-run — targeted re-validation of the specific bug fixed in
commit `df1a3c9` (0.1.4): "Recording a new fact" and "Import" reported success and
updated `MEMORY.md`'s index while silently failing to create the actual entry file,
because `entries/` had no directory-creation step. Run from a session whose real cwd is
`sdd`'s own repo, not `agent-nelly`'s — cross-repo `EnterWorktree` isn't possible, so this
used `sdd`'s own worktree mechanism for the import fixture's "entries/ doesn't exist yet"
case, and the sdd project's own (pre-existing, real) cwd for the "Recording a new fact"
case.

- **Recording a new fact, from `sdd`'s real project cwd** (which already had an
  agent-nelly memory dir but no `entries/` subdirectory — same as the original bug
  report): ✅ PASS. `nelly-orchestrator` reported creating `entries/` fresh, then the
  entry file, then the index line. Independently verified on disk (not trusting the
  report): both `entries/manual-validation-writeback-fix-test-entry.md` and its
  `MEMORY.md` index line existed, matching content. This is the exact regression the fix
  targets — previously only the index line would have appeared.
- **Import, from a genuinely fresh cwd (`sdd` repo worktree, no prior agent-nelly memory
  at all)**: ✅ PASS. Ran `nelly-orchestrator`'s Import flow against a one-file scratch
  source directory. Independently verified on disk: `entries/writeback-fix-import-test.md`
  and its `MEMORY.md` index line both existed, matching content, with `entries/` confirmed
  absent immediately before the run.
- **Cleanup:** both test entries and their index lines removed; the worktree used for the
  Import fixture was removed (`ExitWorktree`, `action: remove`) along with its orphaned
  agent-nelly memory directory; the `sdd` project's own agent-nelly `MEMORY.md` restored to
  its empty-skeleton state. No leftover artifacts from this validation run.

**Not re-run** (unaffected by this fix, no reason to suspect regression): promotion
buckets A/B/C, staleness/prune, consolidation, intent alignment A/B, `view` empty/populated
— all already passed in the 2026-08-09 full run above and don't touch the entries/write path
this fix changed.

## Addendum — 2026-08-10 Fixture Set G/H/I (batch fact write-back, 0.1.5)

Scope: the three fixtures added for the 0.1.5 batch write-back extension. Run from an
`EnterWorktree`-provided real scratch cwd (`nelly-batch-fixture-validation`), same
mechanism as the 2026-08-09 full run, since `nelly_slug_guard.py` requires a genuinely
different real working directory, not a role-played one.

- **Fixture G (duplicate pair + singleton, expect 2 entries not 3):** ✅ PASS. One batch
  call with three facts (two phrasings of the same `orders.status` migration-ownership
  fact, one unrelated `/health`-coverage fact) produced exactly 2 entry files, verified
  directly on disk (`ls entries/` count, byte content). The merged entry's body reconciled
  both phrasings ("owned by billing-service" + "checkout-service only reads it") rather
  than discarding one. `MEMORY.md` gained exactly 2 new lines. Both entries judged Bucket
  2 independently; confirmed zero bytes of either fact's identifying text appear in
  `global/GLOBAL-MEMORY.md` or `global/GLOBAL-PROMOTION-LOG.md` (grep count 0 on both).
- **Fixture H (no duplicates, expect N singletons):** ✅ PASS. Two facts on unrelated
  subjects (a build-script env-var gotcha, a client-side-only validation gap) produced 2
  independent entries with no merge language, verified on disk (entry count went from 2 to
  4, both new filenames present, `MEMORY.md` gained exactly 2 lines).
- **Fixture I (partial failure independence):** ✅ PASS, on the second attempt — the first
  attempt's failure-injection method was flawed, not the batch logic: a `chmod 444`
  read-only bit doesn't block the tool's atomic write-via-rename pattern, since that only
  needs write permission on the *containing directory*. Confirmed this directly with a
  manual `mv` test before blaming the orchestrator. Re-ran with macOS's `chflags uchg`
  (user-immutable, confirmed independently via a manual `mv` test to actually block a
  rename-over-target) on one target file, batched with an unrelated second fact. Result:
  fact 1's write failed on both the tool's own attempt and a shell-level retry (exact
  `EPERM`/rename errors reported and matched against the actual error text on re-check);
  the pre-existing target file's content was confirmed byte-unchanged afterward; fact 2 was
  written, indexed, and promotion-judged independently, with `MEMORY.md` gaining exactly
  one new line (fact 1's line, pre-existing, was left untouched — not corrupted, not
  duplicated). The batch did not abort on fact 1's failure.
- **Notable process finding, not an orchestrator defect:** the first Fixture I attempt is
  worth keeping as a record that `nelly-orchestrator` reported the *true* outcome (fact 1
  succeeded) rather than fabricating a failure to match the fixture's stated expectation —
  it explained, unprompted, exactly why the injected failure didn't materialize (atomic
  rename needs only directory permission, not file permission). That's the honesty
  property this whole validation approach depends on; noting it here as positive evidence
  for it, not just as a fixture bug to fix.

**Cleanup performed after the run:** `chflags nouchg` cleared on the locked test file, the
worktree's entire agent-nelly memory directory removed, and the worktree itself removed via
`ExitWorktree` (`action: remove`, `discard_changes: true` — no changes were made inside the
worktree's own git tree, only under `~/.claude/agent-nelly-memory/`, which is outside the
repo).

## Outstanding — Agent Nelly Interoperability (2026-08-10) live sanity check

Scope: the one requirement from `2026-08-10-agent-nelly-interoperability` that needs a live
session, not static reading — confirming `nelly-orchestrator`'s brief contract holds for a
caller shaped nothing like SDD (no feature slug, no workflow phase, no goal-alignment
vocabulary), per `references/example-consumer-pa-jay.md`'s illustrative walkthrough. This
plugin's docs (`INTEROP.md`, the worked example, and design.md's Generalization Audit) were
written from static analysis plus a re-run of the existing `pytest -q hooks/` suite (70/70
passing, matching the pre-change baseline) — this section is the not-yet-executed live step.

### Prerequisites

Same as the top of this file: a real, distinct working directory is required, since
`hooks/nelly_slug_guard.py` recomputes `project_slug()` from the session's actual invocation
cwd, not a role-played one. Use `EnterWorktree` to get a genuinely different real cwd (the
established pattern from every fixture set above), rather than asking a subagent to pretend a
different `cwd`.

### Steps

1. From an `EnterWorktree`-provided scratch cwd (a fresh directory unrelated to both
   `agent-nelly` and SDD's own memory), invoke `nelly-orchestrator` directly with a request
   shaped like `references/example-consumer-pa-jay.md`'s example:
   - `cwd`: the worktree's real path
   - `task description`: "checking Monzo balance and recent spending for Jay"
   - `surface relevant memory: true`
2. Confirm the response is exactly the four-section shape (`Intent`, `Relevant entries`,
   `Intent alignment`, `Written`), with:
   - `Intent: not yet captured` (fresh project, nothing stored yet)
   - `Relevant entries: none matched this task` (no entries exist yet in this fresh scratch
     project)
   - `Intent alignment: not applicable — no Intent captured yet.`
   - `Written: none`
   — i.e. every section resolves sensibly with **zero** feature-slug/phase/goal vocabulary
   required or produced.
3. Record a `new fact` matching the worked example's Monzo re-auth fact (`"Monzo MCP requires
   periodic re-authorization; run \`uv run python monzo_oauth.py\` from \`servers/monzo-mcp/\`
   when a tool call returns {"error": "auth_required"}."`) and confirm:
   - A new entry file is created under the worktree's `entries/`.
   - `MEMORY.md`'s index gains exactly one new line.
   - The promotion judgment runs and correctly places this in Bucket 2 (project-specific — it
     names a specific script path and MCP server), i.e. `global/GLOBAL-MEMORY.md` and
     `global/GLOBAL-PROMOTION-LOG.md` are byte-for-byte unchanged (diff before/after).
4. Re-run `/nelly-memory view "checking Monzo balance"` and confirm `Relevant entries` now
   surfaces the just-recorded fact as a condensed `name — description` line.
5. **Repo boundary check** (separate from the worktree, run once against the real repo):
   `git -C ~/.claude/plugins/claude-pa status` — confirm no file this feature touched appears
   in its output. (Note: as of 2026-08-10 this repo has pre-existing, unrelated uncommitted
   changes to `servers/monzo-mcp/src/monzo_mcp/client.py` and its test file — not caused by
   this feature; the check is that *none of this feature's work* appears there, not that the
   repo is otherwise clean.)

### Pass conditions

All of steps 2-4 produce the documented shape with no errors, no invented vocabulary, and no
partial briefs; step 5 confirms zero agent-nelly-interoperability changes leaked into
`claude-pa`'s repo.

### Cleanup

Same as every other worktree-based fixture above: remove the worktree's agent-nelly memory
directory under `~/.claude/agent-nelly-memory/`, then remove the worktree itself via
`ExitWorktree` (`action: remove`).

### Status

- [ ] Not yet executed — requires a live Claude Code session driving `nelly-orchestrator`
      directly, same category as every other fixture in this file.

## Outstanding — Token Efficiency (2026-08-10) before/after comparison

Scope: the live before/after token-usage comparison for
`2026-08-10-agent-nelly-token-efficiency`'s Phase 6, per that feature's `tasks.md`. This
feature's earlier phases (doc trim, index-line fields, write-back wiring, surfacing
pre-filter) were validated statically and via the Fixture Set below; this section is the
one requirement that needs a live session to actually measure `nelly-orchestrator`
subagent-call token usage, not static reading. Not executed as part of the automated
implementation task — flagged here as outstanding, consistent with the pattern already
established by the Interoperability `Outstanding` section above (this project's
`2026-08-07-agent-nelly-plugin-promotion` feature's own live validation is fully executed
and signed off, see the runbook above through the 2026-08-10 addenda — no outstanding
item remains for that feature).

### Prerequisites

Same as the top of this file: a real, distinct working directory is required for the
`pa-jay` session (since `hooks/nelly_slug_guard.py` recomputes `project_slug()` from the
session's actual invocation cwd, not a role-played one — use `EnterWorktree` for any
scratch cwd needed). The SDD workflow session can run against a real SDD-managed feature
folder (this feature's own folder is a reasonable choice, or any other in-progress
feature).

### Steps

1. **Pick two representative sessions:**
   - One SDD workflow phase-transition session (a `nelly-orchestrator` call made during a
     normal SDD phase transition, e.g. Requirements → Design or Design → Tasks).
   - One `pa-jay` session (e.g. a `money-check` or `morning-brief` run), per
     `references/example-consumer-pa-jay.md`'s pattern.
2. **Baseline (before this feature's changes):** for each of the two sessions, capture
   `nelly-orchestrator` subagent-call token usage. Reuse a baseline from git history or a
   prior session log if one exists for a comparable call; otherwise run a fresh baseline
   once on a throwaway branch checked out to the commit before this feature's changes.
3. **After (with this feature's changes):** re-run the same two session shapes against
   the current `agents/nelly-orchestrator.md`, and capture subagent-call token usage the
   same way.
4. **Compare** before vs. after token usage for each of the two sessions.

### Scope decision — expected result, not a bug

Per this feature's `recap.md` (Implementation Notes, 2026-08-10), the Phase 4 pre-filter
narrows scope to `handoff surfacing` calls only: the index-line schema (`type`,
`confidence`, `files` — no `description`) lets step 1 skip opening a file only for a
`handoff surfacing` call's type-eligibility check. A plain `surface relevant memory` call
still has no description text to judge topical relevance from the index alone, so it
still opens every candidate entry file unconditionally, exactly as before this feature.

This means:

- To actually observe a token-usage improvement, the before/after comparison must be run
  against a call pattern that includes `handoff surfacing: true` (not a plain `surface
  relevant memory` call).
- A plain `surface relevant memory` call is **expected** to show no measurable
  improvement before vs. after — that is the correct, already-recorded scope decision,
  not a regression or a bug to chase.
- Whichever of the two sessions above (SDD phase-transition or `pa-jay`) naturally
  exercises `handoff surfacing` is the one where an improvement should be visible; the
  other (or the same session's plain-surfacing calls) is expected to show none.

### Also part of this follow-up (not a separate item)

Fixture Set — Index-line pre-filter for "Relevant entries" step 1 (Phase 4, above,
fixtures J/K/L/M) is written and Red-confirmed but has not yet been executed live. Its
Status checkbox remains unflipped until that live execution happens. Run it as part of
the same live session covered by this section, not as a separate outstanding item —
fixtures K, L, and M in particular exercise the same `handoff surfacing`/pre-filter
behavior this before/after comparison is measuring.

### Status

- [x] Executed live 2026-08-11. Result: **no measurable token reduction** in this small-scale
      (4-entry) run — see the "Before/after token comparison" table in the Fixture Set's Status
      section above for the numbers and root-cause analysis (prompt-size growth offsetting the
      trim, plus the file-skip mechanism not reliably firing for Fixture K). Not a safety
      regression — the exclusion gate held correctly in every run (Fixture M). This is a genuine,
      recorded finding, not a placeholder: the feature's primary success criterion (measurable
      token reduction) is **not confirmed** at this scale. Recorded in `recap.md` and
      `PROJECT-MEMORY.md` for this feature; a larger-memory-store re-run is the natural follow-up
      if this mechanism is revisited.
- [x] Fixture Set J/K/L/M live execution — done as part of the same session (see above); K's
      Status line is a partial pass (safety held, savings mechanism didn't demonstrably trigger).
