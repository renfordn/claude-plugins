# Design: User Authentication System

## Architecture Overview

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   Client    │────────▶│  Auth Middleware │────────▶│   Handler   │
│  (Browser)  │◀────────│   (Validate JWT) │◀────────│  (Express)  │
└─────────────┘         └──────────────────┘         └─────────────┘
       │                        │                           │
       │                        │                           │
       └────────────────────────┴───────────────────────────┘
                        │
                  ┌─────▼──────┐
                  │ auth/db.ts │
                  │  (SQLite)  │
                  └────────────┘
```

## File Touchpoints

- **src/auth/login.ts** — login handler, email/password validation
- **src/auth/token.ts** — JWT token generation and validation
- **src/auth/middleware.ts** — request middleware for token verification
- **src/auth/db.ts** — database layer for user credentials
- **src/types/user.ts** — User type definition

## Interfaces & Contracts

### Login Request/Response
```typescript
interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  token: string;
  user: { id: string; email: string };
  expiresAt: number; // Unix timestamp
}
```

### Token Validation
```typescript
interface TokenPayload {
  userId: string;
  email: string;
  iat: number;
  exp: number;
}

function validateToken(token: string): TokenPayload | null;
```

### Middleware
```typescript
export function authMiddleware(req: Request, res: Response, next: NextFunction): void;
```

### Database Schema
```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Research Basis

**File summaries available for:**
- `src/auth/login.ts` ✓ Exists, auth pattern documented
- `src/auth/token.ts` ✓ JWT library (jsonwebtoken) already vendored
- `src/auth/middleware.ts` ✓ Express middleware pattern established
- `src/auth/db.ts` ✓ SQLite wrapper ready
- `src/types/user.ts` ✓ User type already defined

**Key constraints discovered:**
- Passwords must use bcrypt with salt rounds >= 10
- Token algorithm: RS256 (RSA keypair required)
- Session store: in-memory for Phase 1 (scalability addressed later)
- Middleware chain: Express 4.17+

## Risks And Tradeoffs

### High Risk
- **Cryptography implementation**: using industry-standard library (jsonwebtoken) to mitigate
- **Password storage**: bcrypt enforced, no plaintext paths possible

### Medium Risk
- **Token revocation**: Phase 1 uses expiration only (blacklist deferred to Phase 2)
- **Concurrent logins**: not restricted (multi-device support Phase 2 decision point)

### Low Risk
- **API contract changes**: stable interfaces, backward-compatible defaults
- **Database migration**: additive schema, no breaking changes

## Implementation Strategy

Implement in three phases:

1. **Phase 1**: Login handler + password hashing (1 file, 1-2 day sprint)
2. **Phase 2**: Token generation + validation (1 file, 1-2 day sprint)
3. **Phase 3**: Middleware integration + endpoint wiring (1 file, 1 day sprint)
