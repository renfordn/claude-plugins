---
max_turns: 15
allowed_tools: [Skill]
tags: [standard, correctness]
---

Code review `config.py` at review_level: Standard. Its full contents, with line numbers:

```python
 1  import os
 2  
 3  def db_port() -> int:
 4      raw = os.environ.get("DB_PORT")
 5      return int(raw.strip())
```

End your final message with one line per finding in the form
`config.py:<line> — <severity> — <summary>`, or the single line `No findings.` if there are none.
