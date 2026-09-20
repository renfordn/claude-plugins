# Tasks: Prevent Interop Drift Between Plugins (Phase 1A + Implementation)

## Slice 1: INTEROP.md Format Normalization (Phase 1A, Blocking)

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** agent-isdd/INTEROP.md, agent-tdd/INTEROP.md, code-reviewer/INTEROP.md, plugin-orchestrator/INTEROP.md, agent-nelly/INTEROP.md, agent-cache-plugin/STRUCTURE.md  

### Test Intent
Normalize all 6 INTEROP.md files from mixed formats (prose bullets, tables, mixed prose) into a consistent markdown table format (| Field | Type | Required |) for machine parsing; validate via doc-consistency-auditor before commit (no schema changes, only format refactoring).

### Validation Target
```bash
# After normalizing all 6 INTEROP.md files:
# Invoke doc-consistency-auditor (via agent-isdd skill or pre-commit gate)
# Expected: passes with no schema drift findings (format change only, no content change)
```

### Ordered Steps
1. Define standard format for INTEROP.md "consumes" and "produces" sections:
   - Markdown fenced table: `| Field | Type | Required |` (matching agent-ux's existing style)
   - Example row: `| requirements_md | string | yes |`
   - Add header comment documenting format expectation (helps future maintainers)
   
2. Normalize **agent-isdd/INTEROP.md**: Convert prose bullet-point format ("- requirements_md: string description") to markdown table format; preserve all field names, types, and requirement indicators.

3. Normalize **agent-tdd/INTEROP.md**: Convert mixed prose to table format; preserve sub-schema details (research_cache internal fields documented as nested structure within table cell or as separate subsection).

4. Normalize **code-reviewer/INTEROP.md**, **plugin-orchestrator/INTEROP.md**, **agent-nelly/INTEROP.md**: Standardize to same table format.

5. Normalize **agent-cache-plugin/STRUCTURE.md**: Apply same table format (non-standard filename but same contract).

6. **Critical validation step:** After all 6 files normalized, run doc-consistency-auditor to ensure:
   - No accidental schema changes during format refactoring
   - All documented fields, types, and requirement indicators match before → after
   - No new cross-plugin drift introduced
   - Gate passes before commit (atomic batch commit per Phase 1A design)

7. Commit atomically with message: "docs(interop): normalize all INTEROP.md files to markdown table format"

---

## Slice 2: Schema Extraction Module (Mechanical Parser)

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** plugin-orchestrator/orchestrator/schema_extractor.py  

### Test Intent
Parse normalized INTEROP.md files (all 6 plugins) into a queryable schema registry; extract field names and types from markdown tables; handle edge cases (missing types, unknown type names); performance: all 6 files parsed in <100ms.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_schema_extractor -v
```
(New test file testing extraction from real + synthetic normalized INTEROP.md examples)

### Ordered Steps
1. Create `schema_extractor.py` with:
   - `Field` dataclass: name, type_name, required (bool), description
   - `Schema` dataclass: plugin_name, capability_name, fields (dict of Field)
   - `SchemaRegistry` class: in-memory registry of all extracted schemas
   
2. Implement `extract_from_file(path: str) -> Schema` parsing logic:
   - Parse markdown table format (rows with | delimiters)
   - Extract field name (column 1), type_name (column 2), required (column 3: "yes"/"no")
   - Handle sub-schema structures (nested objects, arrays) in agent-tdd/INTEROP.md
   - Graceful fallback on parse failure (log warning, return empty schema with empty fields dict)
   
3. Implement `extract_all_plugins(base_dir: str) -> Dict[str, Dict[str, Schema]]` registry builder:
   - Scan known plugin directories: agent-isdd, agent-tdd, code-reviewer, agent-nelly, agent-cache-plugin, plugin-orchestrator
   - For each plugin's INTEROP.md (or STRUCTURE.md), parse all "consumes" and "produces" sections
   - Return nested dict: {plugin_name: {capability_name: Schema}}
   
4. Add caching layer: compute sha256 fingerprint of each INTEROP.md before/after, skip re-parse if unchanged (performance: all 6 files <100ms).

5. Write unit tests:
   - Parse real normalized INTEROP.md files (from Slice 1)
   - Extract correct field names, types, requirement indicators
   - Handle edge cases: missing colons, malformed tables, nested objects
   - Performance benchmark: all 6 files parsed in <100ms ✓
   
---

## Slice 3: Refactor interop_parser.py (Backwards Compatible)

**Risk Tier:** high-risk  
**Depends On:** Slice 2 (schema extraction must be complete)  
**Files:** plugin-orchestrator/orchestrator/interop_parser.py, plugin-orchestrator/tests/test_capability_map.py  

### Test Intent
Replace hardcoded plugin schemas in `_extract_capabilities()` (lines 313–327, 336–340, etc. per research cache.md) with runtime lookups from SchemaRegistry (Slice 2); all 30 existing capability tests must pass unchanged; `Capability.consumes` shape (Dict[str, str]) unchanged for backwards compatibility.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_capability_map -v
```
(30 existing tests, all must pass; no regressions)

### Ordered Steps
1. Import SchemaRegistry from schema_extractor.py; initialize in CapabilityMap.__init__() with extracted schemas.

2. Refactor `_extract_capabilities()` method:
   - Identify current hardcoded if/elif blocks for each plugin (agent-tdd, agent-nelly, agent-cache-plugin, etc.)
   - Replace each block with registry lookup: `schema = registry.get_schema(plugin_name, capability_name)`
   - Assign consumes field from schema (Dict[str, str]: field_name → type_name)
   
3. For each plugin lookup:
   - If schema found in registry: use it (consumes = {field_name: type_name, ...})
   - If schema not found: fall back to empty dict {} (graceful degradation)
   - Preserve detection logic (substring checks for "Design Spec", etc. remain unchanged)
   
4. **Critical: preserve Capability.consumes shape**
   - Continue assigning Dict[str, str] to consumes field
   - Consumers downstream (validate_input, save_to_cache, _reconstruct_from_cache) depend on this shape
   - No API changes to CapabilityMap methods
   
5. Run full test suite: execute all 30 test_capability_map.py tests; verify no regressions.

6. Flag any regression immediately; this is a high-risk refactor (validation logic impacts all handoffs).

---

## Slice 4: Pre-Commit Drift Validator Hook

**Risk Tier:** high-risk  
**Depends On:** Slice 3 (refactored interop_parser.py must be in place)  
**Files:** plugin-orchestrator/orchestrator/interop_drift_validator.py, plugin-orchestrator/tests/test_interop_drift_validator.py  

### Test Intent
Detect when staged INTEROP.md changes are not reflected in corresponding validation code (interop_parser.py); block commits if drift detected; allow SDD_GATE=off override; execute in <500ms (leaves 500ms budget for doc-consistency-auditor in same pre-commit gate).

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_interop_drift_validator -v
```
(Test scenarios: no drift, intentional drift, SDD_GATE=off override, code already in sync)

### Ordered Steps
1. Create `interop_drift_validator.py` as PreToolUse hook on Bash tool (detect `git commit` via regex in command).

2. On commit attempt, detect if any INTEROP.md files staged:
   - Run: `git diff --cached --name-only | grep -E "INTEROP\.md|STRUCTURE\.md"`
   - If no INTEROP.md changes: pass (allow commit)
   
3. For each staged INTEROP.md file:
   - Extract "before" schema: `git show HEAD:path/to/INTEROP.md | schema_extractor.extract_from_file()`
   - Extract "after" schema: staged file contents → `schema_extractor.extract_from_file()`
   - Compare schemas field-by-field (name, type, required flag)
   - Track detected drift (new fields, removed fields, type mismatches)
   
4. Drift decision logic:
   - If no drift detected: pass (allow commit)
   - If drift detected AND corresponding validation code (interop_parser.py) **not** staged:
     - Check if schema drift field is hardcoded in interop_parser.py (grep for field_name)
     - If hardcoded: fail (deny commit, suggest code update)
     - If not hardcoded: pass (informational; drift is safe)
   - If drift detected AND validation code **is** staged:
     - Compare before/after in interop_parser.py (via git diff HEAD)
     - If code schema updated to match INTEROP.md: pass (allow commit)
     - If code schema not updated: fail (deny commit)
   - If SDD_GATE=off environment var set: pass (allow commit, log override)
   
5. Error message when denying commit:
   - Side-by-side schema diff (before → after)
   - List affected fields (added, removed, type changes)
   - Reference interop_parser.py line numbers where hardcoded schema is located
   - Suggest: "Update interop_parser.py lines 321-326 to add field: consumes['field_name'] = 'type'"
   
6. Write tests using hook_test_utils pattern (from agent-isdd/tests/):
   - temp_git_repo fixture: setup test repo with real INTEROP.md files
   - Scenario A: No INTEROP.md changes → pass ✓
   - Scenario B: INTEROP.md drift, no code changes → fail ✓
   - Scenario C: INTEROP.md drift + matching code changes → pass ✓
   - Scenario D: SDD_GATE=off override → pass ✓
   
---

## Slice 5: CLI Validation Tool

**Risk Tier:** standard  
**Depends On:** Slice 2 (schema extraction must work)  
**Files:** plugin-orchestrator/orchestrator/schema_extractor.py (add --check flag)  

### Test Intent
Developers can run `python orchestrator/schema_extractor.py --check` locally to validate all schemas before committing (informational, not blocking); output indicates which INTEROP.md files have issues and suggests fixes.

### Validation Target
```bash
python3 orchestrator/schema_extractor.py --check
# Expected: exit 0 (no drift) or exit 1 (drift found); summary printed
```

### Ordered Steps
1. Add argparse argument `--check` to schema_extractor.py main block.

2. On `--check`, execute validation logic:
   - Call `extract_all_plugins()` to parse all 6 INTEROP.md files
   - For each plugin+capability extracted, validate against hardcoded schema in interop_parser.py:
     - Check if all documented fields exist in validation code
     - Check for type mismatches (extracted type vs. hardcoded type)
     - Check for dead code (validation schema not documented in INTEROP.md)
   - Collect results (pass/fail per plugin, field-level details)
   
3. Output format: human-readable summary
   - Example PASS: "agent-tdd: PASS (5 fields validated)"
   - Example FAIL: "agent-tdd: FAIL — research_cache type mismatch (INTEROP.md: object, code: dict)"
   - Print file paths and line numbers for mismatches
   
4. Exit code: 0 if all pass, 1 if any mismatch (enables CI integration).

5. Test: 
   - Manual CLI invocation on current codebase (expected: PASS)
   - Intentionally update an INTEROP.md field without updating interop_parser.py, re-run (expected: FAIL with field-level error)

---

## Slice 6: Error Messages & Reporting

**Risk Tier:** standard  
**Depends On:** Slice 4 (drift validator hook must exist)  
**Files:** plugin-orchestrator/orchestrator/interop_drift_validator.py (enhance error formatting)  

### Test Intent
Drift validator (Slice 4) produces actionable error messages: side-by-side schema comparison, field-by-field diffs, suggested code changes with line numbers.

### Validation Target
```bash
# Trigger drift intentionally: update INTEROP.md, don't update interop_parser.py, attempt commit
# Expected: hook blocks commit, prints detailed side-by-side diff
```

### Ordered Steps
1. Enhance Slice 4's error message formatting:
   - Generate side-by-side schema diff (columns: "Before" (HEAD), "After" (staged))
   - Example format:
     ```
     Schema Drift Detected: agent-tdd/INTEROP.md
     
     Before (HEAD)              | After (staged)
     ---                        | ---
     requirements_md: string    | requirements_md: string
     design_md: string          | design_md: string
     research_cache: object     | research_cache: object ← sub-schema expanded
     recap_md: string           | recap_md: string
                                | phase_md: string (NEW)
     ```
   
2. For each mismatched field, generate actionable fix suggestions:
   - Identify affected interop_parser.py line numbers (grep for plugin's consumes dict, find line range)
   - Print: "Update interop_parser.py lines 321-326 to add field: consumes['phase_md'] = 'string'"
   - Reference INTEROP.md section (file path, line number where new field is documented)
   
3. Test error message format:
   - Trigger known drift scenario (add one field to agent-tdd schema, omit from interop_parser.py)
   - Assert message contains side-by-side diff, field names, line number references
   - Verify message is readable and actionable
   
---

## Slice 7: Integration Test (End-to-End)

**Risk Tier:** standard  
**Depends On:** Slice 1, Slice 2, Slice 3, Slice 4, Slice 5, Slice 6  
**Files:** plugin-orchestrator/tests/test_interop_drift_integration.py  

### Test Intent
End-to-end: normalized INTEROP.md files → extract schemas (Slice 2) → validate against interop_parser.py (Slice 3) → trigger drift validator on intentional changes (Slice 4) → verify error messages (Slice 6) → confirm hook response and latency <1s.

### Validation Target
```bash
python3 -m unittest plugin_orchestrator.tests.test_interop_drift_integration -v
```

### Ordered Steps
1. Create `test_interop_drift_integration.py` with integration test suite (uses real INTEROP.md files from Slice 1, normalized schema_extractor from Slice 2).

2. Test Scenario A: No drift (baseline)
   - Extract schemas from normalized INTEROP.md files
   - Validate all schemas match hardcoded dicts in interop_parser.py (Slice 3)
   - Assertion: no drift detected, all fields match, latency <100ms
   
3. Test Scenario B: Intentional INTEROP.md drift
   - Create temp INTEROP.md copy with new field added (e.g., agent-tdd consumes: add "phase_md": "string")
   - Extract schema, compare to current interop_parser.py
   - Trigger drift validator (simulate staged changes via git diff)
   - Assertion: drift detected, error message suggests field update, latency <500ms
   
4. Test Scenario C: Code updated to match INTEROP.md
   - Manually update interop_parser.py to add new field from scenario B
   - Trigger validator again
   - Assertion: no drift (code and docs in sync)
   
5. Test Scenario D: Override with SDD_GATE=off
   - Trigger validator with drift + SDD_GATE=off
   - Assertion: override allowed, commit passes, latency unaffected
   
6. Test Scenario E: End-to-end latency
   - Parse all 6 real INTEROP.md files + validate against interop_parser.py + trigger drift validator
   - Assertion: full chain <1s (per requirement)
   
7. Test Scenario F: Regression on all 30 existing capability tests
   - Verify all test_capability_map.py tests still pass (Slice 3 regression surface)
   
---

## Dependency Graph (Topological Order)

```
Slice 1 (INTEROP.md normalization)
  ↓
Slice 2 (schema_extractor.py)
  ├────────────────────────────┐
  ↓                            ↓
Slice 3 (interop_parser refactor)  Slice 5 (CLI tool)
  ↓
Slice 4 (drift validator hook)
  ↓
Slice 6 (error messages)
  ↓
Slice 7 (integration test)
```

**Acyclic:** ✓  
**All slices depend on ≤2 others:** ✓  
**No hidden dependencies:** ✓ (all file touchpoints explicit)

---

## Risk Summary

| Slice | Risk Tier | Why | Mitigation |
|-------|-----------|-----|-----------|
| 1 | standard | Documentation refactoring only, no code logic | Format validation via doc-consistency-auditor before commit; atomic batch reduces ceremony |
| 2 | standard | Regex parsing fragility, format-specific | Format tolerance (handle normalized tables from Slice 1), graceful fallback, edge-case unit tests |
| 3 | high-risk | Backwards compatibility, 30 regression tests, all handoffs depend on validation logic | Full regression test run, no API changes to CapabilityMap, Capability.consumes shape preserved |
| 4 | high-risk | Pre-commit gate affects all commits; false positives block valid commits, false negatives miss drift | Careful decision logic, synthetic test scenarios (A–D), SDD_GATE=off escape hatch, <500ms latency |
| 5 | standard | CLI is informational only, not blocking | Manual testing sufficient, no logic changes |
| 6 | standard | Error messaging only, no behavioral change | Test message format assertions |
| 7 | standard | Integration test (verification only) | Real INTEROP.md copies, latency profiling included |

---

## Phase Mapping

- **Phase 1A (Design)** → Slice 1 (INTEROP.md normalization, blocking)
- **Phase 1B (Design)** → Slice 2 (schema extraction)
- **Phase 2 (Design)** → Slices 3, 4 (refactor + drift validator hook)
- **Phase 3 (Design)** → Slices 5, 6 (CLI + error messages)
- **Validation** → Slice 7 (integration test, all slices combined)

---

## Implementation Notes

- **Performance Budget:** Each slice must not exceed <1s total validation latency (requirement)
  - Slice 1: doc-auditor pass (LLM-driven, may be slow, but format-only audit should be fast)
  - Slice 2: <100ms (all 6 INTEROP files parsed, caching layer included)
  - Slice 3: regression tests only (no new perf cost beyond Slice 2)
  - Slice 4: <500ms (leaves 500ms for doc-auditor in same gate)
  - Slices 5–7: negligible overhead
  - **Total pre-commit latency:** <1s ✓
  
- **Backwards Compatibility:** Slice 3 is critical — `Capability.consumes` shape must remain Dict[str, str]; all 3 call sites (validate_input, save_to_cache, _reconstruct_from_cache) depend on it.

- **Scope Limitation:** PreToolUse hook (Slices 4–6) only intercepts Claude Code's Bash tool commits. Raw terminal/CI commits bypass it. Document this limitation; users can run CLI (Slice 5) locally for validation before pushing.

- **Test Infrastructure:** All slices use established patterns:
  - Slice 1: doc-auditor validation (existing skill)
  - Slice 2: standard unittest with real + synthetic INTEROP.md copies
  - Slice 3: regression via test_capability_map.py (no new tests needed for refactor, only verify existing tests pass)
  - Slice 4: hook_test_utils fixtures (temp_git_repo, temp_home, run_hook) from agent-isdd/tests/
  - Slices 5–7: standard unittest
  
- **Research Grounding:** All steps reference research cache.md and design.md:
  - Slice 1: Phase 1A defined in design.md (normalize to markdown table format)
  - Slice 2: schema_extractor.py module defined in design.md, parser logic grounded in research.md (format variations listed)
  - Slice 3: interop_parser.py refactor targets (lines 289–380) per research.md, hardcoded schemas replaced
  - Slice 4: PreToolUse hook pattern from research.md (commit_audit_gate.py), drift detection logic per design.md
  - Slices 5–7: per design.md (CLI, error messages, integration testing)

