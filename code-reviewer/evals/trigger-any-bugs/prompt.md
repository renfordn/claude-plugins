---
max_turns: 15
allowed_tools: [Skill]
tags: [trigger]
---

Any bugs in this? Here's `average.py`, with line numbers:

```python
 1  def average(values):
 2      """Mean of a list of numbers."""
 3      total = 0
 4      for v in values:
 5          total += v
 6      return total / len(values)
```
