---
name: ralph-loops
description: Three autonomous validation loops for tasks.md — Slice Size, Dependency Correctness, Research-to-Implementation Traceability. Validates slice safety and proposes fixes.
---

# Ralph Loops

## Purpose

Autonomous validation of `tasks.md` slices. Three loops (max 3-5 iterations each) ensure slices are:

1. **Safe for TDD:** ≤ 3 files per slice, testable, ≤ 2 dependencies
2. **Dependency-correct:** Acyclic graph, no hidden dependencies
3. **Traceable to research:** Each slice's Ordered Steps grounded in design + research

Each loop can propose fixes (split slices, reorganize, add missing research). If fixes needed, re-slice and re-validate until all loops pass or max iterations hit.

## Input

**From task-slicer:**
- `tasks.md` — initial TDD-sized slices
- Dependency graph (Phase N → Depends On: [Phase X, Y])
- Test Intent + Validation Target per slice

**Additional:**
- `design.md` — to verify Ordered Steps against touchpoints
- `research_cache` — to verify Ordered Steps against findings

## Loop 1: Slice Size Validation

**Goal:** Ensure each slice is ≤ 3 files and testable in isolation

### Rules

1. **File count ≤ 3**
   - Count files in each slice's Ordered Steps
   - If > 3: TOO LARGE — must split

2. **Test surface is clear**
   - Can slice's Test Intent mock/stub external dependencies?
   - Can slice run in isolation (< 5 min, no external I/O)?
   - If no: TOO RISKY — requires design clarification or split

3. **Dependencies ≤ 2**
   - Count `Depends On: [Phase X, Y, ...]` entries
   - If > 2: TOO DEPENDENT — may indicate poor slicing

### Loop Logic

```
for each Phase in tasks.md:
  file_count = count_files(Phase.ordered_steps)
  dep_count = len(Phase.depends_on)
  test_surface = assess_test_surface(Phase.test_intent)
  
  if file_count > 3:
    action = SPLIT (break into smaller phases)
  elif test_surface == "risky":
    action = ESCALATE (ask design-author to clarify)
  elif dep_count > 2:
    action = REVIEW (might be OK, but check for bundling)
  else:
    verdict = PASS
  
  if action != PASS:
    propose_fix(Phase, action)
    mark_for_reslice()
```

### Exit Condition

All slices pass (file_count ≤ 3, testable, dep_count ≤ 2), OR max iterations reached.

### Example: Slice Too Large

**Input:**
```markdown
## Phase 3: Form Integration

### Ordered Steps
1. Update RegisterForm component
2. Update UserService with validation call
3. Update User model with property
4. Add email field to database schema
5. Migrate existing users
```

**Problem:**
- File count: 5 files (Form, Service, Model, Schema, Migration)
- Too large for TDD isolation
- Database migration adds risk

**Ralph Loop Action:**
```
✗ SLICE TOO LARGE (5 files)
  Recommendation: Split into two phases
  - Phase 3a: Form Integration (RegisterForm, UserService)
  - Phase 3b: Schema Migration (schema, migration, User model adjustment)
  
  Rationale: Database migrations have separate testing strategy (not unit-testable in same way)
```

**Reslice:**
```markdown
## Phase 3: Form Integration

Ordered Steps: RegisterForm, UserService calls (2 files)
Test Intent: Mock UserService responses, test form submission logic
Depends On: Phase 1, Phase 2

---

## Phase 4: Schema Migration

Ordered Steps: Database schema update, user data migration
Test Intent: Migration script on test database, verify no data loss
Depends On: Phase 3
```

## Loop 2: Dependency Correctness

**Goal:** Ensure dependencies form an acyclic graph (DAG), no hidden dependencies

### Rules

1. **Acyclic:** Topological sort succeeds
   - Build directed graph: Phase N → [Phases N depends on]
   - Run topological sort
   - If cycle detected: CYCLE — must break

2. **No hidden dependencies:**
   - Phase 3 depends on Phase 1 (declared)
   - Phase 3 Ordered Steps mention "User model validates email"
   - Must Phase 1 (User validation) run before Phase 3?
   - If yes, hidden dependency — make explicit

3. **Minimal dependencies:**
   - Phase N depends on Phase M
   - Is there truly a data/code dependency? Not just "nice to have"?
   - If just convenience, consider removing

### Loop Logic

```
graph = build_dependency_graph(tasks.md)

# Check 1: Acyclic
try:
  topological_sort(graph)
  verdict_acyclic = PASS
except CycleError as e:
  verdict_acyclic = FAIL
  cycles = e.cycles
  action = REORGANIZE (break cycles)

# Check 2: Hidden dependencies
for phase in tasks.md:
  for step in phase.ordered_steps:
    mentioned_concepts = extract_nouns(step)
    required_phases = infer_dependencies(mentioned_concepts, research_cache)
    declared_phases = phase.depends_on
    
    hidden = required_phases - declared_phases
    if hidden:
      action = ADD_DEPENDENCY (add to Depends On)

# Check 3: Minimal dependencies
for phase in tasks.md:
  for dep in phase.depends_on:
    if not is_data_or_code_dependency(phase, dep):
      action = REVIEW (can dependency be removed?)

if verdict_acyclic == FAIL or hidden or over_dependencies:
  propose_reorganization()
  mark_for_reslice()
```

### Exit Condition

Graph is acyclic, all dependencies explicit, no over-dependencies, OR max iterations reached.

### Example: Hidden Dependency

**Input:**
```markdown
## Phase 3: Form Integration

Depends On: [Phase 2]

Ordered Steps:
1. Call UserService.validateEmail()  ← mentions validation
2. Display error "Email already in use"
```

**Problem:**
- Step mentions UserService.validateEmail()
- But Phase 1 (User model validation) is not in Depends On
- Hidden dependency on Phase 1

**Ralph Loop Action:**
```
✗ HIDDEN DEPENDENCY DETECTED
  Phase 3 Ordered Steps reference User model validation (Phase 1)
  Depends On currently: [Phase 2]
  Depends On should be: [Phase 1, Phase 2]
  
  Action: ADD Phase 1 to dependencies
```

**Fix:**
```markdown
## Phase 3: Form Integration

Depends On: [Phase 1, Phase 2]  ← Phase 1 added
```

## Loop 3: Research-to-Implementation Traceability

**Goal:** Ensure each slice's Ordered Steps are grounded in design + research

### Rules

1. **File exists in cache:**
   - Phase 1 Ordered Step: "Add validateEmail() to User model"
   - File: src/models/user.ts
   - Is src/models/user.ts in research_cache.file_summaries?
   - If no: FILE NOT IN CACHE — needs research

2. **Interface documented:**
   - Phase 2 Ordered Step: "Call UserService.isEmailUnique()"
   - Research mentions "UserService.isEmailUnique(email: string): Promise<boolean>"?
   - If no: INTERFACE NOT DOCUMENTED — needs research

3. **Constraint respected:**
   - Phase 1 Ordered Step: "Add email property to immutable User model"
   - Research mentions: "User model is immutable"?
   - If no constraint found, OR constraint contradicted: RISK — flag or research

### Loop Logic

```
for phase in tasks.md:
  for step in phase.ordered_steps:
    file = extract_file(step)  # "src/models/user.ts"
    interface = extract_interface(step)  # "UserService.isEmailUnique()"
    
    # Check 1: File in cache
    if file not in research_cache.file_summaries:
      action = RESEARCH_GAP
      missing.append({file, "not in cache", step})
    
    # Check 2: Interface documented
    if interface:
      if interface not in research_findings:
        action = RESEARCH_GAP
        missing.append({file, f"interface {interface} not documented", step})
    
    # Check 3: Constraint respected
    constraints = research_cache.constraints_for_file(file)
    for constraint in constraints:
      if step contradicts constraint:
        action = FLAG_RISK
        risks.append({file, constraint, step})

if missing:
  action = TARGETED_RESEARCH (fill gaps, update cache)
  mark_for_reslice()
elif risks:
  action = FLAG (add to slice's Risk Tier or Open Blockers)
```

### Exit Condition

All steps are traceable to research, OR risks are flagged and acknowledged, OR max iterations reached.

### Example: Research Gap

**Input:**
```markdown
## Phase 3: Form Integration

Ordered Steps:
1. Import EmailValidator from src/api/email-validator.ts  ← mentions file
2. Call EmailValidator.validate(email)
```

**Problem:**
- Step references src/api/email-validator.ts
- File NOT in research_cache.file_summaries (was never researched)
- Interface EmailValidator.validate() not documented

**Ralph Loop Action:**
```
✗ RESEARCH GAP DETECTED
  Phase 3 Step 1 references src/api/email-validator.ts
  File not in research cache; interface not documented
  
  Missing research:
  - Does src/api/email-validator.ts exist?
  - What is the EmailValidator interface?
  - Performance constraints? Dependencies?
  
  Action: Run targeted deep-read on this file, update cache
```

**Resolution:**
- User (or research-consolidator) deep-reads src/api/email-validator.ts
- Adds file_summary to research_cache
- Re-run ralph-loops, Loop 3 re-validates

## Loop Iteration & Exit

**Iteration limits:** Max 3-5 iterations per loop (prevent infinite loops)

**Exit conditions:**
1. ✓ All loops pass (all slices valid)
2. ✗ Max iterations hit (escalate: "Ralph Loops could not converge; manual review needed")
3. ⚠ Gaps require targeted research (pause for research-consolidator, then re-validate)

**Output per iteration:**
```json
{
  "loop_name": "Slice Size Validation",
  "iteration": 1,
  "status": "VIOLATIONS_FOUND",
  "violations": [
    {
      "phase": "Phase 3",
      "issue": "TOO_LARGE (5 files)",
      "recommendation": "Split into Phase 3 (2 files) + Phase 4 (3 files)"
    }
  ],
  "action": "RESLICE",
  "next": "Re-run task-slicer with split recommendation"
}
```

## Final Ralph Loops Report

After all loops pass (or max iterations):

```
**Ralph Loops Validation Report**

Loop 1 - Slice Size Validation:
  ✓ All slices ≤ 3 files
  ✓ All slices testable (test surface clear)
  ✓ All dependencies ≤ 2
  Iterations: 2/5 (converged)

Loop 2 - Dependency Correctness:
  ✓ Graph is acyclic (topological sort succeeded)
  ✓ No hidden dependencies
  ✓ All dependencies minimal and justified
  Iterations: 1/5 (converged)

Loop 3 - Research-to-Implementation Traceability:
  ✓ All files in research cache
  ✓ All interfaces documented
  ⚠ 1 risk flagged: Phase 4 (database migration) lacks rollback strategy
    - Resolution: Add rollback steps to test intent
  Iterations: 2/5 (converged)

**Verdict: READY FOR IMPLEMENTATION**
Slicing confidence: HIGH
All checks passed. Ready to proceed to Risk Tier assignment.
```

## Guardrails

- **Do not** accept slices > 3 files (hard architectural boundary)
- **Do not** allow cycles (build new slices if cycle detected)
- **Do not** skip research gaps (must be researched or escalated)
- **Do not** ignore flagged risks (must be acknowledged in Risk Tier)
- **Do not** exceed iteration limits without escalation

## Integration with Other Phases

- **Input from:** task-slicer (produces initial tasks.md)
- **Output to:** risk-assign (assigns Risk Tiers), readiness-check (final gate)
- **Can escalate to:** research-consolidator (targeted re-research), design-author (design clarification)

## Token Efficiency

- Deterministic loops (no redundant reads)
- Reuse research_cache entirely (no extra research unless gaps)
- Iteration limits prevent runaway loops
- Structured output for downstream agents
