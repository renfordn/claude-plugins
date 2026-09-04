# Tasks: Profile State Schema Migration

## Phase Status

- Current Phase: Tasks
- State: Ready For Implementation
- Last Updated: 2026-07-01

## Execution Rules

- Preserve approved requirements and design intent.
- Keep slices to one behavior change and/or one file or module touched if possible.
- Tests first where implementation follows.
- Refactor only after green.
- Pause on ambiguity, conflicting constraints, weak testability, high-risk migration, or oversized tasks.

## Phase 1: Version Detection And Safe Fallback

### Objective

Detect legacy payload versions and prevent invalid persisted state from breaking startup.

### Prerequisites

- Approved requirements and design artifacts.

### Depends On

- []

### Ordered Steps

1. Add unit tests for version detection and malformed-payload fallback behavior.
2. Implement version detection in the persistence adapter.
3. Route invalid payloads to safe defaults without throwing to hydration callers.

### Test Intent

- Add or update:
  - persistence adapter version-detection tests
  - malformed payload fallback tests
- Expected failing behavior:
  - startup throws or hydrates unsupported state without schema awareness

### Validation Target

- Command:
  - `pnpm test -- profile-state-migration`
- Evidence:
  - version detection and safe fallback tests pass

### Unlocks

- Enables:
  - actual v1-to-v2 transform work in Phase 2

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Phase 2: v1 To v2 Transform

### Objective

Migrate valid v1 payloads into normalized v2 state with explicit schema metadata.

### Prerequisites

- Phase 1 is green.

### Depends On

- [Phase 1]

### Ordered Steps

1. Add transform mapping tests for representative v1 fixtures.
2. Implement pure migration helpers in `migrations/v1-to-v2`.
3. Validate migrated output and write back v2 payload with schema version metadata.

### Test Intent

- Add or update:
  - v1 fixture mapping tests
  - schema metadata write-back tests
- Expected failing behavior:
  - valid v1 payloads remain unreadable by v2 consumers

### Validation Target

- Command:
  - `pnpm test -- profile-state-migration`
- Evidence:
  - migration fixture tests pass and output schemaVersion is `2`

### Unlocks

- Enables:
  - hydration integration and rollback-safety checks in Phase 3

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Phase 3: Hydration Integration And Rollout Guardrails

### Objective

Integrate migration into startup hydration and document compatibility behavior for rollout and rollback.

### Prerequisites

- Phase 2 is green.

### Depends On

- [Phase 2]

### Ordered Steps

1. Add integration tests for hydration using legacy payload fixtures.
2. Wire migrated output into store hydration before downstream consumers read profile state.
3. Capture rollout and rollback notes in the recap and migration documentation artifact.

### Test Intent

- Add or update:
  - hydration integration tests
  - rollback compatibility assertion coverage
- Expected failing behavior:
  - migrated payloads are not consistently consumed during app startup

### Validation Target

- Command:
  - `pnpm test -- profile-state-migration`
- Evidence:
  - integration tests pass and startup consumes migrated state safely

### Unlocks

- Enables:
  - implementation handoff completion for the migration

### Blockers Or Escalation

- [x] No blocker remains for this phase.

## Task Readiness Checklist

- [x] At least one concrete implementation phase exists
- [x] Each phase has explicit objective, steps, test intent, and validation target
- [x] Slices are safe for TDD
- [x] No unresolved blocker requires confirmation before implementation
- [x] State can be marked `Ready For Implementation`
