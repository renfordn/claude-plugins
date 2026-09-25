---
max_turns: 15
allowed_tools: [Skill]
tags: [trigger]
---

Is this change safe to ship? Here's `session.py`, with line numbers:

```python
 1  import hashlib
 2  
 3  
 4  def check_password(stored_hash: str, password: str) -> bool:
 5      return hashlib.md5(password.encode()).hexdigest() == stored_hash
```
