---
type: llm
---

PASS if the response reports, as a defect in `config.py`, that `os.environ.get` returns None when DB_PORT is unset, so `raw.strip()` raises AttributeError instead of a clear error or a default.
FAIL if it doesn't mention this defect, or mentions it only as a style or naming concern.
