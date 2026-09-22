# First-Class Plugin Collection Rubric

Defines what "first class" means for every plugin in this collection, applied
uniformly. Used by the audit (`docs/first-class-audit.md`, hand-scored plus
checker output) and enforced mechanically in CI where possible
(`scripts/first_class_check.py`).

## Status values

- `PASS` — item's condition is met.
- `FAIL` — item's condition is not met; a real gap.
- `SKIPPED` — item is mechanically checkable in principle, but the tool it
  depends on is not available in the current environment (e.g.
  `plugin-validate`). Never silently treated as PASS.
- `N/A` — item does not apply to this plugin, either because the plugin
  declared the component intentionally absent (`first_class.declared_absent`
  in its own `plugin.json`), or because the item is collection-level and
  doesn't apply per-plugin.

## Declared absence

A plugin may add an optional `first_class.declared_absent` array to its own
`.claude-plugin/plugin.json` naming components it intentionally omits, drawn
from a fixed enum: `hooks`, `commands`, `skills`, `agents`, `INTEROP.md`.
`tests` is **not** in the enum and can never be declared absent — every
plugin must have tests, no escape hatch. An unrecognized value in the array
does not suppress any check (fails closed).

## Weight

`1` (low) to `3` (high) — used by the backlog to rank `weight ÷ size`.

---

## Consistency

| ID | Pass Condition | Weight | Mechanical |
|----|-----------------|--------|------------|
| CONS-01 | `INTEROP.md` exists at the plugin's root, or the plugin declares `INTEROP.md` absent via `first_class.declared_absent` | 2 | Y |
| CONS-02 | `hooks/` exists at the plugin's root, or declared absent | 1 | Y |
| CONS-03 | `commands/` exists at the plugin's root, or declared absent | 1 | Y |
| CONS-04 | `skills/` exists at the plugin's root, or declared absent | 1 | Y |
| CONS-05 | `agents/` exists at the plugin's root, or declared absent | 1 | Y |
| CONS-06 | `CHANGELOG.md` exists at the plugin's root | 1 | Y |
| CONS-07 | `.claude-plugin/plugin.json` parses as JSON and contains all of `name, version, description, author, homepage, keywords, license`, and `version` matches `\d+\.\d+\.\d+` | 2 | Y |
| CONS-08 | `LICENSE` file content is byte-identical across every plugin in the collection | 2 | Y |
| CONS-09 | No stray root-level status/history docs in the plugin directory (patterns: `*_STATUS.md`, `*_CHECKLIST.md`, `*_NOTES.md`, `*_SUBMISSION.md`, `CONTINUATION_GUIDE.md`, `STRUCTURE.md`, `tasks.md`) | 1 | Y |
| CONS-10 | Plugin has a discoverable test suite (`tests/` directory, or `test_*.py` / `*.test.js` files anywhere under the plugin root excluding `node_modules/`) — never declarable absent, even if `tests` appears in `declared_absent` | 3 | Y |

## Install & Onboarding

| ID | Pass Condition | Weight | Mechanical |
|----|-----------------|--------|------------|
| ONBOARD-01 | Root `README.md` links to `docs/install-and-verify.md` | 3 | Y |
| ONBOARD-02 | `docs/install-and-verify.md` contains an explicit `claude plugin install <name>@renfordn-plugins` command for every plugin listed in `.claude-plugin/marketplace.json` | 2 | Y |
| ONBOARD-03 | Each plugin's own `README.md` has a Quickstart (or equivalent) section a new user can follow start to finish without leaving the file | 2 | N |

## Quality Gates & CI

| ID | Pass Condition | Weight | Mechanical |
|----|-----------------|--------|------------|
| CI-01 | Plugin's name appears in `.github/workflows/tests.yml`'s `python-tests` job `matrix.plugin` list (this is the standardized per-plugin coverage pattern the collection tracks; a separately-shaped job for a non-Python plugin, like `agent-cache-plugin`'s own `npm test` job, is not treated as equivalent for this item — see `docs/first-class-audit.md`'s `agent-cache-plugin` CI-01 row and `docs/first-class-backlog.md` for the tracked gap) | 3 | Y |
| CI-02 | `deployment-ops-plugin:plugin-validate` passes for this plugin, where the tool is available in the running environment; `SKIPPED` (never silently PASS) when the tool is absent | 2 | Y (SKIPPED when tool absent) |

## Runtime UX & Reliability

| ID | Pass Condition | Weight | Mechanical |
|----|-----------------|--------|------------|
| RUN-01 | `CHANGELOG.md`'s content contains the exact version string currently set in `plugin.json` | 1 | Y |
| RUN-02 | Hooks (where present) degrade gracefully on a missing optional dependency rather than hard-crashing (reviewed against the hook's own source) | 2 | N |

## Collection-level

| ID | Pass Condition | Weight | Mechanical |
|----|-----------------|--------|------------|
| COLL-01 | Every plugin directory containing a `.claude-plugin/plugin.json` is listed in `.claude-plugin/marketplace.json`, and vice versa (1:1, no extras, no omissions) | 2 | Y |
| COLL-02 | Every plugin in `.claude-plugin/marketplace.json` is present in `.github/workflows/tests.yml`'s `python-tests` CI matrix (same underlying check as CI-01, scored once at the collection level) | 3 | Y |
| COLL-03 | Root `README.md`'s plugin bullet list names the same set of plugins as `.claude-plugin/marketplace.json` | 1 | Y |
| COLL-04 | No two plugins ship a divergent copy of a shared bare module without a regression test guarding it (see `shared/test_plugin_packaging_self_containment.py` for the known, currently-guarded case) | 2 | N |

---

Every `Mechanical=Y` item above is implemented by exactly one function in
`scripts/first_class_check.py` (see that file's docstring for the ID→function
map) and is exercised by `scripts/test_first_class_check.py`. Every ID here is
referenced by at least one row in `docs/first-class-audit.md`, and every `FAIL`
row in the audit is referenced by at least one item in
`docs/first-class-backlog.md`.
