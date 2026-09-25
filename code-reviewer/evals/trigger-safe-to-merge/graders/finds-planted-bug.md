---
type: llm
---

PASS if the response reports, as a defect in `session.py`, that passwords are hashed with unsalted MD5 (a fast, broken hash) instead of a slow salted KDF like bcrypt/scrypt/argon2, and the comparison isn't constant-time.
FAIL if it doesn't mention this defect.
