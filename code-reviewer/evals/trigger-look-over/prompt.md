---
max_turns: 15
allowed_tools: [Skill]
tags: [trigger]
---

Can you look over this before I merge it? Here's `retry.py`, with line numbers:

```python
 1  import time
 2  
 3  
 4  def retry(fn, attempts=3, delay=1.0):
 5      for i in range(attempts):
 6          try:
 7              return fn()
 8          except Exception:
 9              time.sleep(delay)
10      return fn()
```
