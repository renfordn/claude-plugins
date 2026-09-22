---
description: Clear cache entries with flexible filtering options
keywords: [clear, invalidate, filtering, cleanup]
version: 2.0.0
---

# Command: /cache-clear

Delete cache entries by filter, or everything.

## Usage
```
/cache-clear [--all --yes] [--agent AGENT] [--task TASK] [--older-than DAYS] [--before DATE]
             [--pattern SUBSTR] [--id KEY] [--tags A,B]
```

## Options
- `--all --yes` - Delete every entry. `--all` alone only reports the count and asks for `--yes`.
- `--agent AGENT` - Entries whose `agent_type` matches (comma-separate for several)
- `--task TASK` - Entries whose `task_slug` matches
- `--older-than DAYS` - Entries created more than N days ago
- `--before DATE` - Entries created before an ISO 8601 date (e.g. `2026-08-20`)
- `--pattern SUBSTR` - Entries whose key contains the substring
- `--id KEY` - One exact key
- `--tags A,B` - Alias for `--agent A,B` (`agent_type` is the only tag-like column)

Filters combine with AND. With no filter, nothing is deleted and the usage examples are shown.

## Examples

```
/cache-clear --agent agent-tdd:agent-TDD
/cache-clear --older-than 7
/cache-clear --task my-feature --older-than 1
/cache-clear --all --yes
```

## Output
```
Cache Clear Report
═══════════════════════════════════════════

Operation: Cleared entries: agent in [agent-tdd:agent-TDD] AND older than 7 days

Entries Removed:   89
Before:            412 entries
After:             323 entries

═══════════════════════════════════════════
```

Bytes freed are not reported; the SQLite backend does not track entry size.

## Related Commands
- `/cache-status` - View cache statistics
- `/cache-config` - Configure cache settings
