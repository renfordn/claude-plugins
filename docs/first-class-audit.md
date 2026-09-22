# First-Class Plugin Collection — Audit

**Snapshot date:** 2026-09-22 · commit `main` (working tree as of this audit)

This is a **point-in-time snapshot**, not a living document. Mechanical rows
(`Mechanical=Y` in `docs/first-class-rubric.md`) were produced by running
`python3 scripts/first_class_check.py --json` against `main` and transcribing
its output verbatim (statuses and evidence below match the checker's own
output exactly — see Reproducibility below). The CI job `first-class-check`
(`.github/workflows/tests.yml`) is the living source of truth for mechanical
items going forward; re-run the checker for a current view, don't treat this
file as current after future changes land.

Non-mechanical rows (`Mechanical=N`) are hand-scored below with written
justification, per rubric item.

## Legend

`PASS` / `FAIL` / `SKIPPED` (tool unavailable in this environment, never
silently PASS) / `N/A` (declared absent, or collection-level item not
applicable to a single plugin).

## Summary

| Status | Count (mechanical) |
|---|---|
| PASS | 71 |
| FAIL | 16 |
| SKIPPED | 7 (all `CI-02` — `deployment-ops-plugin:plugin-validate` not available in this environment) |
| N/A | 3 (all declared-absence: `agent-ux` hooks/commands, `code-reviewer` hooks) |

Exit code of `python3 scripts/first_class_check.py` against `main`: **1** (≥1
mechanical FAIL, as expected — see Reproducibility).

## Mechanical items (machine-filled)

Evidence paths below are relative to the repo root.

| Plugin | Item | Status | Evidence |
|---|---|---|---|
| \<collection\> | COLL-01 | PASS | marketplace.json matches on-disk plugin directories 1:1 |
| \<collection\> | COLL-02 | FAIL | missing from CI matrix: ['agent-cache-plugin'] |
| \<collection\> | COLL-03 | FAIL | README.md does not list: ['plugin-harness'] |
| \<collection\> | CONS-08 | FAIL | LICENSE content diverges across 3 distinct contents: `{'20dc2b4d': ['agent-cache-plugin'], 'ca1aee33': ['agent-isdd', 'agent-nelly', 'agent-tdd', 'agent-ux', 'code-reviewer'], '6abb45d4': ['plugin-harness']}` |
| \<collection\> | ONBOARD-01 | PASS | README.md links install-and-verify.md |
| \<collection\> | ONBOARD-02 | PASS | install command present for every marketplace plugin |
| agent-cache-plugin | CI-01 | FAIL | missing from tests.yml matrix.plugin |
| agent-cache-plugin | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| agent-cache-plugin | CONS-01 | FAIL | not found: agent-cache-plugin/INTEROP.md |
| agent-cache-plugin | CONS-02 | PASS | agent-cache-plugin/hooks |
| agent-cache-plugin | CONS-03 | PASS | agent-cache-plugin/commands |
| agent-cache-plugin | CONS-04 | PASS | agent-cache-plugin/skills |
| agent-cache-plugin | CONS-05 | PASS | agent-cache-plugin/agents |
| agent-cache-plugin | CONS-06 | PASS | agent-cache-plugin/CHANGELOG.md |
| agent-cache-plugin | CONS-07 | PASS | all required fields present, version is semver |
| agent-cache-plugin | CONS-08 | PASS | present and non-empty (per-plugin proxy; collection row above is the real cross-plugin score) |
| agent-cache-plugin | CONS-09 | FAIL | stray docs: ['FOLLOW_UP_ITEMS.md', 'MARKETPLACE_SUBMISSION.md', 'SHIPPING_CHECKLIST.md', 'STRUCTURE.md', 'V1.3_RELEASE_NOTES.md', 'tasks.md'] |
| agent-cache-plugin | CONS-10 | PASS | test suite discovered |
| agent-cache-plugin | RUN-01 | PASS | CHANGELOG.md references version 2.0.9 |
| agent-isdd | CI-01 | PASS | present in tests.yml matrix.plugin |
| agent-isdd | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| agent-isdd | CONS-01 | PASS | agent-isdd/INTEROP.md |
| agent-isdd | CONS-02 | PASS | agent-isdd/hooks |
| agent-isdd | CONS-03 | PASS | agent-isdd/commands |
| agent-isdd | CONS-04 | PASS | agent-isdd/skills |
| agent-isdd | CONS-05 | PASS | agent-isdd/agents |
| agent-isdd | CONS-06 | PASS | agent-isdd/CHANGELOG.md |
| agent-isdd | CONS-07 | PASS | all required fields present, version is semver |
| agent-isdd | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| agent-isdd | CONS-09 | FAIL | stray docs: ['tasks.md'] |
| agent-isdd | CONS-10 | PASS | test suite discovered |
| agent-isdd | RUN-01 | PASS | CHANGELOG.md references version 0.1.47 |
| agent-nelly | CI-01 | PASS | present in tests.yml matrix.plugin |
| agent-nelly | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| agent-nelly | CONS-01 | PASS | agent-nelly/INTEROP.md |
| agent-nelly | CONS-02 | PASS | agent-nelly/hooks |
| agent-nelly | CONS-03 | PASS | agent-nelly/commands |
| agent-nelly | CONS-04 | FAIL | not found: agent-nelly/skills |
| agent-nelly | CONS-05 | PASS | agent-nelly/agents |
| agent-nelly | CONS-06 | PASS | agent-nelly/CHANGELOG.md |
| agent-nelly | CONS-07 | PASS | all required fields present, version is semver |
| agent-nelly | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| agent-nelly | CONS-09 | FAIL | stray docs: ['CONTINUATION_GUIDE.md', 'SLICE_IMPLEMENTATION_STATUS.md', 'tasks.md'] |
| agent-nelly | CONS-10 | PASS | test suite discovered |
| agent-nelly | RUN-01 | PASS | CHANGELOG.md references version 0.4.11 |
| agent-tdd | CI-01 | PASS | present in tests.yml matrix.plugin |
| agent-tdd | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| agent-tdd | CONS-01 | PASS | agent-tdd/INTEROP.md |
| agent-tdd | CONS-02 | PASS | agent-tdd/hooks |
| agent-tdd | CONS-03 | FAIL | not found: agent-tdd/commands |
| agent-tdd | CONS-04 | PASS | agent-tdd/skills |
| agent-tdd | CONS-05 | PASS | agent-tdd/agents |
| agent-tdd | CONS-06 | PASS | agent-tdd/CHANGELOG.md |
| agent-tdd | CONS-07 | PASS | all required fields present, version is semver |
| agent-tdd | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| agent-tdd | CONS-09 | PASS | no stray root-level status/history docs |
| agent-tdd | CONS-10 | PASS | test suite discovered |
| agent-tdd | RUN-01 | PASS | CHANGELOG.md references version 0.2.12 |
| agent-ux | CI-01 | PASS | present in tests.yml matrix.plugin |
| agent-ux | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| agent-ux | CONS-01 | PASS | agent-ux/INTEROP.md |
| agent-ux | CONS-02 | N/A | declared absent via first_class.declared_absent: hooks |
| agent-ux | CONS-03 | N/A | declared absent via first_class.declared_absent: commands |
| agent-ux | CONS-04 | FAIL | not found: agent-ux/skills |
| agent-ux | CONS-05 | PASS | agent-ux/agents |
| agent-ux | CONS-06 | PASS | agent-ux/CHANGELOG.md |
| agent-ux | CONS-07 | PASS | all required fields present, version is semver |
| agent-ux | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| agent-ux | CONS-09 | PASS | no stray root-level status/history docs |
| agent-ux | CONS-10 | PASS | test suite discovered |
| agent-ux | RUN-01 | PASS | CHANGELOG.md references version 0.1.6 |
| code-reviewer | CI-01 | PASS | present in tests.yml matrix.plugin |
| code-reviewer | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| code-reviewer | CONS-01 | PASS | code-reviewer/INTEROP.md |
| code-reviewer | CONS-02 | N/A | declared absent via first_class.declared_absent: hooks |
| code-reviewer | CONS-03 | FAIL | not found: code-reviewer/commands |
| code-reviewer | CONS-04 | PASS | code-reviewer/skills |
| code-reviewer | CONS-05 | FAIL | not found: code-reviewer/agents |
| code-reviewer | CONS-06 | PASS | code-reviewer/CHANGELOG.md |
| code-reviewer | CONS-07 | PASS | all required fields present, version is semver |
| code-reviewer | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| code-reviewer | CONS-09 | PASS | no stray root-level status/history docs |
| code-reviewer | CONS-10 | PASS | test suite discovered |
| code-reviewer | RUN-01 | PASS | CHANGELOG.md references version 0.1.10 |
| plugin-harness | CI-01 | PASS | present in tests.yml matrix.plugin |
| plugin-harness | CI-02 | SKIPPED | deployment-ops-plugin:plugin-validate not available in this environment |
| plugin-harness | CONS-01 | PASS | plugin-harness/INTEROP.md |
| plugin-harness | CONS-02 | PASS | plugin-harness/hooks |
| plugin-harness | CONS-03 | FAIL | not found: plugin-harness/commands |
| plugin-harness | CONS-04 | FAIL | not found: plugin-harness/skills |
| plugin-harness | CONS-05 | FAIL | not found: plugin-harness/agents |
| plugin-harness | CONS-06 | PASS | plugin-harness/CHANGELOG.md |
| plugin-harness | CONS-07 | PASS | all required fields present, version is semver |
| plugin-harness | CONS-08 | PASS | present and non-empty (per-plugin proxy) |
| plugin-harness | CONS-09 | PASS | no stray root-level status/history docs |
| plugin-harness | CONS-10 | PASS | test suite discovered |
| plugin-harness | RUN-01 | PASS | CHANGELOG.md references version 2.1.0 |

### Reproducibility

`python3 scripts/first_class_check.py` was re-run immediately before writing
this table; every FAIL row above matches the checker's own FAIL output
exactly (same plugin, item ID, and evidence), satisfying the requirements'
reproducibility success criterion. Two of `agent-ux`'s and one of
`code-reviewer`'s presence items score `N/A` rather than `FAIL` because this
audit's own `first_class.declared_absent` additions
(`agent-ux`: `hooks`, `commands`; `code-reviewer`: `hooks`) were applied
during this feature's implementation — the only plugin.json edits this
feature makes, each directly evidenced as intentional-by-design in
`requirements.md`'s edge cases and `design.md`'s Research Basis (not applied
to any other plugin/component pair, since no other absence is documented as
intentional there).

## Non-mechanical items (hand-scored)

### ONBOARD-03 — Quickstart section, per plugin

Pass condition: the plugin's own `README.md` has a Quickstart (or equivalent)
section a new user can follow start-to-finish without leaving the file.

| Plugin | Status | Justification |
|---|---|---|
| agent-cache-plugin | PASS | `README.md` has an explicit `## Quick Start` section (line 14). |
| agent-isdd | FAIL | Has `## Commands` and `## Workflow` sections but no single start-to-finish walkthrough combining install + first command to try. |
| agent-nelly | FAIL | Has `## Installation` and `## Storage` but no usage walkthrough after install. |
| agent-tdd | FAIL | Has `## Installation` but the next usage-oriented section is `## Using Agent TDD from another plugin` — aimed at plugin authors, not an end-user quickstart. |
| agent-ux | FAIL | Has `## Installation` and `## Contents` only; no usage walkthrough (consistent with `agent-ux` being a subagent other plugins delegate to, per `docs/install-and-verify.md`'s own note that it has no standalone command — but the rubric's pass condition, as written, is not met literally). |
| code-reviewer | FAIL | Has `## Installation` and `## Using Code Reviewer from another plugin` but no direct end-user quickstart. |
| plugin-harness | FAIL | Has `## Using this on other projects` and `## Scope` but no compact linear quickstart; the content is comprehensive but not structured as a start-to-finish walkthrough. |

### RUN-02 — Hooks degrade gracefully on missing optional dependency

Pass condition: hooks (where present) do not hard-crash on a missing
optional dependency, reviewed against the hook's own source. Spot-checked,
not an exhaustive line-by-line review of every hook file — see Follow-ups.

| Plugin | Status | Justification |
|---|---|---|
| plugin-harness | PASS | `orchestrator/state_store.py` defaults to zero-dependency `FileStateStore`; `RedisStateStore` only raises `ImportError` with an actionable message if explicitly requested and `redis` isn't installed — confirmed in source (`state_store.py:110-180`) and `requirements-dev.txt`'s own comment ("production hooks... have zero third-party dependencies"). |
| agent-cache-plugin | PASS | A dedicated `tests/fallback-backend.test.js` exists, indicating a designed fallback path when the native `better-sqlite3` backend is unavailable. |
| agent-isdd | PASS (spot-checked) | Hooks are stdlib-only (no third-party imports found); nothing to gracefully degrade from. |
| agent-nelly | PASS (spot-checked) | Hooks are stdlib-only (no third-party imports found). |
| agent-tdd | PASS (spot-checked) | Hooks are stdlib-only (no third-party imports found). |
| agent-ux | N/A | No `hooks/` (declared absent). |
| code-reviewer | N/A | No `hooks/` (declared absent). |

### COLL-04 — No divergent shared bare module without a regression test

Pass condition: no two plugins ship a divergent copy of a shared bare module
without a regression test guarding it.

| Status | Justification |
|---|---|
| PASS (known cases only) | `shared/test_plugin_packaging_self_containment.py` guards the one confirmed historical case (`hooks/path_resolution.py`, duplicated across `agent-isdd`, `agent-tdd`, `agent-nelly`, `plugin-harness`) by asserting each plugin's copy imports in isolation. `plugin-harness` additionally ships `hooks/hook_state.py`, which is not a cross-plugin duplicate (no other plugin has a same-named file), so it's outside this item's scope. No new divergent-duplicate-without-a-test was found in this audit, but this was not an exhaustive repo-wide scan for every possible same-named-file collision — see Follow-ups. |

## Conflict notes

None found. No two rubric items were observed to conflict for any plugin in
this audit (per the requirements' edge case, this column is carried for
future audits and intentionally left blank here).

## Follow-ups from this audit

See `docs/first-class-backlog.md` for the ranked, actionable list. Notably:
non-mechanical items above were scored via targeted spot-checks (README
headings, grep for third-party imports, known test coverage), not exhaustive
manual review of every file in every plugin — a future audit pass with more
time budget could deepen RUN-02 and COLL-04 specifically.
