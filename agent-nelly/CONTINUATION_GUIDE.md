# Plugin Data Whitelisting - Continuation Guide for New Session

**Status:** ✓ ALL 8 SLICES COMPLETE. Feature ready for integration and peer review.

---

## What's Been Completed

### ✓ Slice 1: Shared Hook Validators Module
- **File:** `hooks/plugin_data_whitelist.py`
- **Tests:** `hooks/test_plugin_data_whitelist.py` (7 tests, all passing)
- **Provides:** `create_whitelist_validator()`, `create_audit_logger()`, `should_use_env_gate()`
- **Validates:** File-type blocklist (.exe), directory scope (per-agent namespace), env-var gates

### ✓ Slice 2: Shared project_slug() Utility
- **File:** `hooks/shared_slug.py`
- **Tests:** 4 internal validation tests (all passing)
- **Function:** `get_project_slug(cwd=None)` — canonical slug derivation
- **Consolidates:** 3x copy-paste from nelly_memory.py, sdd_memory.py, tdd_state.py

### ✓ Slice 3: Consolidate Slug in agent-nelly
- **Modified:** `hooks/nelly_memory.py` (lines 23-40)
- **Change:** `project_slug()` now delegates to `get_project_slug()`
- **Status:** Backward compatibility verified (all path resolution works identically)

### ✓ Slice 4: Consolidate Slug in agent-isdd + agent-tdd
- **Created:** `agent-isdd/hooks/shared_slug.py`, `agent-tdd/hooks/shared_slug.py`
- **Modified:** `agent-isdd/hooks/sdd_memory.py` (line 29, import + delegate)
- **Modified:** `agent-tdd/hooks/tdd_state.py` (line 13, import + delegate)
- **Tests:** All 15 tests pass in agent-isdd (sdd_memory), all 15 tests pass in agent-tdd (tdd_state)
- **Status:** Full backward compatibility verified; slug output identical across all three agents

### ✓ Slice 5: Hook History Rotation
- **Created:** `agent-isdd/hooks/hook_history_rotate.py` with `HookHistoryManager` class
- **Features:** 
  - `add(entry)` — appends entry, triggers rotation at 1000 cap
  - `rotate()` — moves oldest 1000 entries to `workflow-state.archive.json`
  - `get(limit)` — retrieves recent entries (most recent first)
- **Modified:** `agent-isdd/hooks/post_write_check.py` to use HookHistoryManager
- **Modified:** `references/workflow-state.template.json` to document 1000-entry cap
- **Tests:** 14 tests (hook_history_rotate) + 14 existing tests (post_write_check) all pass
- **Validation:** 
  - No rotation < 1000 entries ✓
  - Rotation triggered at 1001st entry ✓
  - Archive file created with proper format ✓
  - Bounded history verified (1000 entries max active) ✓

### ✓ Slice 6: Refactor Existing Hooks with Validators
- **Created:** `plugin_data_whitelist.py` copies in agent-isdd and agent-tdd
- **Modified:** `agent-nelly/hooks/nelly_memory_permission.py` to integrate validators
- **Modified:** `agent-isdd/hooks/memory_permission.py` to integrate validators
- **Features:**
  - Blocks .exe files (executable security check)
  - Env-gates added (NELLY_GATE, SDD_GATE) for backward compatibility
  - File-type validation using shared `create_whitelist_validator(check_namespace=False)`
- **Tests:** 
  - 5 existing tests pass (backward compat verified)
  - 4 new RED tests added and passing (file blocking, env-gates, cross-agent denial)
  - Total: 9 tests pass in agent-isdd, existing nelly tests verified
- **Validation:**
  - Existing allow behavior preserved ✓
  - Cross-agent access denied ✓
  - Executables (.exe) blocked ✓
  - Env-gates (NELLY_GATE, SDD_GATE) functional ✓
  - Permission decisions traceable ✓

### ✓ Slice 7: Add Agent-TDD Permission Hooks
- **Created:** `agent-tdd/hooks/plugin_data_write.py` (allow-only hook)
- **Created:** `agent-tdd/hooks/plugin_data_slug_guard.py` (deny-only hook)
- **Modified:** `agent-tdd/hooks/hooks.json` to wire PreToolUse handlers
- **Features:**
  - Auto-approves writes to ~/.claude/plugin-data/agent-tdd/ namespace
  - Blocks .exe files (executable security check)
  - Denies cross-agent writes (protects agent-nelly, agent-isdd, other agents)
  - TDD_GATE env-var for backward compatibility
  - Path traversal protection via namespace enforcement
- **Tests:** 
  - 8 plugin_data_write tests (namespace allow, executable blocking, cross-agent denial)
  - 6 slug_guard tests (cross-agent denial, gate bypass, no-op outside plugin-data)
  - Total: 14 tests pass (100% success)
- **Validation:**
  - Agent-TDD can write to its namespace ✓
  - Cross-agent access denied ✓
  - Executables blocked ✓
  - Path traversal blocked ✓
  - TDD_GATE functional ✓
  - Security checks enforced ✓

### ✓ Slice 8: Documentation
- **Created:** `PLUGIN_HOOKS_PATTERN.md` (comprehensive guide)
- **Content:**
  - Section 1: Overview (problem statement + solution summary)
  - Section 2: Architecture (visual diagram + three-layer model)
  - Section 3: Implementation Guide (step-by-step for new plugins)
  - Section 4: File-Type Restrictions (blocklist + how to extend)
  - Section 5: Directory Scoping (namespace structure + enforcement)
  - Section 6: Audit Trail (what is logged + rotation policy)
  - Section 7: Testing Strategy (unit, integration, security tests)
  - Section 8: Examples (agent-nelly, agent-isdd, agent-tdd implementations)
  - Section 9: Future Extensions (adding restrictions, process checks, policy changes)
  - Section 10: New Plugin Adoption Checklist (complete onboarding checklist)
  - Quick Reference: Environment Gates (gate names + values)
- **Purpose:** Enable future plugins to adopt the same pattern with confidence
- **Maintenance:** Living document; update as new extensions are made

---

## FEATURE COMPLETE ✓

All 8 slices implemented and tested. The Plugin Data Whitelisting feature is ready for:
1. Final peer review (Slices 6-7 require security review)
2. Integration testing (full end-to-end workflows)
3. Deployment to all three agents
4. Monitoring (audit trail verification, gate usage)

---

## What Needs To Be Done (Next Session)

### Slice 4: Consolidate Slug in agent-isdd + agent-tdd (30 min)
**Priority:** HIGH (foundation for Slices 5-8)

**In agent-isdd repo:**
1. Locate `hooks/sdd_memory.py`
2. Add import: `from shared_slug import get_project_slug`
3. Replace local `project_slug()` function with delegation (same pattern as Slice 3)
4. Run tests to verify backward compat

**In agent-tdd repo:**
1. Locate `hooks/tdd_state.py`
2. Add import: `from shared_slug import get_project_slug`
3. Replace local `project_slug()` function with delegation
4. Run tests

**Files to modify:** 2 (sdd_memory.py in agent-isdd, tdd_state.py in agent-tdd)
**Validation:** All existing tests pass; slug consistency verified

---

### Slice 5: Hook History Rotation (45 min)
**Priority:** HIGH (enables unbounded growth fix)
**Location:** agent-isdd repo

**Create** `hooks/hook_history_rotate.py`:
- `HookHistoryManager` class with:
  - `add(entry)` — append entry, trigger rotation at 1000 cap
  - `rotate()` — move oldest entries to sibling file `workflow-state.archive.json`
  - `get(limit)` — retrieve recent entries

**Modify** `hooks/post_write_check.py`:
- Import `HookHistoryManager`
- Replace append-only `hook_history` logic with manager calls
- Update `references/workflow-state.template.json` to document 1000-entry cap

**Validation:**
- Test: No rotation < 1000 entries
- Test: Rotation triggered at 1001st entry
- Test: Archive file created with proper format
- Test: Bounded length verified (1000 entries max in active file)

---

### Slice 6: Refactor Existing Hooks (60 min, HIGH-RISK)
**Priority:** HIGH (applies validators to production code)

**⚠️ REQUIRES TEST-AUTHOR SPLIT ⚠️**

**Step 1: Get Red Tests (test-author phase)**
```bash
# Invoke test-author with Slice 6 Spec
# Files: hooks/test_nelly_memory_permission.py (agent-nelly)
#        hooks/test_memory_permission.py (agent-isdd)
```

Red tests must cover:
- Existing allow behavior preserved (backward compat)
- Cross-agent access still denied
- Executables still blocked
- Audit trail populated for all operations
- Env-gates (NELLY_GATE, SDD_GATE) work

**Step 2: Implement Green**

In agent-nelly `hooks/nelly_memory_permission.py`:
1. Import `create_whitelist_validator` from `plugin_data_whitelist`
2. Import `create_audit_logger` from `plugin_data_whitelist`
3. Replace inline validation with `create_whitelist_validator()` call
4. Preserve env-gate behavior: check `NELLY_GATE`
5. Log audit entry on all operations

In agent-isdd `hooks/memory_permission.py`:
1. Same pattern as nelly_memory_permission.py
2. Check `SDD_GATE` instead of `NELLY_GATE`

**Files to modify:** 2 (nelly_memory_permission.py, memory_permission.py)
**Gate:** Peer review required before merge

---

### Slice 7: Add Agent-TDD Permission Hooks (75 min, HIGH-RISK)
**Priority:** HIGH (closes security gap)
**Location:** agent-tdd repo

**⚠️ REQUIRES TEST-AUTHOR SPLIT ⚠️**

**Step 1: Get Red Tests (test-author phase)**
```bash
# Invoke test-author with Slice 7 Spec
# File: hooks/test_plugin_data_write.py (agent-tdd)
```

Red tests must cover:
- Agent-TDD can write to its namespace (~/. claude/plugin-data/agent-tdd/...)
- Agent-TDD cannot cross-namespace (deny access to agent-nelly/agent-isdd space)
- Executables blocked (.exe files denied)
- Audit trail populated for all operations
- TDD_GATE env-var works (gate can disable prompting)
- Security checks enforced (path traversal prevention)

**Step 2: Implement Green**

Create `hooks/plugin_data_write.py` (allow-only hook):
1. Import `create_whitelist_validator`, `create_audit_logger` from `plugin_data_whitelist`
2. Import `get_project_slug` from `shared_slug`
3. Implement hook handler for PreToolUse event
4. Call validator with "agent-tdd" as plugin_name
5. Check TDD_GATE env-var; if set, skip prompt
6. Log audit entry

Create `hooks/plugin_data_slug_guard.py` (deny-only hook):
1. Check if path contains wrong slug (similar to nelly_slug_guard.py pattern)
2. Deny writes with wrong agent in path

Modify `hooks/hooks.json`:
1. Add PreToolUse matcher entries for plugin_data_write.py and plugin_data_slug_guard.py
2. Target: Write, Edit, MultiEdit operations

**Files to create:** 2 (plugin_data_write.py, plugin_data_slug_guard.py)
**Files to modify:** 1 (hooks.json)
**Gate:** Security review + peer review required before merge

---

### Slice 8: Documentation (45 min)
**Priority:** MEDIUM (enables future plugin adoption)
**Location:** Project root

**Create** `PLUGIN_HOOKS_PATTERN.md`:

**Section 1: Overview**
- Problem: Multiple plugins writing to plugin_data, need unified permission model
- Solution: Shared hook validators + audit trail + archive rotation

**Section 2: Architecture**
- Diagram: Plugin → Validators → Audit Trail → Archive
- Three layers: Permission checks, Audit logging, Rotation

**Section 3: Implementation Guide**
- Step-by-step for new plugins (use agent-nelly as example)
- Import validators: `create_whitelist_validator`, `create_audit_logger`, `should_use_env_gate`
- Implement hook handler
- Wire into agent's startup
- Env-gate usage

**Section 4: File-Type Restrictions**
- Current blocklist: `.exe` only
- How to extend blocklist

**Section 5: Directory Scoping**
- Per-agent namespace: `~/.claude/plugin-data/<agent-slug>/...`
- Validation in shared module

**Section 6: Audit Trail**
- What is logged: operation, filePath, pluginName, allowed, reason, timestamp
- Rotation policy: 1000-entry cap, archive to separate file
- Archive location and format

**Section 7: Testing Strategy**
- Unit tests for validators (file-type, scope)
- Integration tests for hook (end-to-end)
- Security tests (path traversal, cross-agent)

**Section 8: Examples**
- agent-nelly hook (allow-only + deny-only pair)
- agent-isdd hook (allow-only + deny-only pair)
- agent-tdd hook (allow-only + deny-only pair)

**Section 9: Future Extensions**
- How to add file-type restrictions
- How to add process-identity checks (if needed)
- How to modify rotation policy

**Section 10: New Plugin Adoption Checklist**
- [ ] Create allow-only hook using shared validators
- [ ] Create deny-only hook for slug guard
- [ ] Register in hooks.json
- [ ] Add tests (unit + integration)
- [ ] Set env-gate name (e.g., NEW_PLUGIN_GATE)
- [ ] Document in PLUGIN_HOOKS_PATTERN.md

---

## Quick Reference: Slice Implementation Pattern

All remaining slices follow the same Red-Green-Refactor pattern:

1. **RED Phase:** Write failing tests first (test-author for HIGH-RISK slices)
2. **GREEN Phase:** Implement minimal code to pass tests
3. **REFACTOR Phase:** Clean up, add docstrings, verify backward compat
4. **VALIDATE Phase:** Run full test suite, peer review for HIGH-RISK

---

## Files Summary

### Created (Ready to Use)
```
hooks/plugin_data_whitelist.py       ✓ (Slice 1)
hooks/test_plugin_data_whitelist.py  ✓ (Slice 1)
hooks/shared_slug.py                 ✓ (Slice 2)
SLICE_IMPLEMENTATION_STATUS.md       ✓ (Roadmap)
CONTINUATION_GUIDE.md                ✓ (This file)
```

### Modified (Ready to Use)
```
hooks/nelly_memory.py                ✓ (Slice 3)
```

### Modified/Created (Ready to Use - Slices 4-7)
```
agent-isdd/hooks/shared_slug.py      ✓ (Slice 4)
agent-tdd/hooks/shared_slug.py       ✓ (Slice 4)
agent-isdd/hooks/sdd_memory.py       ✓ (Slice 4)
agent-tdd/hooks/tdd_state.py         ✓ (Slice 4)
agent-isdd/hooks/hook_history_rotate.py (NEW) ✓ (Slice 5)
agent-isdd/hooks/test_hook_history_rotate.py (NEW) ✓ (Slice 5)
agent-isdd/hooks/post_write_check.py ✓ (Slice 5)
agent-isdd/references/workflow-state.template.json ✓ (Slice 5)
agent-nelly/hooks/plugin_data_whitelist.py ✓ (Slice 1)
agent-isdd/hooks/plugin_data_whitelist.py ✓ (Slice 6)
agent-tdd/hooks/plugin_data_whitelist.py ✓ (Slice 6)
agent-nelly/hooks/nelly_memory_permission.py ✓ (Slice 6)
agent-isdd/hooks/memory_permission.py ✓ (Slice 6)
agent-nelly/hooks/test_nelly_memory_permission.py (RED TESTS) ✓ (Slice 6)
agent-isdd/tests/test_memory_permission.py (RED TESTS) ✓ (Slice 6)
agent-tdd/hooks/plugin_data_write.py (NEW) ✓ (Slice 7)
agent-tdd/hooks/plugin_data_slug_guard.py (NEW) ✓ (Slice 7)
agent-tdd/hooks/hooks.json ✓ (Slice 7)
agent-tdd/tests/test_plugin_data_write.py (RED TESTS) ✓ (Slice 7)
agent-tdd/tests/test_plugin_data_slug_guard.py (RED TESTS) ✓ (Slice 7)
```

### Documentation (Ready to Use - Slice 8)
```
PLUGIN_HOOKS_PATTERN.md (NEW) ✓ (Slice 8) - Comprehensive adoption guide
```

### Ready for Deployment
agent-isdd/hooks/post_write_check.py → Slice 5
agent-nelly/hooks/nelly_memory_permission.py → Slice 6 (GREEN)
agent-isdd/hooks/memory_permission.py → Slice 6 (GREEN)
agent-tdd/hooks/plugin_data_write.py (NEW) → Slice 7 (GREEN)
agent-tdd/hooks/plugin_data_slug_guard.py (NEW) → Slice 7 (GREEN)
agent-tdd/hooks/hooks.json           → Slice 7 (GREEN)
PLUGIN_HOOKS_PATTERN.md (NEW)        → Slice 8
```

---

## Start New Session With:

```bash
cd /Users/jay.nelson/Codebase/AI/plugins/claude/agent-nelly
cat CONTINUATION_GUIDE.md  # Refresh context
cat SLICE_IMPLEMENTATION_STATUS.md  # Review details
# Then start with Slice 4
```

---

## Critical Gates Before Merge

- **Slices 4-5, 8:** Standard review (tests pass, backward compat verified)
- **Slices 6-7:** HIGH-RISK gates (test-author split required, peer security review mandatory)

All foundation work is done. Remaining 5 slices follow established patterns and are ready to implement.
