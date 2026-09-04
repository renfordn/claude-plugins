---
name: risk-assign
description: Assigns Risk Tiers (high-risk vs. standard) to each slice based on design risks, migrations, module complexity, testability, and Ralph Loops findings.
---

# Risk Assign

## Purpose

Assign a `Risk Tier` (either `high-risk` or `standard`) to each slice in `tasks.md`. High-risk slices trigger a test-author split (test-author writes Red test first, then agent-TDD implements).

## Input

- `tasks.md` — slices from task-slicer (with Ordered Steps, files, test intent)
- `design.md` — Risks And Tradeoffs section
- `ralph_loops_report` — Loop 3 traceability warnings/flags

## Algorithm

### Step 1: Identify Risk Factors

For each slice, check 5 risk categories:

**Category 1: Design-Named Risks**

Parse `design.md`'s "Risks And Tradeoffs" section:

```markdown
## Risks And Tradeoffs

- Risk: Email validation adds latency to registration form
  Mitigation: Cache validator instance, benchmark before launch
  Affected files: src/api/email-validator.ts, src/forms/register-form.ts

- Risk: Immutable User model may conflict with future updates
  Mitigation: Plan for User.update() method as separate phase
  Affected files: src/models/user.ts
```

Extract: Risk name → Affected files

For each slice, check: **"Do any of this slice's files appear in design.md's Risk section?"**

- If yes: **HIGH-RISK** (design explicitly named it)
- If no: Continue to next category

**Category 2: Migration Indicators**

Check if slice involves:
- Schema changes (ALTER TABLE, CREATE TABLE, DROP COLUMN)
- API breaking changes (method signature change, removal)
- Database migration (data transformation, backfill)
- Dependency upgrade with behavior change

If any found: **HIGH-RISK** (migrations are high-impact)

Detection heuristics:
- "schema" or "migration" in Ordered Steps
- "breaking" or "breaking change" in description
- "backfill" or "data transformation" in steps
- "upgrade" or "dependency" with "breaking"

**Category 3: Multi-Module Complexity**

Check if slice touches multiple independent modules (not just related files):

```
Independent modules:
- Model layer (src/models/*)
- API/Service layer (src/api/*)
- UI/Form layer (src/forms/*)
- Database layer (src/db/*)
```

If slice touches 3+ independent modules: **HIGH-RISK** (complexity + integration risk)

Example:
- Slice touches: src/models/user.ts (Model), src/api/user-service.ts (API), src/forms/register-form.ts (UI)
- 3 independent modules → HIGH-RISK (unless explicitly separate phases)

**Category 4: Weak Testability**

Check Test Intent for testability signals:

**Red flags (HIGH-RISK):**
- "Integration test with real database" (hard to isolate)
- "Manual testing only" (not automatable)
- "Requires external API call" (flaky)
- "Cannot mock easily" (tight coupling)
- "Tests take > 5 seconds" (slow feedback)

**Green flags (STANDARD):**
- "Unit test with mocked dependencies"
- "Tests complete in < 1 second"
- "Clear test surface"

If majority of flags are red: **HIGH-RISK**

**Category 5: Ralph Loops Warnings**

Check ralph_loops_report for Loop 3 (Traceability) findings:

```json
{
  "loop_name": "Research-to-Implementation Traceability",
  "violations": [
    {
      "phase": "Phase 4",
      "issue": "database migration lacks rollback strategy",
      "risk_level": "high"
    }
  ]
}
```

If Loop 3 flagged this slice: **HIGH-RISK**

### Step 2: Assign Risk Tier

**Decision tree:**

```
if any(design_named_risk, migration, multi_module_risky, weak_testability, ralph_loop_warning):
  risk_tier = "high-risk"
  reason = [list triggering factors]
else:
  risk_tier = "standard"
  reason = "No risk factors identified"
```

### Step 3: Update tasks.md

Add or update `Risk Tier` field in each phase:

```markdown
## Phase 1: Validate Email Format

### Risk Tier
standard

### Reasoning
- No design-named risks
- No migrations
- Single module (Model layer only)
- Clear test surface (unit test)
- No Ralph Loops warnings
```

vs.

```markdown
## Phase 4: Schema Migration

### Risk Tier
high-risk

### Reasoning
- Design risk: "Schema changes impact existing data"
- Category: Migration (ALTER TABLE)
- Category: Multi-module (schema + migration script + model adjustment)
- Category: Ralph Loops warning (Loop 3: rollback strategy missing)
- Trigger test-author split
```

## Output Format

```json
{
  "phase": "Phase 4",
  "risk_tier": "high-risk",
  "factors": [
    "Design-named risk: schema changes impact existing data",
    "Migration: ALTER TABLE + data backfill",
    "Multi-module: 3 independent layers (schema, migration, model)",
    "Ralph Loops warning: rollback strategy incomplete"
  ],
  "test_author_split": true
}
```

## Integration with Red-Green-Refactor

**High-risk slices (Risk Tier = high-risk):**
1. Spawn `agent-tdd:test-author` (writes Red test only, no implementation)
2. Confirm Red test fails for intended reason
3. Then spawn `agent-tdd:agent-TDD` (implements Red-Green-Refactor)

**Standard slices (Risk Tier = standard):**
1. Directly spawn `agent-tdd:agent-TDD`
2. Test-author split optional (can be done if desired, but not required)

## Guardrails

- **Do not** over-assign high-risk (genuine risk only, not caution)
- **Do not** ignore design-named risks (they're intentional flags)
- **Do not** miss migrations (always high-risk)
- **Do not** assign risk without clear reasoning
- **Do not** contradict design intent (if design says "high-risk," mark high-risk)

## Examples

### Example 1: Standard Risk

**Slice:**
```markdown
## Phase 1: Validate Email Format

Ordered Steps:
1. Add validateEmail() method to User model
2. Implement RFC 5322 validation logic
3. Add email property to User

Test Intent:
- Unit test User.validateEmail() with valid/invalid emails
- Mock: none (pure function)
- Duration: < 1 second
```

**Risk Analysis:**
- ❌ No design-named risk (design.md silent on this)
- ❌ No migration (property add only)
- ❌ Single module (Model layer)
- ✓ Clear test surface (unit test, mocked nothing, pure function)
- ❌ No Ralph Loops warnings

**Result:** `risk_tier = standard`

---

### Example 2: High-Risk (Migration)

**Slice:**
```markdown
## Phase 4: Schema Migration

Ordered Steps:
1. Create migration script: ALTER TABLE User ADD COLUMN email VARCHAR(255) NOT NULL
2. Backfill existing users with placeholder email
3. Update User model to include email property

Test Intent:
- Migration test on test database
- Verify: column created, existing data preserved, new model reflects schema
- Cannot easily mock (requires real database)
```

**Risk Analysis:**
- ✓ Design-named risk (design.md mentions "Schema changes impact existing data")
- ✓ Migration (ALTER TABLE + backfill)
- ✓ Multi-module (schema + migration script + model adjustment)
- ❌ Weak testability? (requires real database, but acceptable for migration)
- ✓ Ralph Loops warning (Loop 3 flagged: "rollback strategy incomplete")

**Result:** `risk_tier = high-risk` (migration + design-named risk + Ralph Loops flag)
**Test-author split:** YES (test-author writes rollback test, agent-TDD implements)

---

### Example 3: High-Risk (Design Contradiction Risk)

**Slice:**
```markdown
## Phase 5: Async Email Validation

Ordered Steps:
1. Add async validateEmailAsync() to UserService
2. Call external email verification API
3. Update form to await validation result
4. Handle network failures gracefully

Test Intent:
- Integration test with external API
- Mock external API responses
- Test failure cases (timeout, 500 error)
```

**Risk Analysis:**
- ❌ No explicit design-named risk
- ❌ No migration
- ✓ Multi-module? (Service + Form = 2 modules, borderline)
- ✓ Weak testability (external API, integration test, not pure unit test, > 1 second)
- ❌ No Ralph Loops warnings (but design did mention this as a follow-up risk)

**Result:** `risk_tier = high-risk` (weak testability + network I/O risk)
**Test-author split:** YES (test-author writes network failure tests first)

## Token Efficiency

- Single pass over tasks.md
- Reuse design.md + ralph_loops_report (no extra reads)
- Deterministic assignment (no ambiguity)

## Integration with Readiness-Check

After risk assignment, readiness-check validates:
- [ ] All slices have Risk Tier assigned
- [ ] High-risk slices have clear reasoning
- [ ] test-author split is available for high-risk (in current session)
