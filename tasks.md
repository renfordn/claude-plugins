# Tasks: Prevent Interop Drift Between Plugins

## Slice 1: Schema Extraction Module (Mechanical Parser)

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** plugin-orchestrator/orchestrator/schema_extractor.py  

### Test Intent
Parse INTEROP.md files (all 6 plugins) into a queryable schema registry; handle multiple markdown formats (prose bullets, tables, code blocks); extract field names and types without regex brittleness.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_schema_extractor -v
```
(New test file testing extraction from real + synthetic INTEROP.md examples)

### Ordered Steps
1. Create `schema_extractor.py` with `SchemaRegistry` class; define `Schema` and `Field` data classes (name, type_name, required, description).
2. Implement `extract_from_file(path: str) -> Schema` parsing logic:
   - Handle bullet-point format (e.g., "- field_name: type description")
   - Handle markdown table format (columns: field, type, required)
   - Handle sub-schema blocks (nested objects, arrays) seen in agent-tdd/INTEROP.md
   - Graceful fallback on parse failure (log warning, return empty schema)
3. Implement `extract_all_plugins(base_dir: str) -> Dict[str, Schema]` registry builder; scan all known plugin directories (agent-isdd, agent-tdd, code-reviewer, agent-nelly, agent-ux, plugin-orchestrator).
4. Add caching layer: compute sha256 of INTEROP.md before/after, skip re-parse if unchanged (performance constraint: all 6 files parsed in <100ms).
5. Add CLI entry point: `if __name__ == "__main__": python schema_extractor.py --check` validates all schemas locally, outputs summary (0 errors/warnings = exit 0).
6. Write unit tests: parsing edge cases (missing colons, malformed tables, nested objects), all 6 real INTEROP.md files, performance benchmark (<100ms).

---

## Slice 2: Refactor interop_parser.py (Backwards Compatible)

**Risk Tier:** high-risk  
**Depends On:** Slice 1  
**Files:** plugin-orchestrator/orchestrator/interop_parser.py, plugin-orchestrator/tests/test_capability_map.py  

### Test Intent
Replace hardcoded plugin schemas in `_extract_capabilities()` (lines 313–327, 336–340, etc.) with runtime lookups from the SchemaRegistry (Slice 1); all 30 existing capability tests must pass unchanged; `Capability.consumes` shape (Dict[str, str]) unchanged.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_capability_map -v
```
(30 existing tests, all must pass; no new tests needed for this slice)

### Ordered Steps
1. Import SchemaRegistry from schema_extractor.py; initialize in CapabilityMap.__init__().
2. Refactor `_extract_capabilities()` method: replace hardcoded `if/elif` blocks for agent-tdd, agent-nelly, agent-cache-plugin, etc. with `registry.get_schema(plugin_name)` lookups.
3. For each plugin, map detected capability (e.g., "Design Spec" in content) → schema lookup by plugin name. If schema not found, fall back to empty dict {} (graceful degradation).
4. Preserve Capability.consumes shape: continue assigning Dict[str, str] to consumes field (consumers downstream depend on this shape).
5. Verify backwards compatibility: existing validate_input(), save_to_cache(), _reconstruct_from_cache() must accept unchanged Capability objects.
6. Run full test suite: verify all 30 test_capability_map.py tests pass. Flag any regression.

---

## Slice 3: Pre-Commit Drift Validator Hook

**Risk Tier:** high-risk  
**Depends On:** Slice 1, Slice 2 (must pass all regression tests)  
**Files:** plugin-orchestrator/orchestrator/interop_drift_validator.py, plugin-orchestrator/tests/test_interop_drift_validator.py  

### Test Intent
Detect when staged INTEROP.md changes are not reflected in corresponding code (schema_extractor.py, interop_parser.py); block commits if drift detected; allow SDD_GATE=off override; execute in <500ms (leaves 500ms budget for doc-consistency-auditor in same pre-commit gate).

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_interop_drift_validator -v
```
(Synthetic test: intentional INTEROP.md drift, hook should deny; SDD_GATE=off, hook should allow)

### Ordered Steps
1. Create `interop_drift_validator.py` as PreToolUse hook on Bash tool (detect `git commit` via regex in command).
2. On commit, extract staged files via `git diff --cached --name-only | grep INTEROP.md`.
3. For each staged INTEROP.md:
   - Extract "before" schema: `git show HEAD:path/to/INTEROP.md | schema_extractor.extract_from_file()`
   - Extract "after" schema: staged file contents | schema_extractor.extract_from_file()
   - Compare schemas (field-by-field): new fields, removed fields, type changes
4. If drift detected AND field is hardcoded in interop_parser.py:
   - Check if interop_parser.py was also staged; if not, flag as mismatch (block commit)
   - If interop_parser.py staged, compare before/after in that file too (via git diff HEAD)
5. Decision logic:
   - No INTEROP.md changes in staging area: pass (allow commit)
   - INTEROP.md changes + matching code changes: pass (allow commit)
   - INTEROP.md changes + no code changes: fail (deny commit, suggest code updates)
   - SDD_GATE=off environment var set: pass (allow commit, log override)
6. Error message: side-by-side schema diff (schema before → schema after), list affected fields, reference interop_parser.py lines needing update.
7. Write tests using hook_test_utils pattern (temp_git_repo, temp_home, run_hook fixtures): verify allow/deny decision for each scenario above.

---

## Slice 4: CLI Validation Tool

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** plugin-orchestrator/orchestrator/schema_extractor.py (--check flag, added to Slice 1)  

### Test Intent
Developers can run `python orchestrator/schema_extractor.py --check` locally to validate all schemas before committing (informational, not blocking); output indicates which INTEROP.md files have issues and why.

### Validation Target
```bash
python3 orchestrator/schema_extractor.py --check
# Expected: exit 0 (no errors) or exit 1 (errors found); summary printed to stdout
```

### Ordered Steps
1. Add argparse argument `--check` to schema_extractor.py main block.
2. On `--check`, call `extract_all_plugins()` and validate each schema:
   - Hardcoded fields in interop_parser.py (agent-tdd consumes, agent-cache-plugin consumes, etc.) exist in extracted schema.
   - No unexpected type mismatches (compare extracted type vs. hardcoded type in code).
   - Report: pass/fail per plugin, field-level details for mismatches.
3. Output format: human-readable summary (e.g., "agent-tdd: PASS (5 fields validated)" or "agent-tdd: FAIL (research_cache type mismatch: object vs. dict)").
4. Exit code: 0 if all pass, 1 if any mismatch (enables CI integration).
5. Test: manual CLI invocation on current codebase (expected: PASS); commit with intentional drift, re-run (expected: FAIL with field-level error).

---

## Slice 5: Error Messages & Reporting

**Risk Tier:** standard  
**Depends On:** Slice 3  
**Files:** plugin-orchestrator/orchestrator/interop_drift_validator.py (enhanced with formatting)  

### Test Intent
Drift validator (Slice 3) produces actionable error messages: side-by-side schema comparison, field-by-field diffs, suggested code changes with line numbers.

### Validation Target
```bash
# Trigger drift intentionally (update INTEROP.md, don't update interop_parser.py), commit
# Expected: hook blocks commit, prints side-by-side diff (before/after schemas)
```

### Ordered Steps
1. Enhance Slice 3's error message: format as side-by-side schema diff.
   - Column 1: "Before" (schema from git HEAD)
   - Column 2: "After" (schema from staged)
   - Highlight added/removed/modified fields (with types)
2. For each mismatched field:
   - Print affected interop_parser.py line numbers (grep hardcoded consumes dict for this plugin)
   - Suggest: "Update interop_parser.py lines 321-326 to add field: consumes['field_name'] = 'type'"
3. Write test: validate message format on known drift scenario (add one field to agent-tdd schema, omit from code); assert message contains "Before/After", field names, line number references.

---

## Slice 6: Integration Test (End-to-End)

**Risk Tier:** standard  
**Depends On:** Slice 1, Slice 2, Slice 3, Slice 4, Slice 5  
**Files:** plugin-orchestrator/tests/test_interop_drift_integration.py  

### Test Intent
End-to-end: parse real INTEROP.md files → extract schemas → validate against interop_parser.py hardcoded dicts → trigger drift validator on intentional changes → confirm hook response.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_interop_drift_integration -v
```

### Ordered Steps
1. Create `test_interop_drift_integration.py` with integration test suite.
2. Test scenario A: No drift (baseline)
   - Extract schema from current INTEROP.md files
   - Validate all schemas match hardcoded dicts in interop_parser.py
   - Assertion: no drift detected, all fields match
3. Test scenario B: Intentional INTEROP.md drift
   - Create temp INTEROP.md with new field added (e.g., agent-tdd consumes: add "phase_md": "string")
   - Extract schema, compare to current interop_parser.py
   - Trigger validator (simulate staged changes)
   - Assertion: drift detected, message suggests field update
4. Test scenario C: Code already in sync with INTEROP.md
   - Manually update interop_parser.py to add new field from scenario B
   - Trigger validator again
   - Assertion: no drift (code and docs in sync)
5. Test scenario D: Override with SDD_GATE=off
   - Trigger validator with drift + SDD_GATE=off
   - Assertion: override allowed, commit passes
6. All scenarios use realistic INTEROP.md copies (from agent-isdd, agent-tdd, etc.); validate latency <1s for full chain.

---

## Dependency Graph (Topological Order)

```
Slice 1 (schema_extractor)
  ↓
Slice 2 (interop_parser refactor) ┐
  ├──────────────────────────────┤
  ↓                              ↓
Slice 3 (drift validator)    Slice 4 (CLI tool)
  ↓
Slice 5 (error messages)
  ↓
Slice 6 (integration test)
```

**Acyclic:** ✓  
**All slices depend on ≤2 others:** ✓  
**No hidden dependencies:** ✓ (all file touchpoints explicit in "Files" field)

---

## Risk Summary

| Slice | Risk Tier | Why | Mitigation |
|-------|-----------|-----|-----------|
| 1 | standard | Regex parsing fragility | Format tolerance, graceful fallback, unit test edge cases |
| 2 | high-risk | Backwards compatibility, 30 existing tests must pass | Full regression test run, no API changes to CapabilityMap |
| 3 | high-risk | Pre-commit gate affects all commits; false positives block valid commits | Careful logic, synthetic test scenarios, SDD_GATE=off escape hatch |
| 4 | standard | CLI is informational only, not blocking | Manual testing sufficient |
| 5 | standard | Messaging only, no behavioral change | Test message format assertion |
| 6 | standard | Integration test (verification only) | Real file copies, latency validation |

---

## Implementation Notes

- **Performance Budget:** Each slice must not exceed <1s total (requirement: <1s validation latency)
  - Slice 1: <100ms (all 6 INTEROP files parsed)
  - Slice 2: regression tests only (no new perf cost)
  - Slice 3: <500ms (leaves 500ms for doc-auditor in same gate)
  - Slices 4–6: negligible overhead
  
- **Backwards Compatibility:** Slice 2 is critical — `Capability.consumes` shape must remain Dict[str, str]; all 3 call sites depend on it.

- **Scope Limitation:** PreToolUse hook (Slices 3–5) only intercepts Claude Code's Bash tool commits. Raw terminal/CI commits bypass it. Document this limitation; users can run CLI (Slice 4) locally for validation.

- **Test Infrastructure:** All slices use existing patterns:
  - Slice 1: standard unittest
  - Slice 2: regression via test_capability_map.py (no new tests needed)
  - Slice 3: hook_test_utils fixtures (temp_git_repo, temp_home, run_hook) from agent-isdd/tests/
  - Slices 4–6: standard unittest

