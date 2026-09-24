---
description: Display cache statistics and health metrics
keywords: [status, metrics, monitoring, statistics]
version: 1.0.0
---

# Command: /cache-status

Display current cache statistics and health metrics.

## Usage
```
/cache-status [--detailed] [--export json|csv|html]
```

## Run
```bash
CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" node "${CLAUDE_PLUGIN_ROOT}/scripts/cache-command.js" status [options]
```
Pass `CLAUDE_PLUGIN_DATA` explicitly -- the Bash tool doesn't have it, and the script refuses to guess a data directory.

## Options
- `--detailed` - Show detailed breakdown by agent type, task type
- `--export FORMAT` - Export report in specified format

## Output
```
Cache Status Report
==================

Overall Stats:
  Total Entries: 1,234
  Cache Size: 42.5 MB / 100 MB (42.5%)
  Hit Rate: 18.5% (1,247 hits / 6,745 queries)
  Avg Retrieval Time: 8.3ms

Trend (Last 24h):
  Hit Rate: ↑ 2.1%
  Avg Entry Age: 18.2 hours
  Evictions: 45 entries

Top Agents:
  1. agent-tdd:agent-TDD - 312 hits, 28.7% hit rate
  2. Explore - 198 hits, 22.3% hit rate
  3. Plan - 89 hits, 15.2% hit rate

Recommendations:
  • Consider increasing TTL for research entries (high hit rate)
  • Monitor low-value implementation caches (0 hits in 24h)
  • Cache efficiency: 2.9 tokens saved per byte stored
```

## Related Commands
- `/cache-clear` - Clear cache or specific entries
- `/cache-config` - Configure cache settings
- `/cache-search` - Search cache entries
