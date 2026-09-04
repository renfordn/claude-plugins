# Design: Profile State Schema Migration

## Status

- Phase: Design
- State: Approved
- Last Updated: 2026-07-01

## Design Summary

Introduce a versioned profile-state migration layer in the persistence adapter that detects stored schema version, applies a pure v1-to-v2 transform when needed, validates the result, and writes back normalized v2 state with explicit schema metadata.

## Scope Mapping To Requirements

- Requirement: Migrate valid v1 payloads before consumers read them.
  - Design Response: Hydration path routes persisted state through a version-aware migration pipeline.
- Requirement: Invalid payloads must fail safely.
  - Design Response: Validation failures return safe defaults and emit diagnostic telemetry hooks.
- Requirement: Rollback must remain safe.
  - Design Response: Persist schema version metadata and avoid destructive mutation of unsupported legacy semantics.

## Architecture Or Code Touchpoints

- `profile-state/persistence-adapter`: detect version and coordinate migration.
- `profile-state/migrations/v1-to-v2`: pure transform and validation helpers.
- `profile-state/store-hydration`: consume migrated output before store initialization.

## Data Contracts And Interfaces

- Interface: `PersistedProfileStateV1`
  - Inputs: legacy persisted JSON payload
  - Outputs: typed v1 state object
  - Invariants: only accepted if minimum required v1 fields validate

- Interface: `PersistedProfileStateV2`
  - Inputs: migrated state and schema version metadata
  - Outputs: normalized persistence payload
  - Invariants: schemaVersion is always present and equals `2`

- Interface: `migrateProfileState(input)`
  - Inputs: unknown persisted payload
  - Outputs: `{ state, migrated, fallbackUsed }`
  - Invariants: never throws to startup caller

## States, Flows, And Edge-Case Handling

- Primary flow:
  - Persistence adapter reads stored payload.
  - Version detector classifies payload as v1 or v2.
  - v1 payload is transformed and validated into v2.
  - Hydration proceeds using normalized v2 state.

- Edge case:
  - Malformed payload.
  - Migration returns safe defaults and marks fallback path.

- Edge case:
  - Unknown legacy fields.
  - Transform preserves only fields with supported mappings.

- Edge case:
  - Older client reads v2 payload.
  - Explicit schema metadata allows unsupported-state detection instead of unsafe parsing.

## Validation Strategy

- Unit:
  - version detection
  - v1-to-v2 transform mapping
  - invalid payload fallback behavior
- Integration:
  - store hydration with legacy payload fixture
  - write-back behavior after successful migration
- Manual:
  - load app with seeded v1 local state and confirm preserved settings after upgrade

## Risks And Tradeoffs

- Risk: Migration logic may silently drop unsupported user preferences.
  - Mitigation: document unsupported mappings and assert expected omissions in tests.
- Risk: Startup path becomes harder to debug.
  - Mitigation: keep migration pure and isolate orchestration in persistence adapter.

## Open Questions

- [x] No blocking design questions remain for this slice.

## Phase Decision

- [x] Design supports current requirements
- [x] Design is testable
- [x] Design avoids unresolved contradictions
- [x] Ready to move to Tasks

## Phase Completion

- [x] Requirement coverage is explicit
- [x] Architecture or code touchpoints are named
- [x] Interfaces or contracts are described
- [x] Validation strategy is credible
- [x] Phase Decision is fully satisfied
- [x] State can be marked `Approved`
