# Tasks: Profile State Schema Migration

## Slice 1: Detect legacy payload versions and fall back safely on malformed persisted state

**Risk Tier:** standard
**Depends On:** none
**Files:** profile-state/persistence-adapter

### Test Intent
Persisted payloads are classified as v1 or v2 on read, and malformed payloads hydrate to safe defaults instead of throwing.

### Validation Target
`pnpm test -- profile-state-migration` — version detection and safe fallback tests pass.

### Ordered Steps
1. Add unit tests for version detection and malformed-payload fallback behavior.
2. Implement version detection in the persistence adapter.
3. Route invalid payloads to safe defaults without throwing to hydration callers.

---

## Slice 2: Migrate valid v1 payloads into normalized v2 state with explicit schema metadata

**Risk Tier:** high-risk
**Depends On:** Slice 1
**Files:** profile-state/migrations/v1-to-v2

### Test Intent
Representative v1 fixtures map to v2 output, and the written payload carries `schemaVersion: 2`.

### Validation Target
`pnpm test -- profile-state-migration` — migration fixture tests pass and output `schemaVersion` is `2`.

### Ordered Steps
1. Add transform mapping tests for representative v1 fixtures.
2. Implement pure migration helpers in `migrations/v1-to-v2`.
3. Validate migrated output and write back v2 payload with schema version metadata.

### Notes
High-risk: this is the transform at the core of the schema migration. design.md's Risks And Tradeoffs section flags that migration logic may silently drop unsupported user preferences — mitigate by documenting unsupported v1 field mappings and asserting the expected omissions in tests.

---

## Slice 3: Consume migrated state during startup hydration with rollout and rollback notes captured

**Risk Tier:** high-risk
**Depends On:** Slice 2
**Files:** profile-state/store-hydration

### Test Intent
Startup hydration consistently consumes migrated v2 state, verified against legacy payload fixtures, before downstream consumers read profile state.

### Validation Target
`pnpm test -- profile-state-migration` — integration tests pass and startup consumes migrated state safely.

### Ordered Steps
1. Add integration tests for hydration using legacy payload fixtures.
2. Wire migrated output into store hydration before downstream consumers read profile state.
3. Capture rollout and rollback notes in the recap and migration documentation artifact.

### Notes
High-risk: wires the migration into the startup path shared by all downstream consumers. design.md's Risks And Tradeoffs section flags that the startup path becomes harder to debug — mitigate by keeping migration pure and isolating orchestration in the persistence adapter (Slice 1/2).
