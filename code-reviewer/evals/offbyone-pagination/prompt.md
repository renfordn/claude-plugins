---
max_turns: 15
allowed_tools: [Skill]
tags: [standard, correctness]
---

Code review `paginate.py` at review_level: Standard. Its full contents, with line numbers:

```python
 1  def paginate(items, page, page_size):
 2      """Return the items on 1-indexed page `page`."""
 3      if page < 1 or page_size < 1:
 4          raise ValueError("page and page_size must be >= 1")
 5      start = page * page_size
 6      return items[start:start + page_size]
```

End your final message with one line per finding in the form
`paginate.py:<line> — <severity> — <summary>`, or the single line `No findings.` if there are none.
