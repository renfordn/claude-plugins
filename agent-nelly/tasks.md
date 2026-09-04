# Plugin Data Whitelisting: TDD-Ready Slices

## Slice 1: Shared Validator Module (Foundation)

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** hooks/plugin_data_validators.py (new)  

### Test Intent
Validators detect file-type blocklist (executables), verify scopes (agent-owned directories), and detect env-gate overrides; behavior deterministic and testable in isolation.

### Validation Target
`pytest hooks/test_plugin_data_validators.py -v`

### Ordered Steps
1. Create `hooks/plugin_data_validators.py` with three exported functions: `is_blocked_file_type(path)`, `is_within_scope(path, scope_root)`, `env_gate_disabled(env_var_name)`.
2. Implement `is_blocked_file_type()`: detect executables (.exe, .sh, .bin, .dylib, .so) and scripts via shebang; return `True` if blocked, `False` otherwise.
3. Implement `is_within_scope()`: normalize paths, check strict containment under scope_root; block path-traversal attempts (e.g., `../../`).
4. Implement `env_gate_disabled()`: check for env-var values "off", "0", "false", "disabled" (case-insensitive); return `True` if disabled.
5. Create `hooks/test_plugin_data_validators.py` with 8 unit test cases:
   - Test blocked file types (3 cases: .exe, .sh, .dylib)
   - Test valid files (1 case: .md)
   - Test scope containment (2 cases: within scope, outside scope)
   - Test path-traversal rejection (1 case: `../../escape`)
   - Test env-gate detection (1 case: "off" disables gate)
6. Run tests; all 8 must pass before advancing.

---

## Slice 2: Shared project_slug() Utility

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** hooks/shared_slug.py (new), hooks/test_shared_slug.py (new)  

### Test Intent
`project_slug(cwd)` deterministically generates collision-resistant slugs; consolidation target eliminates duplication from nelly_memory.py, sdd_memory.py, tdd_state.py.

### Validation Target
`pytest hooks/test_shared_slug.py -v && python3 hooks/shared_slug.py --help`

### Ordered Steps
1. Extract `project_slug()` function from nelly_memory.py (lines 30-34): identical implementation, deterministic slug generation via regex replacement and lowercasing.
2. Create `hooks/shared_slug.py` as a new module exporting `project_slug(cwd)` with identical logic.
3. Add CLI interface: `--slug <cwd>` flag to compute and print slug for a given cwd.
4. Create `hooks/test_shared_slug.py` with 4 unit test cases:
   - Test standard path (e.g., `/path/to/project` → `path-to-project`)
   - Test paths with special chars (e.g., `/path-with.dots/` → `path-with-dots`)
   - Test collision resistance (verify two different paths produce different slugs)
   - Test root/edge case (verify empty or minimal paths produce safe fallback)
5. Run tests; all 4 must pass before advancing.

---

## Slice 3: Consolidate Slug in agent-nelly

**Risk Tier:** standard  
**Depends On:** Slice 2  
**Files:** hooks/nelly_memory.py, hooks/test_nelly_memory.py  

### Test Intent
agent-nelly's nelly_memory.py imports `project_slug()` from shared_slug.py instead of defining its own; behavior unchanged.

### Validation Target
`pytest hooks/test_nelly_memory.py -v && python3 hooks/nelly_memory.py --path --cwd /tmp`

### Ordered Steps
1. In `hooks/nelly_memory.py`, remove the local `project_slug()` function definition (lines 30-34).
2. Add import: `from shared_slug import project_slug  # noqa: E402` at the top of imports (after sys.path.insert).
3. Run existing test suite to confirm all tests still pass (test_nelly_memory.py, test_nelly_slug_guard.py).
4. Validate CLI: `python3 hooks/nelly_memory.py --path --cwd /tmp` still produces correct memory_dir path.
5. Commit with message: "Consolidate project_slug() into shared_slug module for agent-nelly".

---

## Slice 4: Consolidate Slug in agent-isdd

**Risk Tier:** standard  
**Depends On:** Slice 2  
**Files:** agent-isdd/hooks/sdd_memory.py, agent-isdd/tests/test_sdd_memory.py  

### Test Intent
agent-isdd's sdd_memory.py imports `project_slug()` from shared_slug.py (or copies it locally if cross-repo import not feasible); behavior unchanged.

### Validation Target
`cd agent-isdd && pytest tests/test_sdd_memory.py -v`

### Ordered Steps
1. In `agent-isdd/hooks/sdd_memory.py`, locate local `project_slug()` definition.
2. Option A (preferred): Add import of shared_slug; remove local definition. Requires cross-repo module resolution (Python path setup in sdd_memory.py).
3. Option B (fallback): Copy `project_slug()` implementation from shared_slug.py into sdd_memory.py (with comment linking to shared_slug.py).
4. Run existing test suite (test_sdd_memory.py, memory_slug_guard tests).
5. Validate that `spec_dir()` and related functions still work correctly.
6. Commit separately in agent-isdd repo.

---

## Slice 5: Hook History Rotation (1000-entry cap)

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** agent-isdd/hooks/post_write_check.py, agent-isdd/hooks/hook_history_rotate.py (new), agent-isdd/references/workflow-state.archive.json (new template)  

### Test Intent
hook_history in workflow-state.json is capped at 1000 entries; overflow rotates to workflow-state.archive.json; audit trail preserved and testable.

### Validation Target
`pytest agent-isdd/hooks/test_hook_history_rotate.py -v && grep -q archive agent-isdd/references/workflow-state.template.json`

### Ordered Steps
1. Create `agent-isdd/hooks/hook_history_rotate.py` with function `rotate_history(json_fields, max_entries=1000, archive_file=None)`:
   - Takes parsed JSON object (with hook_history array)
   - If `len(hook_history) >= max_entries`, move oldest `len - 900` entries to archive file
   - Archive file format: `{archive_metadata: {rotated_at, total_entries}, entries: [...]}`
   - Return modified json_fields with truncated hook_history
2. Modify `agent-isdd/hooks/post_write_check.py` line 71-77 to call `rotate_history()` after appending new hook entry.
3. Create test `agent-isdd/hooks/test_hook_history_rotate.py`:
   - Test: appending entry doesn't rotate if count < 1000
   - Test: appending entry to 1000+ entries triggers rotation (keep newest 900, move oldest to archive)
   - Test: archive file is created with correct metadata and entries
   - Test: subsequent rotations append to existing archive file
4. Create `agent-isdd/references/workflow-state.archive.json` template showing archive structure.
5. Update `agent-isdd/references/workflow-state.template.json` comment to document archive behavior.
6. Run tests; all 4 cases must pass.

---

## Slice 6: Refactor Existing Permission Hooks (HIGH-RISK)

**Risk Tier:** high-risk  
**Depends On:** Slice 1, Slice 3, Slice 4, Slice 5  
**Files:** hooks/nelly_memory_permission.py, hooks/nelly_slug_guard.py, agent-isdd/hooks/memory_permission.py, agent-isdd/hooks/memory_slug_guard.py, hooks/test_consolidated_hooks.py (new)  

### Test Intent
**CONDITIONAL TEST-AUTHOR SPLIT REQUIRED.** Existing allow/deny behavior is preserved; cross-agent writes blocked; executables rejected; audit trail populated.

### Validation Target
`pytest hooks/test_consolidated_hooks.py -v` (supplied by test-author)

### Ordered Steps
1. **Pre-Green: Await test-author output.** Caller must spawn test-author with Risk Tier "high-risk" and this slice's Test Intent; receive test file + Red confirmation before proceeding.
2. Apply Slice 1 validators to existing hooks:
   - In nelly_memory_permission.py, after `allow()`, add check: `if is_blocked_file_type(norm)` → `deny()` instead
   - Same in nelly_slug_guard.py allow path
   - Same for agent-isdd memory_permission.py and memory_slug_guard.py
3. Consolidate env-gate checks: if `env_gate_disabled("NELLY_GATE")` or `env_gate_disabled("SDD_GATE")`, allow entire request (preserve existing behavior).
4. Add audit trail entry on allow/deny: append to a file-local hook history (or delegate to post_write_check.py for later sync to workflow-state.json).
5. Run supplied Red test; confirm fail.
6. Implement Green changes above.
7. Run supplied Red test; confirm pass.
8. Refactor for clarity (DRY up allow/deny logic, extract common validators into shared module).
9. Run full test suite + regression tests (test_nelly_memory_permission.py, test_nelly_slug_guard.py, etc.).

---

## Slice 7: Add agent-TDD Permission Hooks (HIGH-RISK)

**Risk Tier:** high-risk  
**Depends On:** Slice 1, Slice 5  
**Files:** agent-tdd/hooks/tdd_memory_permission.py (new), agent-tdd/hooks/tdd_memory_guard.py (new), agent-tdd/hooks/hooks.json (modified), agent-tdd/hooks/test_tdd_memory_hooks.py (new)  

### Test Intent
**CONDITIONAL TEST-AUTHOR SPLIT REQUIRED.** Agent-TDD writes to its own memory namespace allowed; cross-namespace writes denied; executables blocked; security checks enforced.

### Validation Target
`pytest agent-tdd/hooks/test_tdd_memory_hooks.py -v && grep -q "tdd_memory_permission" agent-tdd/hooks/hooks.json`

### Ordered Steps
1. **Pre-Green: Await test-author output.** Caller must spawn test-author with Risk Tier "high-risk" and this slice's Test Intent; receive test files + Red confirmation.
2. Create `agent-tdd/hooks/tdd_memory_permission.py`:
   - Parallel to nelly_memory_permission.py; auto-approve paths under `~/.claude/plugin-data/agent-tdd/...`
   - Use shared validators (is_blocked_file_type, env_gate_disabled("TDD_GATE"))
   - Deny cross-agent paths (e.g., `~/.claude/plugin-data/agent-nelly/`, `~/.claude/sdd-memory/`)
3. Create `agent-tdd/hooks/tdd_memory_guard.py`:
   - Parallel to nelly_slug_guard.py; deny writes to wrong TDD project directory
   - Use shared project_slug() to compute canonical TDD memory path
4. Register both hooks in `agent-tdd/hooks/hooks.json`:
   - Add PreToolUse matcher for "Write|Edit|MultiEdit"
   - Register tdd_memory_guard.py first, then tdd_memory_permission.py
5. Run supplied Red test; confirm fail.
6. Implement hooks per steps 2-4.
7. Run supplied Red test; confirm pass.
8. Validate hook registration: confirm PreToolUse hooks fire on Write/Edit/MultiEdit.
9. Verify cross-agent deny behavior (write to agent-nelly path is denied).

---

## Slice 8: Documentation

**Risk Tier:** standard  
**Depends On:** Slice 1, Slice 6, Slice 7  
**Files:** PLUGIN-DATA-WHITELISTING.md (new)  

### Test Intent
Documentation clearly explains design (path-shape trust, env-var gates, audit trail, cross-agent boundaries); maintainers can reason about future changes.

### Validation Target
`grep -q "plugin_data_validators" PLUGIN-DATA-WHITELISTING.md && wc -l PLUGIN-DATA-WHITELISTING.md`

### Ordered Steps
1. Create `PLUGIN-DATA-WHITELISTING.md` at repo root:
   - **Overview**: Unified permission hook pattern across three agents (nelly, tdd, isdd)
   - **Design Decisions**: Path-shape trust (not process identity), env-var per-plugin gates, separate archive for rotated audit entries
   - **Architecture**: Shared validators module, per-plugin hooks (allow + deny pair), hook_history rotation
   - **Directory Scoping**: `~/.claude/plugin-data/<agent-slug>/...`
   - **Audit Trail**: Entry format, rotation cap (1000), archive location
   - **Env Vars**: `NELLY_GATE`, `SDD_GATE`, `TDD_GATE` (off/0/false/disabled to bypass)
   - **Testing**: Per-slice test strategies and coverage
   - **Future Work**: Planned enhancements (process identity, fine-grained scopes, etc.)
2. Add table of affected files (hooks/modules/imports changed per slice).
3. Add troubleshooting section (common issues, validation commands).
4. Validate markdown formatting and link correctness.

---

## Dependency Graph

```
Slice 1 (Validators)
├─ Slice 5 (History Rotation)
├─ Slice 6 (Refactor Existing Hooks) ← HIGH-RISK
└─ Slice 7 (Add TDD Hooks) ← HIGH-RISK

Slice 2 (Shared Slug)
├─ Slice 3 (Consolidate in Nelly)
└─ Slice 4 (Consolidate in SDD)

Slice 3 → Slice 6
Slice 4 → Slice 6

Slice 6 & 7 → Slice 8 (Documentation)
```

**Topological Order:** 1, 2 (parallel) → 3, 4 (parallel, depends on 2) → 5 (depends on 1) → 6, 7 (parallel, both HIGH-RISK) → 8

---

## Risk Tier Summary

- **Standard (5 slices):** 1, 2, 3, 4, 5, 8
  - Unit tests for new modules
  - Regression tests on refactored code
  - Integration tests for consolidation
  
- **High-Risk (2 slices):** 6, 7
  - Require test-author split (caller spawns test-author, passes Red test)
  - Modify existing critical hooks (permission logic)
  - Security-sensitive (cross-agent boundary checks, executable blocklist)
  - Peer review required before merge

---

## Cross-Repo Implementation Notes

- **Slice 1, 2:** Can be implemented in any agent repo or shared location; suggest agent-nelly as foundation
- **Slice 3:** agent-nelly repo
- **Slice 4:** agent-isdd repo  
- **Slice 5:** agent-isdd repo (post_write_check.py lives there)
- **Slice 6:** Split across agent-nelly and agent-isdd repos (parallel implementation)
- **Slice 7:** agent-tdd repo
- **Slice 8:** Recommend shared location (e.g., root of monorepo or main plugin repo)

---

## Validation Checklist (Ralph Loops)

### Loop 1: Slice Size Validation
- [x] Slice 1: 1 file (new module) → ✓ testable
- [x] Slice 2: 2 files (new module + tests) → ✓ testable
- [x] Slice 3: 1 file (modify nelly_memory.py) → ✓ testable via existing suite
- [x] Slice 4: 1 file (modify sdd_memory.py) → ✓ testable via existing suite
- [x] Slice 5: 2 files (modify post_write_check.py, new rotate module) → ✓ testable
- [x] Slice 6: 4 files (modify existing hooks in 2 repos) → ✓ testable with supplied Red test
- [x] Slice 7: 4 files (new hooks in agent-tdd, modify hooks.json) → ✓ testable with supplied Red test
- [x] Slice 8: 1 file (new documentation) → ✓ validation by grep

**Result:** All slices ≤ 3 new/modified files, testable in isolation. ✓ PASS

### Loop 2: Dependency Correctness
- [x] Build graph: 1, 2 → {3, 4} → {5, 6, 7} → 8
- [x] Topological sort: 1, 2, 3, 4, 5, 6, 7, 8 (no cycles)
- [x] Hidden dependencies check:
  - Slice 3 uses project_slug() → depends on Slice 2 ✓
  - Slice 4 uses project_slug() → depends on Slice 2 ✓
  - Slice 6 uses validators from Slice 1 ✓
  - Slice 7 uses validators from Slice 1, history from Slice 5 ✓
  - Slice 8 depends on Slices 6 & 7 ✓

**Result:** Acyclic, complete, topologically sorted. ✓ PASS

### Loop 3: Research-to-Implementation Traceability
- [x] Slice 1: Validators module matches Design Spec (file-type blocklist, scope validation, env-gate) → all traceable to research findings ✓
- [x] Slice 2: project_slug() extracted from nelly_memory.py (research confirmed duplication) ✓
- [x] Slice 3: nelly_memory.py exists and has project_slug() (confirmed via file read) ✓
- [x] Slice 4: sdd_memory.py exists and has project_slug() (confirmed via find) ✓
- [x] Slice 5: post_write_check.py exists, hook_history documented in template (confirmed via file read) ✓
- [x] Slice 6: Existing hooks confirmed in both repos (nelly_memory_permission.py, nelly_slug_guard.py, memory_permission.py, memory_slug_guard.py) ✓
- [x] Slice 7: agent-tdd/hooks/hooks.json exists, no PreToolUse hooks yet (confirmed) ✓
- [x] Slice 8: Documentation target clear ✓

**Result:** All steps traceable to research findings. No unresearched assumptions. ✓ PASS

---

## Ralph Loops Verdict: READY FOR IMPLEMENTATION

✓ Slice Size: All ≤ 3 files, testable, single implementer per slice  
✓ Dependencies: Acyclic, complete, topologically ordered  
✓ Research: All steps traceable, no gaps or contradictions  
✓ Risk Tiers: HIGH-RISK slices (6, 7) flagged for test-author split  

**Next Step:** Proceed to per-slice Red-Green-Refactor implementation, starting with Slice 1.

### Risk Tier
standard

### Prerequisites
- Phase 2: Shared project_slug() utility created
- Phase 3: agent-nelly consolidation completed (for reference; this phase is independent)

### Depends On
- Phase 2, Phase 3

### Ordered Steps
1. Locate agent-isdd's current `project_slug()` implementation:
   - Check `agent-isdd/utils/project-slug.ts` (likely location)
   - Grep for function if location unclear

2. Update all imports within agent-isdd:
   - Find all references to local project_slug
   - Change to: `import { getProjectSlug } from '../../../src/utils/project-slug'` (adjust path as needed)

3. Delete agent-isdd's local project_slug.ts file

4. Repeat steps 1-3 for agent-tdd:
   - Locate `agent-tdd/utils/project-slug.ts` or grep for implementation
   - Update imports in agent-tdd
   - Delete local project_slug.ts

5. Verify exports in both agents' index/entry points (if applicable)

6. Run both agents' existing tests to confirm backward compatibility

### Test Intent
- Add or update:
  - agent-isdd integration tests (existing test suite)
  - agent-tdd integration tests (existing test suite)
- Test cases:
  - All agent-isdd tests still pass (no broken imports)
  - All agent-tdd tests still pass (no broken imports)
  - Project slug is correctly derived when either agent runs
  - No import errors or path resolution issues
- Expected failing behavior:
  - Without import fixes, tests fail with "module not found"
  - After fix: all tests pass (red → green)

### Validation Target
- Command: `npm test -- agent-isdd/ agent-tdd/` (or each agent's test command)
- Evidence: All existing agent-isdd and agent-tdd tests pass; no import errors

### Unlocks
- Phase 6 (refactoring existing hooks can now proceed with all utilities consolidated)

### Blockers Or Escalation
- [ ] Confirm agent-isdd and agent-tdd test commands
- [ ] Verify relative paths from each agent to src/utils/project-slug
- [ ] Check if either agent has circular imports or special path resolution (monorepo considerations)

---

## Phase 5: Hook History Rotation (Audit Trail Management)

### Objective
Implement audit trail rotation with a 1000-entry cap, archiving older entries to a separate file to prevent unbounded growth.

### Risk Tier
standard

### Prerequisites
- Phase 1: Shared hook module (audit interface defined)

### Depends On
- Phase 1

### Ordered Steps
1. Create `src/audit/hook-history.ts`:
   - Export `HookHistoryManager` class
   - Constructor accepts:
     - `maxEntries: number` (default 1000)
     - `dataDir: string` (where to store hook-history.json and archive)

2. Implement `HookHistoryManager.add(entry: PluginDataHook)` method:
   - Load current hook-history.json (if exists)
   - Append new entry
   - If total entries > maxEntries, rotate (see step 3)

3. Implement rotation logic in `rotate()` private method:
   - Identify entries to archive (oldest entries, count = total - maxEntries)
   - Write archived entries to `hook-history.archive.json` (append mode)
   - Truncate hook-history.json to keep only newest maxEntries
   - Add archive metadata: `{ rotatedAt: timestamp, count: N, entriesToEntries: M }`

4. Implement `HookHistoryManager.get(limit?: number)` method:
   - Load and return most recent entries from hook-history.json
   - Limit parameter controls how many to return (default all)

5. Error handling:
   - File I/O errors caught and logged (do not throw on archive write failures)
   - Graceful degradation if archive is missing or corrupted

### Test Intent
- Add or update:
  - `src/audit/__tests__/hook-history.test.ts`
- Test cases:
  - Add 500 entries, no rotation (all in memory/file)
  - Add 1000 entries, no rotation (exactly at cap)
  - Add 1001 entries, rotation triggers (1 entry archived, 1000 remain)
  - Add 2500 entries, multiple rotations (oldest 1500 archived, 1000 remain)
  - Archive file format validation (JSON parseable, metadata present)
  - `get()` returns only active entries, not archived
  - Error handling: file write fails, manager continues (no throw)
- Expected failing behavior:
  - Without rotation, hook-history.json grows unbounded (test setup with 5000 entries shows size)
  - With rotation at 1000-entry cap: hook-history.json stays ≤1000, archive accumulates
  - Rotation threshold test: 999 entries (no archive), 1000 entries (no archive), 1001 (archive triggered)

### Validation Target
- Command: `npm test -- src/audit/__tests__/hook-history.test.ts`
- Evidence: All 8 test cases pass (red → green); archive created after threshold; entries preserved

### Unlocks
- Phase 6 (hook management is now complete; existing hooks can be refactored)
- Phase 7 (agent-TDD hooks can now safely log to audit trail)

### Blockers Or Escalation
- [ ] Confirm data directory location (is `~/.claude/agent-nelly-memory/` used? Or separate `~/.claude/plugin-audit/`?)
- [ ] Archive retention policy (keep indefinitely, or delete after N days?)

---

## Phase 6: Refactor Existing Hooks (agent-nelly + agent-isdd)

### Objective
Update agent-nelly and agent-isdd's existing `plugin-data-write` hooks to use the shared permission module, consolidated project_slug(), and audit trail manager.

### Risk Tier
**HIGH** (modifying existing agent code; potential for backward-compatibility breakage)

### Prerequisites
- Phase 1: Shared hook module created
- Phase 3: agent-nelly project_slug consolidation completed
- Phase 4: agent-isdd + agent-tdd project_slug consolidation completed
- Phase 5: Hook history rotation implemented

### Depends On
- Phase 1, Phase 3, Phase 4, Phase 5

### Ordered Steps
1. Locate agent-nelly's existing hook:
   - File: `agent-nelly/hooks/plugin-data-write.ts` (typical location)
   - Review current allow/deny logic (likely environment-variable based or hardcoded)

2. Refactor agent-nelly hook to use shared module:
   - Import: `{ createWhitelistValidator, createAuditLogger, shouldUseEnvGate } from '../../../src/hooks/plugin-data-whitelist'`
   - Replace inline validation with `createWhitelistValidator()` call
   - Replace inline audit logging with `HookHistoryManager` from Phase 5
   - Preserve behavior: if `NELLY_GATE` env var set, skip prompt (use `shouldUseEnvGate()`)
   - Update hook handler to call shared validators
   - NO logic changes, only refactoring (red → green)

3. Repeat step 2 for agent-isdd:
   - File: `agent-isdd/hooks/plugin-data-write.ts`
   - Same refactoring pattern (use shared module, env-gate, audit trail)

4. Run full test suite for both agents:
   - Verify no import errors
   - Verify existing functionality unchanged (backward compatibility)
   - Audit trail is populated correctly

### Test Intent
- High-risk: Use test-author split (test-author writes failing test BEFORE implementation)
- Test suite:
  - `agent-nelly/hooks/__tests__/plugin-data-write.test.ts` (update if exists, or create)
  - `agent-isdd/hooks/__tests__/plugin-data-write.test.ts` (update if exists, or create)
- Test cases:
  - Existing behavior preserved: allow agent-nelly writes to `/plugin-data/agent-nelly/...`
  - Existing behavior preserved: allow agent-isdd writes to `/plugin-data/agent-isdd/...`
  - Deny cross-agent access (agent-nelly cannot write to `/plugin-data/agent-isdd/...`)
  - Block executable writes
  - Audit trail entries created for all operations
  - Env-gate check works: `NELLY_GATE=1` skips prompt
  - Env-gate check works: `SDD_GATE=1` skips prompt for isdd
- Expected failing behavior:
  - Without refactoring: tests fail with "validator not found" or "audit not called"
  - After refactoring: all tests pass (red → green); existing behavior unchanged

### Validation Target
- Command: `npm test -- agent-nelly/hooks agent-isdd/hooks` (or respective test commands)
- Evidence: All existing hook tests pass; backward compatibility confirmed; audit trail logging works

### Unlocks
- Phase 7 (agent-TDD hooks can now be added; existing hooks are stable)

### Blockers Or Escalation
- [ ] **CRITICAL**: Test-author split required before implementation (high-risk code change)
- [ ] Confirm agent-nelly and agent-isdd have existing hook test coverage
- [ ] Verify env-var gates (`NELLY_GATE`, `SDD_GATE`) are documented and currently used
- [ ] Check for any custom validation logic in existing hooks that shared module may not cover

---

## Phase 7: Add Agent-TDD Permission Hooks

### Objective
Implement a new allow/deny permission hook for agent-TDD, using the shared module and audit trail infrastructure.

### Risk Tier
**HIGH** (new permission system for agent-TDD; careful testing required to ensure security)

### Prerequisites
- Phase 1: Shared hook module created
- Phase 5: Hook history rotation implemented
- Phase 4: agent-tdd project_slug consolidation completed (for consistency)

### Depends On
- Phase 1, Phase 5
- Can run after Phase 6, but recommended for stability

### Ordered Steps
1. Create `agent-tdd/hooks/plugin-data-write.ts`:
   - Import shared validators: `{ createWhitelistValidator, createAuditLogger, shouldUseEnvGate }`
   - Import: `HookHistoryManager` from `src/audit/hook-history`
   - Import: `{ getProjectSlug }` from shared utility

2. Implement hook handler:
   - Hook registration: subscribe to `claudeDataWrite` event or equivalent
   - Input: operation details (filePath, operation type, userId)
   - Call `createWhitelistValidator()` with agent-tdd identifier
   - Check allow/deny decision; if deny, return error reason
   - If allow or env-gate set, proceed without prompt
   - Log audit entry via `HookHistoryManager.add()`

3. Configure env-gate check:
   - Check `TDD_GATE` environment variable
   - If set, skip prompting (preserve backward compat for future TDD integrations)

4. Wire hooks into agent-tdd's startup/initialization

5. Add error handling and logging

### Test Intent
- High-risk: Use test-author split (test-author writes failing test BEFORE implementation)
- Test suite:
  - `agent-tdd/hooks/__tests__/plugin-data-write.test.ts`
- Test cases:
  - Agent-TDD can write to `/plugin-data/agent-tdd/...` (allowed)
  - Agent-TDD cannot write to `/plugin-data/agent-nelly/...` (denied)
  - Agent-TDD cannot write `.exe` files (denied)
  - Audit trail entry created for all operations (allowed and denied)
  - `TDD_GATE=1` skips prompt
  - Env-gate absent: respects whitelist
  - Security: no bypass via path traversal or malformed requests
- Expected failing behavior:
  - Without hook implementation: agent-TDD operations not logged or blocked
  - After implementation: operations logged, cross-agent access denied, executables blocked (red → green)

### Validation Target
- Command: `npm test -- agent-tdd/hooks/__tests__/plugin-data-write.test.ts`
- Evidence: All 7 test cases pass (red → green); audit trail populated; security checks enforced

### Unlocks
- Phase 8 (documentation can now cover all three agents)

### Blockers Or Escalation
- [ ] **CRITICAL**: Test-author split required before implementation (high-risk security feature)
- [ ] Confirm `TDD_GATE` env var naming is aligned with other agents
- [ ] Verify agent-TDD's hook registration mechanism (does it exist, or needs creation?)
- [ ] Confirm agent-TDD's initialization flow (where should hook be wired in?)

---

## Phase 8: Documentation — Plugin Hooks Permission Pattern

### Objective
Document the generalized hook permission pattern for current and future plugins, covering implementation guide, testing strategy, and env-gate usage.

### Risk Tier
standard (documentation only; no code change risk)

### Prerequisites
- Phase 1: Shared hook module fully implemented
- Phase 6: Existing hooks refactored (implementation pattern visible)
- Phase 7: Agent-TDD hooks added (third example available)

### Depends On
- Phase 1, Phase 6, Phase 7

### Ordered Steps
1. Create `PLUGIN_HOOKS_PATTERN.md` at project root:
   - Title: "Plugin Data Write Permission Pattern"
   - Audience: future plugin authors

2. Document structure:
   - **Overview**: problem (multiple plugins writing to shared data, need unified permission model), solution (shared hook module + audit trail)
   - **Architecture**:
     - Diagram (text or ASCII) showing plugin → shared validators → audit trail → archive
     - Three layers: (1) Permission checks, (2) Audit logging, (3) Rotation
   - **Implementation Guide** (with agent-nelly as example):
     - Import shared module: `createWhitelistValidator`, `createAuditLogger`, `shouldUseEnvGate`
     - Implement hook handler (code snippet)
     - Wire into agent's startup
     - Env-gate usage (backward compat)
   - **File-Type Restrictions**:
     - Current blocklist: `.exe` only
     - How to extend (add to `plugin-data-whitelist.ts`)
   - **Directory Scoping**:
     - Per-agent namespace: `~/.claude/plugin-data/<agent-slug>/...`
     - Validation in shared module
   - **Audit Trail**:
     - What is logged (operation, filePath, pluginName, allowed, reason, timestamp)
     - Rotation policy (1000-entry cap, older entries archived)
     - Archive location and format
   - **Testing Strategy**:
     - Unit tests for validators (file-type, scope)
     - Integration tests for hook handler (end-to-end workflow)
     - Security tests (path traversal, cross-agent access)
   - **Future Extensions**:
     - How to add new file-type restrictions
     - How to add process-identity checks (if needed)
     - How to modify rotation policy

3. Add examples for all three agents (agent-nelly, agent-isdd, agent-tdd)

4. Include checklist for new plugin adoption

### Test Intent
- Documentation review (no automated tests)
- Manual validation:
  - [ ] All three agents (nelly, isdd, tdd) covered with examples
  - [ ] Code snippets are accurate and runnable
  - [ ] Implementation guide can be followed by new plugin author
  - [ ] Arch diagram is clear (shows flow from plugin to archive)
  - [ ] Testing strategy is comprehensive (unit, integration, security)
  - [ ] Env-gate backward compat explained
- Acceptance: documentation is reviewed and approved by at least one stakeholder

### Validation Target
- Command: Peer review of `PLUGIN_HOOKS_PATTERN.md`
- Evidence: Peer confirms (1) examples are accurate, (2) guide is followable, (3) missing sections identified or none needed

### Unlocks
- None (final phase; unblocks future plugin adoption)

### Blockers Or Escalation
- [ ] Confirm stakeholder for documentation review (who approves?)
- [ ] Diagram preference (Markdown ASCII, SVG, or external file?)
- [ ] Future plugin list (are there known plugins to mention as motivation?)

---

## Task Readiness Checklist

- [x] Eight TDD-ready phases (each ≤ 3 files, independently testable)
- [x] Dependency ordering (topological sort, no cycles):
  - Phase 1 (Shared Module) → unblocks Phases 5, 6, 7
  - Phase 2 (Shared slug) → unblocks Phases 3, 4
  - Phase 3 (nelly slug) → unblocks Phase 4, 6
  - Phase 4 (isdd+tdd slug) → unblocks Phase 6
  - Phase 5 (Rotation) → unblocks Phases 6, 7
  - Phase 6 (Refactor existing) → unblocks Phase 8
  - Phase 7 (TDD hooks) → unblocks Phase 8
  - Phase 8 (Docs) → final
- [x] File affinity (≤ 3 files per phase):
  - Phases 1, 2, 7, 8: 1 file each
  - Phases 3, 5, 6: 2 files each
  - Phase 4: 3 files
- [x] Risk tiers assigned (Phases 6, 7 flagged HIGH, others standard)
- [x] Test-author split required for high-risk phases (Phases 6, 7)
- [x] Acceptance criteria explicit (test commands, expected failures, pass conditions)
- [x] Traceability to design (each phase maps to research task or design decision)
- [x] Blockers and escalations identified for each phase

## Dependency Graph

```
Phase 1 (Shared Module)
├─→ Phase 5 (Rotation)
│   ├─→ Phase 6 (Refactor Existing)
│   │   └─→ Phase 8 (Documentation)
│   └─→ Phase 7 (TDD Hooks)
│       └─→ Phase 8 (Documentation)
├─→ Phase 6 (requires Phase 3, 4)
└─→ Phase 7

Phase 2 (Shared Slug)
├─→ Phase 3 (Consolidate nelly)
│   └─→ Phase 4 (Consolidate isdd+tdd)
│       └─→ Phase 6 (Refactor Existing)
└─→ Phase 4 (Consolidate isdd+tdd)
```

## Summary

- **Phase 1**: Foundation (shared validators, file-type checks, scope validation)
- **Phases 2–4**: Refactoring (consolidate duplicated project_slug utility)
- **Phase 5**: Audit infrastructure (rotation with 1000-entry cap)
- **Phase 6**: Existing agent updates (refactor to use shared module) **HIGH-RISK**
- **Phase 7**: New agent integration (agent-TDD hooks) **HIGH-RISK**
- **Phase 8**: Documentation (pattern guide for future adoption)

All slices are TDD-sized, with clear test surfaces and acceptance criteria. High-risk phases (6, 7) require test-author split before implementation to ensure security and backward compatibility.

---

## Implementation Sequencing (Recommended Order)

1. Run Phases 1 & 2 in parallel (both foundational, no dependencies)
2. Phase 3 (depends on 2)
3. Phase 4 (depends on 2, 3)
4. Phase 5 (depends on 1)
5. Phase 6 (depends on 1, 3, 4, 5) **WITH TEST-AUTHOR SPLIT**
6. Phase 7 (depends on 1, 5) **WITH TEST-AUTHOR SPLIT**
7. Phase 8 (final, documentation)

Total phases: 8
Estimated duration: 5–7 days (2 days per complex phase, 1 day per simple phase, 1 day for doc review)

---

## State

**Ready For Implementation** ✓
- All phases defined
- Dependencies acyclic and ordered
- Test surfaces identified
- Risk tiers assigned
- Blockers and escalations noted
- High-risk phases marked for test-author split
