---
max_turns: 15
allowed_tools: [Skill]
tags: [ultra, security]
---

Code review `users.py` at review_level: Ultra. Its full contents, with line numbers:

```python
 1  import sqlite3
 2  
 3  def find_user(conn: sqlite3.Connection, username: str):
 4      cur = conn.execute(f"SELECT id, email FROM users WHERE username = '{username}'")
 5      return cur.fetchone()
```

End your final message with one line per finding in the form
`users.py:<line> — <severity> — <summary>`, or the single line `No findings.` if there are none.
