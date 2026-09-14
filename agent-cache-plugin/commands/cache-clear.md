---
description: Clear cache entries with flexible filtering options
keywords: [clear, invalidate, filtering, cleanup]
version: 1.0.0
---

# Command: /cache-clear

Clear cache entries, with granular control over what gets removed.

## Usage
```
/cache-clear [--all] [--agent AGENT] [--task TASK] [--older-than DAYS] [--before DATE]
```

## Options
- `--all` - Clear entire cache (requires confirmation)
- `--agent AGENT` - Clear entries for specific agent type (e.g., agent-tdd)
- `--task TASK` - Clear entries for specific task type (e.g., implementation, testing)
- `--older-than DAYS` - Clear entries older than N days
- `--before DATE` - Clear entries created before ISO 8601 date (e.g., 2026-08-20)
- `--tags TAG1,TAG2` - Clear entries matching any of these tags
- `--yes` - Skip confirmation prompt

## Examples

### Clear by agent type
```
/cache-clear --agent agent-tdd
Clearing cache for agent-tdd... Done.
Removed: 234 entries (15.2 MB)
```

### Clear old entries
```
/cache-clear --older-than 7
Clearing entries older than 7 days... Done.
Removed: 89 entries (5.8 MB)
```

### Clear everything (with confirmation)
```
/cache-clear --all
⚠️  This will delete ALL cache entries (2,456 entries, 156 MB).
Continue? (yes/no): yes
Clearing entire cache... Done.
Removed: 2,456 entries (156 MB)
```

### Clear with tags
```
/cache-clear --tags "stale,testing"
Clearing entries with tags: stale, testing... Done.
Removed: 145 entries (9.3 MB)
```

## Output
Returns summary:
- Number of entries removed
- Total size freed
- Estimated time to recalculate now missing from cache

## Related Commands
- `/cache-status` - View cache statistics
- `/cache-config` - Configure cache settings
- `/cache-search` - Search cache entries

## Safety
- Always shows what will be deleted before proceeding
- Requires confirmation for `--all` unless `--yes` flag provided
- Deletion is permanent; consider export before clearing large volumes

## Notes
- When clearing by criteria, provides count and size impact before confirmation
- Freed space is reclaimed immediately from in-memory storage
- For persistent backends, freed entries are marked deleted but storage may remain until compaction
