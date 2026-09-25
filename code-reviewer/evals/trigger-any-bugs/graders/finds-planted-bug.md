---
type: llm
---

PASS if the response reports, as a defect in `average.py`, that `average([])` divides by zero (ZeroDivisionError) because an empty list isn't handled.
FAIL if it doesn't mention this defect.
