# First-Class Plugin Collection — Backlog

Derived from `docs/first-class-audit.md`'s FAIL/partial rows (snapshot
2026-09-22). Each item is self-contained, sized, risk-rated, and startable
independently via `/isdd`. Ranked by `weight ÷ estimated_size`
(size: S=1, M=2, L=3), highest first. No backlog item is implemented as part
of this feature (audit-only, per requirements' non-goals).

| Rank | Item | Weight | Size | Score |
|---|---|---|---|---|
| 1 | [1. Link root README.md's plugin list to include plugin-harness](#1-link-root-readmemds-plugin-list-to-include-plugin-harness) | 1 | S | 1.0 |
| 2 | [2. Add agent-cache-plugin to the python-tests CI matrix (or document why it's exempt)](#2-add-agent-cache-plugin-to-the-python-tests-ci-matrix-or-document-why-its-exempt) | 3 | M | 1.5 |
| 3 | [3. Unify LICENSE content across all 7 plugins](#3-unify-license-content-across-all-7-plugins) | 2 | M | 1.0 |
| 4 | [4. Add INTEROP.md to agent-cache-plugin](#4-add-interopmd-to-agent-cache-plugin) | 2 | M | 1.0 |
| 5 | [5. Clean up stray root-level status/history docs](#5-clean-up-stray-root-level-statushistory-docs) | 1 | M | 0.5 |
| 6 | [6. Fill in genuinely-missing structural components (or declare them absent)](#6-fill-in-genuinely-missing-structural-components-or-declare-them-absent) | 1 | L | 0.33 |
| 7 | [7. Add a Quickstart section to each plugin's README](#7-add-a-quickstart-section-to-each-plugins-readme) | 2 | L | 0.67 |

---

## 1. Link root README.md's plugin list to include plugin-harness

- **Rubric items closed:** COLL-03
- **Affected plugins:** none directly (root `README.md` only)
- **Size:** S · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md` — `<collection>` / `COLL-03` / FAIL — "README.md does not list: ['plugin-harness']"
- **Description:** Root `README.md`'s intro bullet list currently names 6 of
  the 7 marketplace plugins (`plugin-harness` is described in prose as the
  thing the others are "used together by" but never gets its own bullet).
  Add a `plugin-harness/` bullet consistent with the other six.
- **Why self-contained:** single-file, single-section edit; no code or
  behavior change.

## 2. Add agent-cache-plugin to the python-tests CI matrix (or document why it's exempt)

- **Rubric items closed:** CI-01 (agent-cache-plugin), COLL-02
- **Affected plugins:** agent-cache-plugin
- **Size:** M · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md` — `agent-cache-plugin` / `CI-01` / FAIL; `<collection>` / `COLL-02` / FAIL
- **Description:** `agent-cache-plugin` is a Node package with its own
  separate `agent-cache-plugin` CI job (`npm ci && npm test && npm run
  lint`) — its tests do run in CI today, just not through the
  `python-tests` job's `matrix.plugin` list (which only runs Python
  plugins). This item is either (a) formalize the existing separate job as
  the collection's documented "equivalent CI coverage" path and update the
  rubric/checker to recognize it, or (b) if the Python-matrix pattern is
  meant to be the single source of truth, add an explicit note/annotation
  the checker can read instead. Decide the mechanism during `/isdd`, since
  either resolution touches the checker's `plugins_missing_from_ci_matrix`
  logic (a functional change, correctly out of scope for this audit-only
  feature).
- **Why self-contained:** touches only CI config + (if chosen) the checker's
  matrix-diff logic; no plugin runtime behavior changes.

## 3. Unify LICENSE content across all 7 plugins

- **Rubric items closed:** CONS-08 (collection-level)
- **Affected plugins:** agent-cache-plugin, agent-isdd, agent-nelly, agent-tdd, agent-ux, code-reviewer, plugin-harness (all 7)
- **Size:** M · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md` — `<collection>` / `CONS-08` / FAIL — 3 distinct LICENSE contents across the 7 plugins (one plugin-harness variant, one agent-cache-plugin variant, 5 plugins sharing a third)
- **Description:** Same author, same repo, 3 different LICENSE file
  contents. Pick one canonical license text and apply it to all 7 plugin
  directories (or document a deliberate per-plugin licensing reason if one
  exists, which the audit did not find evidence of).
- **Why self-contained:** file-content-only change across known files, no
  code touched; capped at L would only apply if legal review were required,
  which is out of this feature's scope to determine — flagged for the
  `/isdd` intake to confirm licensing intent first.

## 4. Add INTEROP.md to agent-cache-plugin

- **Rubric items closed:** CONS-01 (agent-cache-plugin)
- **Affected plugins:** agent-cache-plugin
- **Size:** M · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md` — `agent-cache-plugin` / `CONS-01` / FAIL — "not found: agent-cache-plugin/INTEROP.md"
- **Description:** `agent-cache-plugin` is the only plugin in the collection
  without an `INTEROP.md` capabilities contract (6/7 have one). Author one
  following the existing 6 plugins' format so other plugins (notably
  `plugin-harness`) can route to it consistently.
- **Why self-contained:** one new doc file, no code change; `interop-drift`
  CI job already validates `INTEROP.md` schema drift once one exists.

## 5. Clean up stray root-level status/history docs

- **Rubric items closed:** CONS-09 (agent-cache-plugin, agent-isdd, agent-nelly)
- **Affected plugins:** agent-cache-plugin, agent-isdd, agent-nelly
- **Size:** M · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md` FAIL rows for `CONS-09` on
  all three plugins — `agent-cache-plugin`: `FOLLOW_UP_ITEMS.md`,
  `MARKETPLACE_SUBMISSION.md`, `SHIPPING_CHECKLIST.md`, `STRUCTURE.md`,
  `V1.3_RELEASE_NOTES.md`, `tasks.md`; `agent-isdd`: `tasks.md`;
  `agent-nelly`: `CONTINUATION_GUIDE.md`, `SLICE_IMPLEMENTATION_STATUS.md`,
  `tasks.md`
- **Description:** These are one-time migration/shipping artifacts (per
  design.md's content skim), not living docs. Relocate genuinely useful
  content into `CHANGELOG.md` or a plugin's own docs, then delete the stray
  files. `tasks.md` specifically is agent-isdd's own SDD leftover artifact
  not meant to ship — same fix (delete) applies to all three occurrences.
- **Why self-contained:** deletions/relocations only, no functional code
  touched; capped at M since it spans 3 plugin directories but each is a
  trivial per-file decision.

## 6. Fill in genuinely-missing structural components (or declare them absent)

- **Rubric items closed:** CONS-03 (agent-tdd, code-reviewer, plugin-harness), CONS-04 (agent-nelly, agent-ux, plugin-harness), CONS-05 (code-reviewer, plugin-harness)
- **Affected plugins:** agent-tdd, agent-nelly, agent-ux, code-reviewer, plugin-harness
- **Size:** L · **Risk:** medium
- **Audit evidence:** `docs/first-class-audit.md` FAIL rows for `CONS-03`/`CONS-04`/`CONS-05` across 5 plugins (8 individual gaps total)
- **Description:** For each FAIL, a human decision is needed per (plugin,
  component) pair: is the missing `commands/`/`skills/`/`agents/` directory
  a genuine gap to build, or a legitimate design choice that should instead
  get a `first_class.declared_absent` entry in that plugin's `plugin.json`
  (the mechanism this feature introduced, already applied narrowly to the
  two cases requirements.md/design.md explicitly confirmed as intentional —
  `agent-ux` hooks/commands, `code-reviewer` hooks)? This item is scoped as
  the triage-and-resolve pass for the remaining 8 gaps this audit did not
  have design-doc evidence to resolve unilaterally.
- **Why capped at L, not split further without a product decision:** the 8
  gaps span 5 different plugins and two different resolution types
  (build vs. declare-absent) per gap; splitting further without first
  knowing which plugins get which resolution would either invent structure
  or produce phantom sub-items — the `/isdd` intake for this item should
  start with the triage decision, then split into per-plugin slices from
  there.

## 7. Add a Quickstart section to each plugin's README

- **Rubric items closed:** ONBOARD-03 (agent-isdd, agent-nelly, agent-tdd, agent-ux, code-reviewer, plugin-harness)
- **Affected plugins:** agent-isdd, agent-nelly, agent-tdd, agent-ux, code-reviewer, plugin-harness (6 of 7 — `agent-cache-plugin` already has one)
- **Size:** L · **Risk:** low
- **Audit evidence:** `docs/first-class-audit.md`'s ONBOARD-03 hand-scored
  table — 6/7 plugins FAIL, each with a specific justification
- **Description:** Each of the 6 READMEs has installation instructions but
  no single start-to-finish walkthrough a new user can follow without
  leaving the file. Use `agent-cache-plugin`'s existing `## Quick Start`
  section as the template/format to replicate.
- **Why self-contained:** doc-only, one section per plugin, no code touched;
  capped at L (6 files) rather than 6 separate S items since the same
  template and review pass naturally covers all of them together.

---

Every FAIL row in `docs/first-class-audit.md`'s mechanical table and every
FAIL row in its non-mechanical ONBOARD-03/RUN-02/COLL-04 tables is referenced
by exactly one item above (RUN-02 and COLL-04 scored all-PASS in this
snapshot, so neither has a backlog item — nothing to close). No orphaned
gaps.
