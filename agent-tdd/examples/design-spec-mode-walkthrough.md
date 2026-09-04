# Design Spec Mode Workflow: Complete Walkthrough

This document walks through a complete Design Spec mode handoff from agent-isdd to agent-tdd, using the User Authentication System as an example.

---

## Setup: Agent-ISDD Prepares Design Spec

Agent-isdd has completed requirements research and design. It prepares:

1. **requirements.md** — User stories with acceptance criteria
2. **design.md** — Architecture, file touchpoints, interfaces, research basis
3. **research-cache.md** — File summaries, technology stack, constraints, slicing opportunity

Agent-isdd sends this Design Spec to agent-tdd with instruction: "Implement using Design Spec mode."

---

## Phase 1: Research Validation

### Agent-TDD Action: Validate Research Completeness

Agent-tdd receives the Design Spec and immediately validates:

**Check 1: Are all design file-touchpoints in research cache?**

```
Design mentions:
  - src/auth/login.ts
  - src/auth/token.ts
  - src/auth/middleware.ts
  - src/auth/db.ts
  - src/types/user.ts

Research cache has file_summaries for:
  ✓ src/auth/login.ts
  ✓ src/auth/token.ts
  ✓ src/auth/middleware.ts
  ✓ src/auth/db.ts
  ✓ src/types/user.ts

Result: PASS
```

**Check 2: Do design interfaces match research documentation?**

```
Design specifies LoginRequest interface:
  {
    email: string;
    password: string;
  }

Research cache documents:
  ```typescript
  interface LoginRequest {
    email: string;
    password: string;
  }
  ```

Result: PASS
```

**Check 3: Are design constraints documented in research?**

```
Design requires: RS256 algorithm, bcrypt hashing, SQLite database

Research cache documents:
  - RS256: ✓ "RS256 algorithm, 24h expiration"
  - bcrypt: ✓ "bcrypt: min 10 salt rounds"
  - SQLite: ✓ "SQLite in-memory for tests, file-based ./data/auth.db"

Result: PASS
```

### Agent-TDD Output: Research Valid

Agent-tdd confirms research is sufficient to proceed:

```
✅ Research Validation Complete
  - All design file-touchpoints documented in cache
  - Design interfaces match research findings
  - All constraints captured in research
  
Proceeding to Phase 2: Task Slicing
```

**Hypothetical Escalation**: If a design file (e.g., `src/auth/crypto.ts`) was NOT in the research cache, agent-tdd would pause:

```
❌ Research Gap Found
  
  File: src/auth/crypto.ts
  Status: Mentioned in design but not in research cache
  
  Design assumes: RSA keypair generation and signature validation logic
  Research gap: No file summary for src/auth/crypto.ts
  
  Action: PAUSING - awaiting targeted research
  Marker: AGENT-TDD-RESEARCH-GAP
```

Agent-isdd receives this, runs targeted research on `src/auth/crypto.ts`, updates research-cache.md, and resumes agent-tdd.

---

## Phase 2: Task Slicing

### Agent-TDD Action: Apply Ralph Loops

Agent-tdd reads the Identified Slicing Opportunity from research-cache.md:

```markdown
### Identified Slicing Opportunity

1. **Slice 1: Password Hashing & User Lookup** (standard-risk)
   - Files: src/auth/db.ts, src/types/user.ts (2 files) ✓
   - Task: getUser(email) query, passwordHash field, bcrypt integration
   - Test Intent: Query returns user with hash, validation works
   - Depends On: None

2. **Slice 2: Token Generation & Validation** (standard-risk)
   - Files: src/auth/token.ts (1 file) ✓
   - Task: JWT token generation (RS256) and validation
   - Test Intent: Generated token is valid, expired/invalid tokens rejected
   - Depends On: Slice 1 (User type needed)

3. **Slice 3: Login Handler & Middleware** (high-risk)
   - Files: src/auth/login.ts, src/auth/middleware.ts (2 files) ✓
   - Task: Login endpoint validates email/password, middleware enforces auth
   - Test Intent: Valid credentials login, invalid credentials error, middleware rejects invalid
   - Depends On: Slice 1, Slice 2
```

### Ralph Loop 1: Slice Size Validation

Agent-tdd checks each slice touches ≤3 files (TDD safe):

```
Slice 1: 2 files (db.ts, types/user.ts) ✓ PASS
Slice 2: 1 file (token.ts) ✓ PASS
Slice 3: 2 files (login.ts, middleware.ts) ✓ PASS

All slices within TDD-safe size limits.
```

### Ralph Loop 2: Dependency Correctness

Agent-tdd constructs dependency graph:

```
Slice 1 → (no dependencies)
Slice 2 → Slice 1
Slice 3 → Slice 1, Slice 2

Topological sort: 1, 2, 3
Acyclic: ✓ YES (no cycles)
```

### Ralph Loop 3: Research-to-Implementation Traceability

Agent-tdd verifies each slice is traceable to research:

```
Slice 1 (User Lookup):
  - Research documents src/auth/db.ts ✓
  - Research documents src/types/user.ts ✓
  - Research specifies bcrypt constraint ✓
  
Slice 2 (Token Generation):
  - Research documents src/auth/token.ts ✓
  - Research documents RS256 requirement ✓
  - Research documents 24h expiration ✓
  
Slice 3 (Login Handler & Middleware):
  - Research documents src/auth/login.ts ✓
  - Research documents src/auth/middleware.ts ✓
  - Research documents LoginRequest interface ✓
```

### Agent-TDD Output: Slicing Complete

Agent-tdd confirms task slicing:

```
✅ Task Slicing Complete (Phase 2 Marker: slicing_complete)
  
Ralph Loops Validation:
  ✓ Slice Size: All slices ≤3 files
  ✓ Dependency Correctness: Acyclic graph
  ✓ Research Traceability: All slices traceable to research
  
Risk Assessment:
  - Slice 1 (standard-risk): Focused database layer
  - Slice 2 (standard-risk): Cryptography library integration
  - Slice 3 (high-risk): Integration point with multiple error paths
  
Proceeding to Per-Slice Implementation
```

**Hypothetical Escalation**: If two slices had a circular dependency:

```
❌ Dependency Conflict
  
  Slice 2 requires Slice 3 (needs Login handler for testing)
  Slice 3 requires Slice 2 (needs Token generation)
  
  Acyclic dependency requirement cannot be met with current design.
  
  Options:
    (a) Change design to isolate changes
    (b) Accept non-minimal slice (merge slices)
    (c) Reorder requirements
  
  Action: PAUSING - awaiting design/product decision
  Marker: Product Decision Required
```

Agent-isdd receives this, design-author decides, updates design.md, and resumes agent-tdd.

---

## Phase 3: Per-Slice Implementation (Red/Green Loops)

### Slice 1: Password Hashing & User Lookup

#### Red: Write Failing Test

Agent-tdd creates test file `tests/auth/test_user_db.ts`:

```typescript
describe("User Lookup and Hashing", () => {
  it("getUser returns user with email match", async () => {
    const user = await getUser("alice@example.com");
    expect(user.email).toBe("alice@example.com");
  });

  it("password hash validation succeeds for correct password", async () => {
    const user = await getUser("alice@example.com");
    const isValid = await validatePassword("password123", user.passwordHash);
    expect(isValid).toBe(true);
  });

  it("password hash validation fails for wrong password", async () => {
    const user = await getUser("alice@example.com");
    const isValid = await validatePassword("wrongpassword", user.passwordHash);
    expect(isValid).toBe(false);
  });
});
```

Tests fail (Red) — functions don't exist yet.

#### Green: Implement Slice 1

Agent-tdd implements `src/auth/db.ts`:

```typescript
import bcrypt from "bcrypt";
import { User } from "../types/user";

export async function getUser(email: string): Promise<User | null> {
  // Query SQLite for user by email
  const user = await db.get("SELECT * FROM users WHERE email = ?", [email]);
  return user || null;
}

export async function validatePassword(
  password: string,
  hash: string
): Promise<boolean> {
  return bcrypt.compare(password, hash);
}
```

Extends `src/types/user.ts`:

```typescript
export interface User {
  id: string;
  email: string;
  name?: string;
  passwordHash: string;
  createdAt: Date;
}
```

Tests pass (Green) — slice complete.

#### Review

Agent-tdd pauses for mandatory review after Green phase. (In real workflow, code review happens here.)

---

### Slice 2: Token Generation & Validation

#### Red: Write Failing Test

Agent-tdd creates `tests/auth/test_token.ts`:

```typescript
describe("JWT Token Generation", () => {
  it("generateToken creates valid JWT", async () => {
    const token = generateToken("user123", "alice@example.com");
    expect(token).toBeTruthy();
  });

  it("validateToken returns payload for valid token", () => {
    const token = generateToken("user123", "alice@example.com");
    const payload = validateToken(token);
    expect(payload.userId).toBe("user123");
    expect(payload.email).toBe("alice@example.com");
  });

  it("validateToken returns null for expired token", () => {
    // Create token with past expiration
    const expiredToken = jwt.sign(
      { userId: "user123", email: "alice@example.com" },
      RSA_PRIVATE_KEY,
      { algorithm: "RS256", expiresIn: "-1h" }
    );
    const payload = validateToken(expiredToken);
    expect(payload).toBeNull();
  });
});
```

Tests fail (Red).

#### Green: Implement Slice 2

Agent-tdd implements `src/auth/token.ts`:

```typescript
import jwt from "jsonwebtoken";

const RSA_PRIVATE_KEY = process.env.RSA_PRIVATE_KEY || generateKey();
const RSA_PUBLIC_KEY = process.env.RSA_PUBLIC_KEY || derivePublicKey();

export function generateToken(userId: string, email: string): string {
  return jwt.sign(
    { userId, email },
    RSA_PRIVATE_KEY,
    { algorithm: "RS256", expiresIn: "24h" }
  );
}

export function validateToken(token: string): TokenPayload | null {
  try {
    const payload = jwt.verify(token, RSA_PUBLIC_KEY, {
      algorithms: ["RS256"],
    }) as TokenPayload;
    return payload;
  } catch {
    return null;
  }
}

export interface TokenPayload {
  userId: string;
  email: string;
  iat: number;
  exp: number;
}
```

Tests pass (Green) — slice complete.

#### Review

Mandatory review pause after Green phase.

---

### Slice 3: Login Handler & Middleware

#### Red: Write Failing Tests

Agent-tdd creates `tests/auth/test_login.ts`:

```typescript
describe("Login Handler", () => {
  it("valid credentials return token", async () => {
    const response = await loginHandler(
      { email: "alice@example.com", password: "password123" },
      res
    );
    expect(response.token).toBeTruthy();
    expect(response.user.email).toBe("alice@example.com");
  });

  it("invalid email returns 401", async () => {
    const response = await loginHandler(
      { email: "nonexistent@example.com", password: "password123" },
      res
    );
    expect(res.statusCode).toBe(401);
  });

  it("invalid password returns 401", async () => {
    const response = await loginHandler(
      { email: "alice@example.com", password: "wrongpassword" },
      res
    );
    expect(res.statusCode).toBe(401);
  });
});

describe("Auth Middleware", () => {
  it("valid token allows request to continue", async () => {
    const token = generateToken("user123", "alice@example.com");
    req.headers.authorization = `Bearer ${token}`;
    
    await authMiddleware(req, res, next);
    expect(next).toHaveBeenCalled();
  });

  it("invalid token returns 403", async () => {
    req.headers.authorization = `Bearer invalid-token`;
    
    await authMiddleware(req, res, next);
    expect(res.statusCode).toBe(403);
  });

  it("missing token returns 401", async () => {
    await authMiddleware(req, res, next);
    expect(res.statusCode).toBe(401);
  });
});
```

Tests fail (Red).

#### Green: Implement Slice 3

Agent-tdd implements `src/auth/login.ts`:

```typescript
import { getUser, validatePassword } from "./db";
import { generateToken } from "./token";
import { Request, Response } from "express";

export async function loginHandler(
  req: Request,
  res: Response
): Promise<void> {
  const { email, password } = req.body;

  const user = await getUser(email);
  if (!user) {
    res.status(401).json({ error: "Invalid email or password" });
    return;
  }

  const isValid = await validatePassword(password, user.passwordHash);
  if (!isValid) {
    res.status(401).json({ error: "Invalid email or password" });
    return;
  }

  const token = generateToken(user.id, user.email);
  res.json({
    token,
    user: { id: user.id, email: user.email },
    expiresAt: Date.now() + 24 * 60 * 60 * 1000,
  });
}
```

Implements `src/auth/middleware.ts`:

```typescript
import { validateToken } from "./token";
import { Request, Response, NextFunction } from "express";

export function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    res.status(401).json({ error: "Missing authorization header" });
    return;
  }

  const [scheme, token] = authHeader.split(" ");
  if (scheme !== "Bearer") {
    res.status(401).json({ error: "Invalid authorization scheme" });
    return;
  }

  const payload = validateToken(token);
  if (!payload) {
    res.status(403).json({ error: "Invalid or expired token" });
    return;
  }

  req.user = payload;
  next();
}
```

Tests pass (Green) — slice complete.

#### Review

Mandatory review pause after Green phase.

---

## Hypothetical Escalation During Slice 3

While implementing the login handler, agent-tdd discovers:

### Example 1: Research Gap During Implementation

```
During Green implementation of login.ts, agent-tdd discovers:
  - Design specifies: "Authentication via email/password"
  - Actual codebase has: User entity with no email field, only username

Discovery: Design assumes User.email field, but research/actual code uses User.username

Action: PAUSE implementation
Emit Research Gap Flag:
```

```
<!--AGENT-TDD-RESEARCH-GAP:
Expected: User interface with email and passwordHash fields for login
Found: User type has id, username, name fields but no email or passwordHash
Impact: Login handler cannot be implemented per design without clarifying User schema
-->
```

Agent-isdd receives this, runs targeted research on the User schema, clarifies what fields actually exist, updates research-cache.md and design.md accordingly, and resumes agent-tdd.

### Example 2: Plan Validity Flag During Slice 3

```
While implementing login handler, agent-tdd checks requirements:
  - Slice 1 acceptance criteria: "Users stored in database with bcrypt hashing"
  - Slice 3 acceptance criteria: "Logout endpoint clears token blacklist"

Conflict discovered: Slice 1 has no token blacklist, Slice 3 requires it.

This is not a research gap (not missing information) or blocker (not unachievable).
This is a task planning error: requirements are contradictory.

Action: PAUSE implementation
Emit Plan Validity Flag:
```

```
<!--AGENT-TDD-PLAN-FLAG:reason="Slice 3 acceptance criteria requires 'logout clears token blacklist' but Slice 1 has no blacklist mechanism. Requirements conflict. Task needs replanning."-->
```

Agent-isdd receives this, reviews requirements, realizes token blacklist is Phase 2 work (not Phase 1), updates requirements.md to clarify Phase 1 scope, and resumes agent-tdd.

---

## Final Handoff Report

When all three slices are complete, agent-tdd emits final handoff report:

```markdown
<!--AGENT-TDD-HANDOFF-REPORT:
mode="Design Spec Mode"
phase="all_slices_complete"
-->

# Design Spec Mode Implementation Complete

## Summary
All three slices implemented and tested:
- Slice 1: Password Hashing & User Lookup ✓
- Slice 2: Token Generation & Validation ✓
- Slice 3: Login Handler & Middleware ✓

## Files Changed
- src/auth/db.ts (new)
- src/auth/token.ts (new)
- src/auth/login.ts (new)
- src/auth/middleware.ts (new)
- src/types/user.ts (extended)

## Tests
- 14 tests passing (100%)
- Coverage: unit and integration

## Escalations
- None during final implementation

## Ready for
- Code review
- Integration testing
- Deployment
```

Agent-isdd receives this report and either:
1. Merges to main (if no escalations and review is clean)
2. Resumes with Phase 2 work (if additional features requested)
3. Surfaces escalations to user for resolution

---

## Key Takeaways

**One-Directional Monitoring**: Agent-isdd doesn't auto-monitor agent-tdd's progress. Agent-tdd completes work and provides a final handoff report.

**Two-Way Escalation**: If agent-tdd encounters missing research, design contradictions, or planning errors, it escalates back to agent-isdd with specific reasons. Agent-isdd addresses the issue and resumes agent-tdd with updated information.

**Authority Boundaries**:
- Agent-tdd implements code, writes tests, validates research completeness
- Agent-isdd owns research, design decisions, requirements, task authority
- Neither agent modifies the other's domain without explicit escalation

**Transparency**: All blockers are explicit. Agent-tdd never silently works around issues.
