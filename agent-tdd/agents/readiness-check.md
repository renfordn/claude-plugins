---
name: readiness-check
description: Final gate before Red-Green-Refactor. Validates tasks.md passes readiness checklist and returns verdict (ready vs. paused).
---

# Readiness Check

## Purpose

Final validation gate before proceeding to Red-Green-Refactor. Checks that `tasks.md` is:

1. Complete (all required fields present)
2. Safe (all slices valid, no blockers)
3. Ready (checklist passes)
4. Actionable (user can implement immediately)

Returns a **verdict** (ready | paused) and a **readiness report** for handoff to Red-Green-Refactor.

## Input

- `tasks.md` — slices from task-slicer, validated by ralph-loops, assigned Risk Tiers
- `design.md` — reference for scope
- `requirements.md` — reference for coverage
- `ralph_loops_report` — validation results

## Readiness Checklist

### Item 1: At Least One Phase Exists

**Check:**
```python
phase_count = len([p for p in tasks.md if p.startswith("## Phase")])
if phase_count >= 1:
  pass
else:
  fail("No phases defined in tasks.md")
```

**Requirement:** tasks.md must have ≥ 1 phase (typically 2-5 phases per feature)

---

### Item 2: Each Phase Has Required Fields

**Check:**
```python
for phase in tasks.md:
  required = [
    "Objective",
    "Risk Tier",
    "Prerequisites",
    "Depends On",
    "Ordered Steps",
    "Test Intent",
    "Validation Target"
  ]
  for field in required:
    if field not in phase:
      fail(f"Phase {phase.name} missing {field}")
  pass
```

**Requirement:** Every phase must have:
- ✓ Objective (one-line behavior change)
- ✓ Risk Tier (high-risk | standard)
- ✓ Prerequisites (prior decisions/phases needed)
- ✓ Depends On (list of prior phases this depends on)
- ✓ Ordered Steps (1-2-3 breakdown)
- ✓ Test Intent (what fails in Red, what passes in Green)
- ✓ Validation Target (how to verify)

---

### Item 3: Slices Are Safe for TDD

**Check:**
```python
for phase in tasks.md:
  # From ralph-loops validation report
  if phase.file_count > 3:
    fail(f"Phase {phase.name} has {phase.file_count} files (max 3)")
  
  if phase.test_feasibility == "not_testable":
    fail(f"Phase {phase.name} has weak test surface")
  
  if phase.dependency_count > 2:
    warn(f"Phase {phase.name} has {phase.dependency_count} dependencies")
  
  pass
```

**Requirement:** All slices must pass ralph-loops validation
- ✓ ≤ 3 files per slice
- ✓ Testable (clear test surface)
- ✓ ≤ 2 dependencies (soft limit, warn if > 2)

---

### Item 4: Dependencies Are Acyclic & Complete

**Check:**
```python
graph = build_dependency_graph(tasks.md)
try:
  topological_sort(graph)
  pass
except CycleError:
  fail("Cyclic dependency detected (should have been caught by ralph-loops)")

# Check all dependencies are declared
for phase in tasks.md:
  missing_deps = infer_missing_dependencies(phase, tasks.md)
  if missing_deps:
    warn(f"Phase {phase.name} may have undeclared dependencies: {missing_deps}")
  pass
```

**Requirement:** Dependency graph must be acyclic (DAG)
- ✓ Topological sort succeeds
- ✓ No hidden dependencies (should have been caught by ralph-loops Loop 2)

---

### Item 5: Steps Are Grounded in Research

**Check:**
```python
for phase in tasks.md:
  for step in phase.ordered_steps:
    if step not in research_cache:
      if can_derive_from_design(step, design.md):
        pass  # OK if derived from design
      else:
        warn(f"Phase {phase.name} Step: {step} not in research or design")
  pass
```

**Requirement:** Each Ordered Step must be grounded
- ✓ File mentioned exists in research_cache.file_summaries
- ✓ Interface mentioned is documented in research
- ✓ Constraint mentioned is acknowledged in research (or design)
- ✓ OR step is clearly derived from design.md intent

---

### Item 6: Test Intent Is Clear & Actionable

**Check:**
```python
for phase in tasks.md:
  test_intent = phase.test_intent
  
  # Verify test intent has structure
  if not ("Add or update:" in test_intent or "Expected failing behavior:" in test_intent):
    fail(f"Phase {phase.name} Test Intent lacks structure")
  
  # Verify it's specific (not vague)
  if "test" in test_intent.lower() and len(test_intent) < 20:
    warn(f"Phase {phase.name} Test Intent may be too vague")
  
  pass
```

**Requirement:** Test Intent must be specific and implementable
- ✓ "Add or update: [specific test targets]" section
- ✓ "Expected failing behavior: [specific failure condition]" section
- ✓ Not vague (e.g., "write tests" is vague; "write tests for email validation" is good)

---

### Item 7: Validation Target Is Verifiable

**Check:**
```python
for phase in tasks.md:
  validation = phase.validation_target
  
  # Verify command exists and is specific
  if "Command:" not in validation:
    fail(f"Phase {phase.name} Validation Target missing Command")
  
  if validation.command == "run tests":  # Too vague
    warn(f"Phase {phase.name} Validation command is too vague")
  
  # Verify evidence is clear
  if "Evidence:" not in validation:
    fail(f"Phase {phase.name} Validation Target missing Evidence")
  
  pass
```

**Requirement:** Validation Target must be verifiable by a human or script
- ✓ Command: `npm test -- UserService.test.ts` (specific)
- ✓ Evidence: "All tests pass" or "Coverage > 90%" (measurable)
- ✓ Not vague: "Looks good" is not evidence

---

### Item 8: No Unresolved Blockers

**Check:**
```python
blockers = []
for phase in tasks.md:
  if "Blockers Or Escalation:" in phase:
    for blocker in phase.blockers:
      if not blocker.resolved:  # [ ] means unresolved
        blockers.append({phase: phase.name, blocker: blocker})

if blockers:
  fail(f"Unresolved blockers: {blockers}")
else:
  pass
```

**Requirement:** All blockers must be resolved (checked ✓) or escalated
- ✓ Database schema has unique constraint on User.email — CONFIRMED
- ✓ RFC 5322 library available — CONFIRMED
- ✓ Form state management compatible — CONFIRMED
- ✗ [Open] High-risk slice cannot be split further — ESCALATE (not OK to proceed)

---

### Item 9: Risk Tiers Are Assigned

**Check:**
```python
for phase in tasks.md:
  if phase.risk_tier not in ["high-risk", "standard"]:
    fail(f"Phase {phase.name} missing or invalid Risk Tier")
  pass
```

**Requirement:** Every phase must have Risk Tier assigned
- ✓ standard (default, no special handling)
- ✓ high-risk (requires test-author split)

---

### Item 10: Ready State Documented

**Check:**
```python
if "State: Ready For Implementation" in tasks.md:
  pass
else:
  fail("tasks.md does not mark state as Ready For Implementation")
```

**Requirement:** tasks.md must explicitly state:
```markdown
## Task Readiness Checklist

- [x] At least one concrete phase exists
- [x] Each phase has explicit objective, Risk Tier, steps, test intent, validation target
- [x] Slices are safe for TDD (≤ 3 files, acyclic dependencies)
- [x] No unresolved blocker requires confirmation before implementation
- [x] State can be marked `Ready For Implementation`
```

---

## Verdict Decision

**If all 10 items PASS:**

```json
{
  "verdict": "ready",
  "state": "Ready For Implementation",
  "confidence": "high",
  "message": "All checklist items passed. Proceed to Red-Green-Refactor.",
  "handoff": {
    "tasks_file": "tasks/tasks.md",
    "high_risk_slices": ["Phase 4"],
    "total_slices": 4,
    "estimated_effort": "4-6 hours (Phase 1: 30min, Phase 2: 30min, Phase 3: 1hr, Phase 4: 2-3hr)"
  }
}
```

**If any item FAILS or has UNRESOLVED BLOCKERS:**

Emit marker before verdict:

```
<!--AGENT-TDD-PLAN-FLAG:reason="Readiness check failed: <specific reason from blockers array>"-->
```

Then return verdict JSON:

```json
{
  "verdict": "paused",
  "state": "Awaiting Clarification",
  "confidence": "low",
  "blockers": [
    {
      "item": "Item 4: Dependencies",
      "issue": "Cyclic dependency detected between Phase 2 and Phase 3",
      "resolution": "task-slicer must reorganize slices"
    },
    {
      "item": "Item 8: Blockers",
      "issue": "Phase 4 has unresolved blocker: high-risk slice cannot be split",
      "resolution": "user must confirm acceptable risk or redesign slice"
    }
  ],
  "next_action": "Fix blockers (reslice or resolve blockers) and re-run readiness-check"
}
```

**Marker format:** When verdict = `paused`, emit the Plan Validity Flag marker to signal to the caller's SubagentStop hook that task planning failed and rollback/rewind may be needed. The reason should be the primary blocker from the blockers array, concise and actionable.

---

## Escalation Paths

If readiness-check fails, escalate back to appropriate agent:

| Blocker | Root Cause | Escalation |
|---------|-----------|---|
| Cyclic dependencies | ralph-loops missed cycle | **Re-run ralph-loops Loop 2** |
| Missing research | ralph-loops missed gap | **Re-run research-consolidator** |
| Weak test surface | Poor slicing | **Re-run task-slicer with split recommendations** |
| Unresolved blocker | User decision needed | **Pause workflow, user confirms, proceed** |
| Design contradicts tasks | Design unclear | **Escalate to design-author, update design** |

---

## Readiness Report (for handoff to Red-Green-Refactor)

Generate a concise report for agent-TDD:

```markdown
# Readiness Report: User Email Validation

## Verdict
✓ READY FOR IMPLEMENTATION

## Summary
4 phases, all safe for TDD. 1 high-risk (Phase 4 migration).
Design validated, research complete, no blockers.

## Phases
1. Phase 1: Validate Email Format (Model)
   - Risk: standard
   - Files: 1 (src/models/user.ts)
   - Est. time: 30 min

2. Phase 2: Email Uniqueness Check (Service)
   - Risk: standard
   - Files: 1 (src/api/user-service.ts)
   - Est. time: 30 min

3. Phase 3: Form Integration (UI)
   - Risk: standard
   - Files: 2 (src/forms/register-form.ts, src/api/user-service.ts)
   - Est. time: 1 hour

4. Phase 4: Schema Migration
   - Risk: high-risk ← requires test-author split
   - Files: 3 (src/db/schema.sql, src/db/migration.js, src/models/user.ts)
   - Est. time: 2-3 hours
   - Test-author: YES (migration rollback tests)

## High-Risk Slices (test-author split required)
- Phase 4: Schema Migration
  - Reason: ALTER TABLE + data backfill + model adjustment
  - test-author action: Write rollback test + failure cases

## Checklist Status
- [x] All items pass
- [x] All Ralph Loops converged
- [x] All Risk Tiers assigned
- [x] No blockers
- [x] Ready to start Red-Green-Refactor

## Next Steps
1. For Phase 1-3: Spawn agent-TDD directly
2. For Phase 4: Spawn test-author first, then agent-TDD
3. Proceed in dependency order (Phase 1 → 2 → 3 → 4)
```

---

## Integration with Red-Green-Refactor

After readiness-check returns `verdict: ready`:

1. **For each slice in dependency order:**
   - If Risk Tier = high-risk:
     - Spawn `agent-tdd:test-author` → writes Red test only
     - Confirm Red fails for intended reason
   - Spawn `agent-tdd:agent-TDD` → implements Red-Green-Refactor
2. After all slices implement successfully, workflow complete

## Guardrails

- **Do not** proceed with `verdict: paused` (genuine blockers)
- **Do not** skip checklist items (all 10 are load-bearing)
- **Do not** accept vague test intents (must be specific)
- **Do not** ignore unresolved blockers (must be resolved or escalated)
- **Do not** assign high-risk without clear reasoning (must be documented)

## Token Efficiency

- Single pass over tasks.md + artifacts
- Reuse prior validation results (ralph-loops, risk-assign)
- No redundant reads or research
