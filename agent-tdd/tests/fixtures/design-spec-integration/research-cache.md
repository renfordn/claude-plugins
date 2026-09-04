# Research Cache: User Authentication System

## design_findings

### File Summaries

#### src/auth/login.ts
- **Status**: Does not exist; needs to be created
- **Purpose**: Handle email/password login requests
- **Expected Exports**: `loginHandler(req, res)`, `validatePassword(password, hash)`
- **Dependencies**: bcrypt library, src/auth/db.ts, src/types/user.ts
- **Test Surface**: Email validation, password hashing, error handling (invalid email, wrong password)

#### src/auth/token.ts
- **Status**: Does not exist; needs to be created
- **Purpose**: JWT token generation and validation
- **Expected Exports**: `generateToken(userId, email)`, `validateToken(token)`, `refreshToken(token)`
- **Dependencies**: jsonwebtoken library, config (secret key), src/types/user.ts
- **Constraints**: RS256 algorithm, 24h expiration, no revocation in Phase 1
- **Test Surface**: Token generation, expiration validation, signature verification

#### src/auth/middleware.ts
- **Status**: Does not exist; needs to be created
- **Purpose**: Express middleware for token validation
- **Expected Exports**: `authMiddleware(req, res, next)`
- **Dependencies**: src/auth/token.ts, Express 4.17+
- **Integration**: Wired into app.use() for protected routes
- **Test Surface**: Valid token acceptance, invalid token rejection, missing token handling

#### src/auth/db.ts
- **Status**: Partially exists (SQLite wrapper boilerplate ready)
- **Needs**: User schema + queries (getUser, createUser, updateUser)
- **Dependencies**: sqlite3, SQLite migration system
- **Test Surface**: User lookup, creation, credential storage

#### src/types/user.ts
- **Status**: Exists with partial definition
- **Current**: `{ id: string; email: string; name?: string }`
- **Needs**: Add `passwordHash` field (internal, not exposed), `createdAt` field
- **Test Surface**: Type correctness, no breaking changes

### Interfaces Documentation

#### LoginRequest / LoginResponse
```typescript
interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  token: string;
  user: { id: string; email: string };
  expiresAt: number;
}
```

#### TokenPayload
```typescript
interface TokenPayload {
  userId: string;
  email: string;
  iat: number;
  exp: number;
}
```

#### Middleware Contract
```typescript
function authMiddleware(req: Request, res: Response, next: NextFunction): void;
```

### Technology Stack

| Layer | Technology | Version | Status |
|-------|-----------|---------|--------|
| Auth | jsonwebtoken | 9.0.0 | ✓ Installed |
| Hashing | bcrypt | 5.1.1 | ✓ Installed |
| Database | sqlite3 | 5.1.6 | ✓ Installed |
| HTTP | Express | 4.18.2 | ✓ Installed |

### Key Constraints

**Cryptography:**
- RS256 requires RSA keypair (can be generated in tests or loaded from env)
- bcrypt: min 10 salt rounds (performance ~100ms per hash)
- No plaintext password storage allowed

**Database:**
- SQLite in-memory for tests
- Production: file-based at `./data/auth.db`
- User table already migrated in prior setup

**API Contract:**
- Login endpoint: `POST /auth/login`
- Token header: `Authorization: Bearer <token>`
- Response format: `{ token, user, expiresAt }`

## task_findings

### Identified Slicing Opportunity

The three architectural layers naturally map to three TDD slices:

1. **Slice 1: Password Hashing & User Lookup** (standard-risk)
   - Files: `src/auth/db.ts`, `src/types/user.ts`
   - Task: Implement `getUser(email)` query, add `passwordHash` to User type, bcrypt integration
   - Test Intent: Query returns user with correct hash, hash validation works

2. **Slice 2: Token Generation & Validation** (standard-risk)
   - Files: `src/auth/token.ts`
   - Task: Implement JWT token generation (RS256) and validation
   - Test Intent: Generated token is valid, expired/invalid tokens rejected
   - Depends On: Slice 1 (User type needed)

3. **Slice 3: Login Handler & Middleware** (high-risk)
   - Files: `src/auth/login.ts`, `src/auth/middleware.ts`
   - Task: Login endpoint validates email/password, generates token; middleware enforces auth
   - Test Intent: Valid credentials login, invalid credentials error, middleware rejects invalid tokens
   - Depends On: Slice 1, Slice 2

### Risk Assessment

- **Slice 1**: Standard (focused database layer, clear test surface)
- **Slice 2**: Standard (cryptography library, no custom implementation)
- **Slice 3**: High-risk (integration point, error paths, edge cases)

### Open Questions (Resolved)

✓ RSA keypair generation: can use jsonwebtoken signing key generation  
✓ Token storage client-side: out of scope (UI layer decision)  
✓ Rate limiting: Phase 2 (not Phase 1)  

## file_summaries

### src/types/user.ts
```typescript
// Current state (before Phase 1):
export interface User {
  id: string;
  email: string;
  name?: string;
}

// Will be extended with:
// passwordHash: string (internal, never exposed)
// createdAt: Date
```

### src/auth/db.ts
```typescript
// Current state (boilerplate ready):
// SQLite wrapper initialized
// Migration system in place
// 
// Needs (Phase 1):
// User table schema created
// getUser(email): Promise<User | null>
// createUser(email, passwordHash): Promise<User>
```

### Dependencies Graph
```
requirements.md (US-1, US-2, US-3)
    ↓
design.md (file touchpoints, interfaces)
    ↓
Slice 1 (db.ts, types/user.ts)
    ↓
Slice 2 (token.ts) ← depends on Slice 1
    ↓
Slice 3 (login.ts, middleware.ts) ← depends on Slice 1, 2
```

## git_hashes

- `src/types/user.ts`: `a1b2c3d4` (last modified 2026-08-20)
- `src/auth/db.ts`: `e5f6g7h8` (migration system added 2026-08-15)
