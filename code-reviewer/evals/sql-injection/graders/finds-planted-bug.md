---
type: llm
---

PASS if the response reports, as a defect in `users.py`, that the username is interpolated into the SQL string with an f-string, allowing SQL injection; it should use a parameterized query (`?` placeholder).
FAIL if it doesn't mention this defect, or mentions it only as a style or naming concern.
