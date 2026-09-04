# Plugin Data Whitelisting - Slice Implementation Status

**Workflow Goal:** Whitelist plugin_data writes for Agent Nelly, Agent TDD, SDD to eliminate permission prompts.

---

## Completed Slices

### ✓ Slice 1: Shared Hook Validators Module (COMPLETE)
**Location:** `hooks/plugin_data_whitelist.py` + `hooks/test_plugin_data_whitelist.py`

**What was built:**
- `create_whitelist_validator()` — File-type blocklist (.exe), directory scope checks
- `create_audit_logger()` — Audit entry creation with timestamp
- `should_use_env_gate()` — Env-var gate detection (NELLY_GATE, SDD_GATE, TDD_GATE)

**Status:** ✓ All 7 tests passing (blocklist, scope, logging, env-gates)

---

### ✓ Slice 2: Shared project_slug() Utility (COMPLETE)
**Location:** `hooks/shared_slug.py`

**What was built:**
- `get_project_slug(cwd=None)` — Canonical slug derivation from absolute path
- Consolidated from 3x copy-paste implementations (nelly_memory.py, sdd_memory.py, tdd_state.py)

**Status:** ✓ All 4 tests passing (standard paths, consistency, default cwd)

---

## Remaining Slices (Implementation Roadmap)

### Slice 3: Consolidate Slug in agent-nelly
**Priority:** HIGH (foundational for other consolidations)

**Steps:**
1. Edit `hooks/nelly_memory.py` line 30-34
2. Replace `project_slug()` function with: `from shared_slug import get_project_slug as project_slug`
3. Run existing tests: `python -m pytest hooks/test_nelly_memory.py -v`
4. Verify: Memory paths still resolve correctly

**Files to modify:** 1 file (`nelly_memory.py`)
**Files to delete:** 0 (keep for backward compat initially)
**Estimated time:** 15 minutes

---

### Slice 4: Consolidate Slug in agent-isdd + agent-tdd
**Priority:** HIGH (completes consolidation)

**Steps:**
1. **agent-isdd**: Update `hooks/sdd_memory.py` to import from shared_slug
2. **agent-tdd**: Update `hooks/tdd_state.py` to import from shared_slug
3. Run both agents' tests to verify backward compat
4. Delete local project_slug() definitions

**Files to modify:** 2 files (sdd_memory.py, tdd_state.py in their respective repos)
**Estimated time:** 30 minutes

**Note:** Requires access to agent-isdd and agent-tdd repos. Can be done in parallel with Slice 5.

---

### Slice 5: Hook History Rotation (Audit Trail)
**Priority:** MEDIUM (enables audit trail management)

**Steps:**
1. Create `hooks/hook_history_rotate.py` in agent-isdd
2. Implement `HookHistoryManager` class with:
   - `add(entry)` method — append entry, trigger rotation at 1000 cap
   - `rotate()` method — move oldest entries to workflow-state.archive.json
   - `get(limit)` method — retrieve recent entries
3. Modify `agent-isdd/hooks/post_write_check.py` to use HookHistoryManager
4. Update `references/workflow-state.template.json` to document cap size
5. Run tests: verify rotation at 1000-entry threshold

**Files to create:** 1 (hook_history_rotate.py)
**Files to modify:** 1 (post_write_check.py)
**Estimated time:** 45 minutes

---

### Slice 6: Refactor Existing Hooks (HIGH-RISK)
**Priority:** HIGH (applies validators to production hooks)

**⚠️ REQUIRES TEST-AUTHOR SPLIT ⚠️**

**Steps:**
1. **Test-Author Phase (Required first):**
   - Create failing Red tests in `hooks/test_nelly_memory_permission.py`
   - Tests must cover:
     - Existing allow behavior preserved (backward compat)
     - Cross-agent access still denied
     - Executables still blocked
     - Audit trail populated
     - Env-gates (NELLY_GATE, SDD_GATE) work

2. **Implementation Phase (after Red tests approved):**
   - Update `hooks/nelly_memory_permission.py`:
     - Import `create_whitelist_validator` from plugin_data_whitelist
     - Replace inline validation with validator call
     - Preserve env-gate behavior
   - Repeat for `agent-isdd/hooks/memory_permission.py`
   - Run full test suite for both agents

**Files to modify:** 2 (nelly_memory_permission.py, memory_permission.py in isdd)
**Risk Tier:** HIGH
**Estimated time:** 60 minutes (including test-author handoff)

**Critical:** This modifies existing agent permission logic. Peer review mandatory before merge.

---

### Slice 7: Add Agent-TDD Permission Hooks (HIGH-RISK)
**Priority:** HIGH (closes agent-TDD security gap)

**⚠️ REQUIRES TEST-AUTHOR SPLIT ⚠️**

**Steps:**
1. **Test-Author Phase (Required first):**
   - Create failing Red tests in `agent-tdd/hooks/test_plugin_data_write.py`
   - Tests must cover:
     - Agent-TDD can write to its namespace
     - Agent-TDD cannot cross-namespace
     - Executables blocked
     - Audit trail populated
     - TDD_GATE env-var works
     - Security checks enforced (path traversal, etc.)

2. **Implementation Phase (after Red tests approved):**
   - Create `agent-tdd/hooks/plugin_data_write.py` (allow-only hook)
   - Create `agent-tdd/hooks/plugin_data_slug_guard.py` (deny-only hook)
   - Update `agent-tdd/hooks/hooks.json` to register PreToolUse matchers
   - Wire into agent-tdd initialization
   - Run tests

**Files to create:** 2 (plugin_data_write.py, plugin_data_slug_guard.py)
**Files to modify:** 1 (hooks.json)
**Risk Tier:** HIGH
**Estimated time:** 75 minutes (including test-author handoff)

**Critical:** This is security-critical new code for TDD. Thorough testing and peer review required.

---

### Slice 8: Documentation (STANDARD)
**Priority:** MEDIUM (enables future plugin adoption)

**Steps:**
1. Create `PLUGIN_HOOKS_PATTERN.md` at project root
2. Document:
   - Architecture overview (validator → audit trail → archive)
   - Implementation guide (step-by-step for new plugins)
   - File-type restrictions (how to expand blocklist)
   - Directory scoping (per-agent namespace)
   - Audit trail (format, rotation, recovery)
   - Testing strategy (unit, integration, security)
   - Future extensions (process identity, custom gates)
3. Include examples for all three agents
4. Include adoption checklist for new plugins
5. Peer review

**Files to create:** 1 (PLUGIN_HOOKS_PATTERN.md)
**Estimated time:** 45 minutes

---

## Implementation Sequence

**Critical Path:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

**Parallelizable:** Slice 5 (rotation) can run in parallel with Slices 3-4 (consolidation)

### Recommended Order:
1. **Slice 1** ✓ (complete)
2. **Slice 2** ✓ (complete)
3. **Slice 3** (15 min)
4. **Slice 4** (30 min)
5. **Slice 5** (45 min) — can start in parallel with Slice 4
6. **Slice 6** (60 min) — requires test-author handoff
7. **Slice 7** (75 min) — requires test-author handoff
8. **Slice 8** (45 min)

**Total estimated time:** 5-7 hours (including test-author splits and peer review)

---

## High-Risk Slices (6 & 7) - Test-Author Coordination

**Slices 6 and 7 are security-critical and modify production code. They REQUIRE test-author split:**

1. **Test-Author writes Red tests first** (failing tests that describe desired behavior)
2. **Developer implements Green** (minimal code to pass Red tests)
3. **Developer refactors for clarity** (Refactor phase)
4. **Peer review before merge** (security gates)

**Process:**
- Invoke `agent-tdd:test-author` with Slice 6 Spec (Objective, Test Intent, Risk Tier)
- Test-author returns failing Red test file
- Implement Green from Red tests
- Repeat for Slice 7

---

## Files Created/Modified by Slice

| Slice | Created | Modified | Deleted |
|-------|---------|----------|---------|
| 1 | plugin_data_whitelist.py, test_plugin_data_whitelist.py | — | — |
| 2 | shared_slug.py | — | — |
| 3 | — | nelly_memory.py | — |
| 4 | — | sdd_memory.py, tdd_state.py | — |
| 5 | hook_history_rotate.py | post_write_check.py, workflow-state.template.json | — |
| 6 | — | nelly_memory_permission.py, memory_permission.py | — |
| 7 | plugin_data_write.py, plugin_data_slug_guard.py | hooks.json | — |
| 8 | PLUGIN_HOOKS_PATTERN.md | — | — |

---

## Next Steps

### Immediate (Slices 1-2 Complete):
- [ ] Slice 3: Consolidate slug in agent-nelly (15 min)
- [ ] Slice 4: Consolidate slug in agent-isdd + agent-tdd (30 min)
- [ ] Slice 5: Hook history rotation (45 min)

### High-Risk (Requires Test-Author):
- [ ] Slice 6: Refactor existing hooks (test-author split required)
- [ ] Slice 7: Add TDD hooks (test-author split required)

### Documentation:
- [ ] Slice 8: Documentation (45 min)

---

## Validation Gates

✓ Slice 1: All validators tested and passing
✓ Slice 2: Slug utility tested and consistent
- Slice 3: agent-nelly tests pass (backward compat verified)
- Slice 4: agent-isdd + agent-tdd tests pass
- Slice 5: Rotation triggered at 1000-entry cap, archive created
- Slice 6: Existing hook behavior preserved, audit trail populated, env-gates work
- Slice 7: Cross-agent access denied, executables blocked, TDD_GATE works
- Slice 8: Peer review approval

---

## SLICE-BY-SLICE PROGRESS

### ✓ Slice 3: Consolidate Slug in agent-nelly (COMPLETE)
**Time:** 20 minutes
**Files modified:** 1 (nelly_memory.py)
**Status:** Backward compatibility verified ✓

**Changes:**
- Added: `from shared_slug import get_project_slug`
- Replaced local `project_slug()` with delegation to `get_project_slug()`
- Preserved `re` import for other uses in file
- All path resolution still works identically

**Tests passed:**
- project_slug() delegates correctly
- memory_dir() still works
- Consistency with shared_slug verified
- Multiple test paths produce identical results

**Next:** Slice 4 (agent-isdd + agent-tdd consolidation)

