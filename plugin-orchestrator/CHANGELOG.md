<!-- TDD-SKIP -->
## [Unreleased]

## [1.2.5] - 2026-09-20

- **Pre-commit hook**: wire `InteropDriftValidator` to `.githooks/pre-commit` (tracked) + `scripts/setup-hooks.sh` for new-checkout setup; add `interop-drift` CI job to `.github/workflows/tests.yml`.

## [1.2.4] - 2026-09-20

- **Consistency pass**: fix `SchemaExtractor` section-awareness (`CAPABILITY_SECTION_KEYWORDS`), filter `get_capability_consumes()` to required fields only, remove `code-reviewer` from `EXPECTED_CAPABILITIES`; update agent-ux fixture fields to match real contract.

## [1.2.3] - 2026-09-20

- **Escalation re-spawn**: record escalation re-spawn outcomes in workflow state.
