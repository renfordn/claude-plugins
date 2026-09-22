---
description: Configure cache settings and view current configuration
keywords: [configuration, settings, tuning]
version: 2.0.0
---

# Command: /cache-config

View and change the cache's persisted settings.

## Usage
```
/cache-config [--list] [--get KEY] [--set KEY VALUE] [--reset [KEY]] [--validate]
```

## Options
- `--list` - Show current settings and cache status (default when no option given)
- `--get KEY` - Show one setting
- `--set KEY VALUE` - Change a setting; persisted in `cache.db`, picked up by the next hook/CLI process
- `--reset [KEY]` - Reset one setting, or all of them, to defaults
- `--validate` - Range-check settings and warn on likely misconfiguration (combinable with `--list`)

## Configuration Keys

| Key | Default | Range | Used by |
|-----|---------|-------|---------|
| `maxEntries` | 10000 | ≥ 100 | `CacheManager` — LRU eviction on store |
| `defaultTTL` | 3d | ≥ 1m | `CacheManager` — TTL for entries stored without one |
| `relevanceThreshold` | 75 | 50–95 | `agent-cache-orchestrator` — minimum similarity to reuse an entry |
| `stalenessThreshold` | 1d | ≥ 1m | `agent-cache-orchestrator` — max age before an entry is considered stale |

Durations accept `ms`, `s`, `m`, `h`, `d` (e.g. `7d`, `90m`). Bare integers are milliseconds.

There is no `maxSize` or `evictionPolicy`: the SQLite backend evicts LRU by entry count and does
not track bytes.

## Examples

```
/cache-config --set relevanceThreshold 85
Updated: relevanceThreshold = 85% (was 75%)

/cache-config --set defaultTTL 7d
Updated: defaultTTL = 7d (was 3d)

/cache-config --get relevanceThreshold
relevanceThreshold = 85%

/cache-config --reset relevanceThreshold
Reset: relevanceThreshold = 75% (default)

/cache-config --list --validate
```

Invalid keys or out-of-range values are rejected with a non-zero exit and nothing is written.

## Related Commands
- `/cache-status` - View cache statistics
- `/cache-clear` - Delete cache entries
