# Code Reviewer parameters

### `review_level`

**Type**: enum (`Quick | Standard | Deep | Ultra`) — optional; defaults to `Standard`. Controls depth of analysis and checks performed.

### Review Levels

Each level defines checks performed, skipped checks, and output style, ordered by scope and depth:

#### **Level 1: Quick (Fact-Finding)**

- **Alias**: Fact-Finding
- **Purpose**: Brief understanding of code purpose and structure; minimal essential feedback
- **Checks Performed**:
  - Basic syntax correctness
  - Function/variable naming clarity
  - Function signature coherence
  - Obvious logic errors (null checks, type mismatches)
  - Import/export completeness (at file level)
- **Skipped Checks**: Impact analysis, design patterns, security implications, performance analysis, cross-file impact
- **Output Style**: Minimal findings, high signal-to-noise ratio; focus on clarity and correctness issues only

#### **Level 2: Standard (Impact/Research) — Default**

- **Alias**: Impact/Research Analysis
- **Purpose**: Comprehensive within scope; understand code usage and cross-file impact
- **Checks Performed**:
  - All Quick level checks
  - Import/export correctness and contract consistency
  - API contract consistency
  - Naming conventions (variable, function, class)
  - Basic design coherence (functions not doing too many things)
  - SOLID-principle violations (Single Responsibility, Open/Closed, Liskov Substitution,
    Interface Segregation, Dependency Inversion) — named explicitly, not folded into generic
    "design coherence"
  - Separation of concerns problems, as their own named check
  - Duplicated logic that should be consolidated into a shared function, method, or class —
    within the diff, and against existing helpers the context step turns up
  - Callers and importers of changed or removed symbols (Review Pipeline step 2)
  - Sibling consistency: a new or changed function that lacks what its neighbours in the same
    file or module all have — an auth/permission decorator, input validation, a transaction or
    lock, error handling, a unit conversion — is a finding; copy-paste additions miss these most
  - Obvious bugs and edge cases
  - Test gaps (Review Pipeline step 4)
- **Skipped Checks**: Security vulnerabilities, performance profiling, regression risk analysis, module-wide coherence, and broader refactoring suggestions beyond the narrow duplicate-consolidation check above (those stay a Level 3/Deep concern)
- **Output Style**: Organized by finding type (correctness, naming, design); severity-tiered; typical current behavior

#### **Level 3: Deep (Coherence/Sanity)**

- **Alias**: Coherence/Sanity Checks
- **Purpose**: Validate function/class definitions and design consistency; thorough design validation
- **Checks Performed**:
  - All Standard level checks
  - Design pattern alignment (does implementation match intended patterns?)
  - Single Responsibility Principle (SRP) validation, extended beyond Standard's SOLID check into
    cross-method judgment calls a diff-scoped pass can't make
  - Interface coherence (methods group logically, no leaky abstractions)
  - Class-level design consistency
  - Module-wide coherence (do related functions form a cohesive unit?)
  - Edge case and error handling comprehensiveness
  - Refactoring suggestions (improve clarity, reduce complexity)
- **Skipped Checks**: Security-specific vulnerabilities, performance profiling, multi-module regression analysis
- **Output Style**: Design-level findings grouped by concern (SRP, interface, patterns); refactoring suggestions included; context-rich evidence

#### **Level 4: Ultra (Deep Analysis + Security)**

- **Alias**: Deep Analysis + Security/Regression Focus
- **Purpose**: Comprehensive analysis including security, performance, and regression risk; final vetting for critical code
- **Checks Performed**:
  - All Deep level checks
  - Security vulnerabilities (injection, authorization, data exposure, crypto, etc.)
  - Regression risk (could changes break existing code outside modified files?)
  - Duplicate detection (code duplication across project scope — distinct from Standard's
    diff/file-scoped duplicate-consolidation check above)
  - Performance implications (memory, I/O, CPU complexity)
  - Refactoring opportunities at whole-system scale
- **Skipped Checks**: None (comprehensive)
- **Output Style**: Full spectrum of findings, severity-tiered; separate security findings; regression risks highlighted; performance notes included

### Auto-Detection Rules

When `review_level` is not explicitly specified, the skill infers level from context using this priority order:

1. **Explicit request** (highest priority): If caller explicitly states a level, use it
2. **ISDD workflow phase** (if available in caller context) — *What to review* per phase:
   - Requirements → `Standard` (EARS formatting, scope, non-goal conflicts)
   - Design → `Deep` (patterns, file touchpoints, slice feasibility)
   - Tasks → `Standard` (phrasing, Depends-On graph, validation steps)
   - Impl per-slice (Red) → `Quick` (test intent, acceptance criteria)
   - Impl per-slice (Green) → `Standard`; `Deep` if `risk_tier: high_risk`
   - Impl post-slices (Coherence) → `Deep`; `Ultra` if majority high-risk slices and multi-agent available
3. **File scope** (if available):
   - Single function → `Quick`
   - Single file → `Standard`
   - Multiple files → `Deep`
   - Entire module/subsystem → `Ultra`
4. **Prior context** (if reviewing same code multiple times):
   - Escalate by one level: `Quick` → `Standard` → `Deep` → `Ultra`
   - User can override by explicit re-request
5. **Fallback** (lowest priority): `Standard` (balanced, comprehensive-within-scope, existing behavior)

### Graceful Degradation

If a level is unavailable (e.g., `Ultra` without multi-agent): degrade to next-lower, notify caller. Never block or auto-upgrade. User always gets some review.
