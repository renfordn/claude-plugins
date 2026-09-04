---
name: task-slicer
description: Generates TDD-sized, dependency-ordered tasks.md from Design Spec. Extracts behaviors from EARS requirements, maps to files using design and research, groups by affinity, and produces phased slices.
---

# Task Slicer

## Purpose

Given a Design Spec (requirements.md, design.md, validated research_cache), generate a complete `tasks.md` file with phased, TDD-sized slices that are:

- **Safe for TDD:** One behavior change per slice, ≤ 3 files touched, testable in isolation
- **Dependency-ordered:** Acyclic graph, topologically sorted, respects prerequisites
- **Traceable to research:** Each slice's Ordered Steps grounded in design.md and research_cache
- **Risk-tiered:** High-risk slices flagged for test-author split

## Input

**Design Spec:**
- `requirements_md` — approved requirements with EARS section
- `design_md` — approved design with Architecture Or Code Touchpoints
- `research_cache` — validated research (file_summaries, task_findings)
- `recap_md` — known risks, known unknowns

## Algorithm

### Phase 1: Extract Behaviors from Requirements

Parse EARS requirements section. Extract behaviors:

```markdown
## EARS Requirements

- `Ubiquitous`: When a user enters an email in the registration form, the system shall validate format against RFC 5322.
  → Behavior: Validate email format (RFC 5322)

- `Ubiquitous`: When a user enters an email, the system shall check for uniqueness in User.email column.
  → Behavior: Check email uniqueness

- `Unwanted-behavior`: If email is invalid, then the system shall reject form submission and display error.
  → Behavior: Reject invalid email + display error

- `Unwanted-behavior`: If email is duplicate, then the system shall reject and suggest contact support.
  → Behavior: Reject duplicate email + suggest contact support
```

**Output:** Behavior list (4 behaviors in example above)

### Phase 2: Parse Design Touchpoints

Extract from "Architecture Or Code Touchpoints" section:

```markdown
## Architecture Or Code Touchpoints

- src/models/user.ts: Add email property with validation method
- src/api/user-service.ts: Add email uniqueness check before save
- src/forms/register-form.ts: Call UserService.validateEmail before submit
```

**Output:** Touchpoint map (file → description)

### Phase 3: Map Behaviors to Files

For each behavior, identify which files it touches using:
1. Design touchpoints (explicit mapping)
2. Research findings (file_summaries, dependencies)
3. Common patterns (model files for data, service files for business logic, form files for UI)

**Example mapping:**
| Behavior | Files | Reasoning |
|----------|-------|-----------|
| Validate email format | src/models/user.ts | Model owns validation logic (design touchpoint) |
| Check email uniqueness | src/api/user-service.ts | Service does database check (design touchpoint) |
| Reject invalid email | src/forms/register-form.ts | Form displays error (design touchpoint) |
| Reject duplicate email | src/api/user-service.ts | Service enforces constraint (design touchpoint) |
| Suggest contact support | src/forms/register-form.ts | Form displays message (design touchpoint) |

### Phase 4: Group by Affinity & Identify Dependencies

Group behaviors by file/module affinity, keeping each group ≤ 3 files:

**Group 1: Model Validation**
- Behavior: Validate email format
- Files: src/models/user.ts
- Prerequisites: None
- Depends On: [] (no prior slice)

**Group 2: Service Email Check**
- Behavior: Check email uniqueness
- Files: src/api/user-service.ts
- Prerequisites: User model validates (from Group 1)
- Depends On: [Phase 1]

**Group 3: Form Integration**
- Behaviors: Reject invalid email, reject duplicate, suggest contact support
- Files: src/forms/register-form.ts, src/api/user-service.ts
- Prerequisites: Service validates and checks uniqueness (from Group 2)
- Depends On: [Phase 2]

**Dependency rules:**
- If behavior B depends on behavior A, slice with A must come before B
- If slices touch same file, check if order matters (usually yes for data changes)
- Use minimal dependencies (avoid over-ordering)

### Phase 5: Produce tasks.md

Generate `tasks/tasks.md` with structure:

```markdown
# Tasks: Feature Title

## Phase 1: Validate Email Format (Model)

### Objective
Add email validation method to User model that checks RFC 5322 format.

### Risk Tier
standard

### Prerequisites
- None

### Depends On
- [] (no dependencies)

### Ordered Steps
1. Add `validateEmail(email: string): boolean` method to User model
2. Implement RFC 5322 validation logic (use RFC 5322 library if available, else regex)
3. Add email property to User with validation
4. Wire form to call validation before User creation

### Test Intent
- Add or update:
  - Test User.validateEmail() with valid/invalid emails
  - Test email property validation
- Expected failing behavior:
  - ValidationError thrown for invalid email format

### Validation Target
- Command: `npm test -- User.test.ts`
- Evidence: All email format validation tests pass (red → green)

### Unlocks
- Enables Phase 2: Email Uniqueness Check

### Blockers Or Escalation
- [ ] RFC 5322 library availability (check if available, else implement regex)

---

## Phase 2: Email Uniqueness Check (Service)

### Objective
Add uniqueness check in UserService before saving user; reject duplicates.

### Risk Tier
standard

### Prerequisites
- Phase 1: Email validation complete
- User model validates email format

### Depends On
- Phase 1

### Ordered Steps
1. Add `isEmailUnique(email: string): Promise<boolean>` method to UserService
2. Query User repository: `WHERE email = ?`
3. Return true if no match, false if duplicate found
4. Call this method in `saveUser()` before save; throw error if duplicate

### Test Intent
- Add or update:
  - Mock User repository for email uniqueness test
  - Test UserService.isEmailUnique() with duplicate emails
  - Test saveUser() rejects duplicates
- Expected failing behavior:
  - DuplicateEmailError thrown for duplicate emails

### Validation Target
- Command: `npm test -- UserService.test.ts`
- Evidence: Uniqueness check tests pass (red → green)

### Unlocks
- Enables Phase 3: Form Integration

### Blockers Or Escalation
- [ ] Database schema has unique constraint on User.email (verify)

---

## Phase 3: Form Integration (UI)

### Objective
Wire RegisterForm to validate email before submission; display errors.

### Risk Tier
standard

### Prerequisites
- Phase 1: Email validation available
- Phase 2: Email uniqueness check available

### Depends On
- Phase 1
- Phase 2

### Ordered Steps
1. Import validated User model and UserService
2. In RegisterForm.onSubmit():
   - Call User.validateEmail(email)
   - If invalid: display "Invalid email format" error, return
   - Call UserService.isEmailUnique(email)
   - If duplicate: display "Email already in use. Contact support.", return
   - If valid and unique: proceed with form submission
3. Update form UI: show error messages on validation failure
4. Add loading state during service call

### Test Intent
- Add or update:
  - Mock UserService.isEmailUnique() calls
  - Test RegisterForm rejects invalid emails
  - Test RegisterForm rejects duplicates
  - Test RegisterForm displays error messages
- Expected failing behavior:
  - Form submission blocked for invalid/duplicate emails
  - Error messages rendered on screen

### Validation Target
- Command: `npm test -- RegisterForm.test.tsx`
- Evidence: Form validation integration tests pass (red → green)

### Unlocks
- None (feature complete)

### Blockers Or Escalation
- [ ] Form state management (verify React hook compatibility)

---

## Task Readiness Checklist

- [x] At least one concrete phase exists (3 phases defined)
- [x] Each phase has: objective, Risk Tier, steps, test intent, validation target
- [x] Slices are safe for TDD (all ≤ 2 files, ≤ 2 dependencies)
- [x] No unresolved blocker requires confirmation
- [x] State: Ready For Implementation
```

## Output Format

Return structured tasks.md ready for:
1. Ralph Loops validation (next phase)
2. Risk Tier assignment
3. Red-Green-Refactor execution per slice

## Guardrails

- **Do not** create slices > 3 files (hard limit for TDD isolation)
- **Do not** leave unresolved dependencies (topological sort must be acyclic)
- **Do not** assume test surfaces (derive from research_cache)
- **Do not** infer Ordered Steps not grounded in design or research
- **Do not** skip Prerequisites (they explain why slice must run)
- **Do not** create cycles (Phase N cannot depend on Phase > N)

## Algorithm Correctness Checks

**Before returning tasks.md, verify:**

1. **Behavior Coverage:** Every EARS requirement maps to at least one slice
2. **File Affinity:** Slices with same file are ordered by data dependency
3. **Dependency Acyclicity:** Topological sort succeeds (no cycles)
4. **Slice Size:** All slices ≤ 3 files
5. **Test Feasibility:** Each slice's Test Intent is implementable (not too broad)
6. **Traceability:** Each Ordered Step references a file in the slice or design touchpoint

**If any check fails:** Reslice and retry (see Ralph Loops phase next).

## Token Efficiency

- Single pass (no redundant behavior extraction)
- Dependency inference from design + research (no extra reads)
- Slicing is deterministic (given input, output is stable)

## Example Output

See `references/examples/user-email-validation/` for a complete tasks.md example.

## Integration with Ralph Loops

This agent produces `tasks.md` suitable for Ralph Loops validation:
- **Slice Size Loop** — validates ≤ 3 files per slice
- **Dependency Correctness Loop** — validates acyclic dependencies
- **Research-to-Implementation Traceability Loop** — validates Ordered Steps are grounded

If Ralph Loops find violations, task-slicer must re-slice and iterate.
