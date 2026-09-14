---
description: Configure cache settings and view current configuration
keywords: [configuration, settings, tuning]
version: 1.0.0
---

# Command: /cache-config

Configure cache behavior, thresholds, storage limits, and eviction policies.

## Usage
```
/cache-config [--list] [--set KEY VALUE] [--reset KEY] [--validate]
```

## Options
- `--list` - Show current configuration
- `--set KEY VALUE` - Set a configuration value
- `--reset KEY` - Reset configuration key to default
- `--validate` - Check configuration validity and warn on issues
- `--export FORMAT` - Export current config in json|yaml|env format

## Configuration Keys

### Cache Behavior
- `relevanceThreshold` (default: 75, range: 0-100) - Minimum similarity score to use cached entry
- `stalenessThreshold` (default: 24h) - Maximum age of cached entry (e.g., 24h, 7d)
- `maxEntries` (default: 10000) - Maximum number of cache entries
- `maxSize` (default: 100MB) - Maximum cache size in memory (e.g., 100MB, 1GB)
- `evictionPolicy` (default: LRU) - Policy when limits reached: LRU, LFU, or FIFO

### Validation
- `minRelevanceScore` (default: 70) - Validator minimum relevance (0-100)
- `maxEntryAge` (default: 7d) - Maximum entry age before marking stale

### Storage
- `backend` (default: memory) - Storage backend: memory, redis, dynamodb, file
- `persistenceEnabled` (default: false) - Enable persistent storage
- `compressionEnabled` (default: false) - Compress large entries in storage

### Metrics
- `metricsRetention` (default: 30d) - How long to keep metrics events
- `autoCleanupEnabled` (default: true) - Automatic cleanup of old metrics
- `samplingRate` (default: 1.0) - Record fraction of events (0.0-1.0)

## Examples

### List current configuration
```
/cache-config --list

Current Configuration
====================
Cache Behavior:
  relevanceThreshold: 75
  stalenessThreshold: 24h
  maxEntries: 10000
  maxSize: 100MB
  evictionPolicy: LRU

Validation:
  minRelevanceScore: 70
  maxEntryAge: 7d

Storage:
  backend: memory
  persistenceEnabled: false

Metrics:
  metricsRetention: 30d
  autoCleanupEnabled: true
  samplingRate: 1.0
```

### Increase relevance threshold
```
/cache-config --set relevanceThreshold 85
Updated: relevanceThreshold = 85 (was 75)
Impact: More strict matching; expect lower hit rate, fewer false positives
```

### Extend cache retention
```
/cache-config --set stalenessThreshold 7d
Updated: stalenessThreshold = 7d (was 24h)
Impact: Cache entries valid for 7 days instead of 24 hours
```

### Set maximum cache size
```
/cache-config --set maxSize 500MB
Updated: maxSize = 500MB (was 100MB)
Impact: Cache can grow up to 500MB; requires sufficient memory
```

### Enable persistent storage
```
/cache-config --set persistenceEnabled true
⚠️  Persistent storage requires backend configuration (Redis, DynamoDB, or file storage).
Have you configured the backend? (yes/no): yes
Updated: persistenceEnabled = true
```

### Validate configuration
```
/cache-config --validate

Configuration Validation
========================
✓ relevanceThreshold (75): within acceptable range
✓ maxSize (100MB): sufficient for typical use
✓ evictionPolicy (LRU): well-suited for read-heavy workload
⚠ samplingRate (0.5): only sampling 50% of events; may miss patterns
⚠ backend (memory): data lost on restart; consider persistence

Recommendations:
  • Enable persistence for production use
  • Increase samplingRate to 1.0 for better metrics
  • Monitor cache hit rate; consider adjusting relevanceThreshold if <20%
```

### Reset to defaults
```
/cache-config --reset relevanceThreshold
Reset: relevanceThreshold = 75 (default)
```

## Related Commands
- `/cache-status` - View cache statistics
- `/cache-clear` - Clear cache entries
- `/cache-search` - Search cache entries

## Persistence
Configuration changes take effect immediately and are persisted across sessions.

## Tuning Guide

### For Development (Low Throughput)
```
/cache-config --set relevanceThreshold 70
/cache-config --set stalenessThreshold 24h
/cache-config --set maxSize 100MB
/cache-config --set evictionPolicy LRU
```

### For Production (High Throughput)
```
/cache-config --set relevanceThreshold 80
/cache-config --set stalenessThreshold 48h
/cache-config --set maxSize 1GB
/cache-config --set evictionPolicy LRU
/cache-config --set persistenceEnabled true
```

### For Research (Long TTL, Many Entries)
```
/cache-config --set stalenessThreshold 7d
/cache-config --set maxEntries 50000
/cache-config --set maxSize 500MB
/cache-config --set relevanceThreshold 65
```

## Notes
- Changes apply immediately to new cache operations
- Existing cache entries not retroactively affected by threshold changes
- `--validate` helps spot configuration issues before they impact performance
- Export current config for backup before making major changes
