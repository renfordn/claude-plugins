---
max_turns: 15
allowed_tools: [Skill]
tags: [standard, false-positive]
---

Code review `slugify.py` at review_level: Standard. Its full contents, with line numbers:

```python
 1  import re
 2  
 3  
 4  def slugify(text: str) -> str:
 5      """Lowercase, collapse runs of non-alphanumerics into one hyphen, trim edge hyphens."""
 6      return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
```

End your final message with one line per finding in the form
`slugify.py:<line> — <severity> — <summary>`, or the single line `No findings.` if there are none.
