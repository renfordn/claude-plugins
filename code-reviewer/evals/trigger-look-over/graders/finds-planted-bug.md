---
type: llm
---

PASS if the response reports, as a defect in `retry.py`, that after the loop's attempts are exhausted it calls `fn()` a further time outside the try, so it makes attempts + 1 calls and lets that last exception escape (or the loop should re-raise on the final attempt).
FAIL if it doesn't mention this defect.
