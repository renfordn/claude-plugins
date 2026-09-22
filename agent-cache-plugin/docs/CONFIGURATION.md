# Cache Configuration Guide

> **⚠️ Accuracy warning (2026-09-22):** much of this guide predates the SQLite rewrite and
> describes a configuration model that no longer exists — `maxSize`, `evictionPolicy`,
> `backend`, `persistenceEnabled`, `compressionEnabled`, `samplingRate` and the storage/metrics
> sections below are **not implemented**, and `/cache-config --set` rejects those keys. The four
> settings that actually exist are `maxEntries`, `defaultTTL`, `relevanceThreshold` and
> `stalenessThreshold` — see [commands/cache-config.md](../commands/cache-config.md), which is
> authoritative. A full rewrite of this file is tracked in [ROADMAP.md](ROADMAP.md).

## Overview

The agent-cache-plugin can be configured to suit different deployment environments and usage patterns. This guide covers all configuration options, recommended settings for common scenarios, and tuning strategies.

## Configuration Keys

### Storage & Capacity

#### maxSize
Maximum cache size in bytes.

- **Default:** 100 MB (100 * 1024 * 1024)
- **Type:** number
- **Unit:** bytes
- **Typical Range:** 50 MB - 5 GB

When cache size exceeds this limit, entries are evicted according to the eviction policy.

```javascript
await cacheManagement.configure({ maxSize: 500 * 1024 * 1024 }); // 500 MB
```

#### maxEntries
Maximum number of cache entries.

- **Default:** 10,000
- **Type:** number
- **Typical Range:** 1,000 - 100,000

When entry count exceeds this limit, entries are evicted according to the eviction policy.

```javascript
await cacheManagement.configure({ maxEntries: 50000 }); // 50k entries
```

### Expiration & TTL

#### defaultTTL
Default time-to-live for cache entries in milliseconds.

- **Default:** 3 days (3 * 24 * 60 * 60 * 1000 = 259,200,000 ms)
- **Type:** number
- **Unit:** milliseconds
- **Typical Range:** 1 hour - 30 days

Individual entries can override this via metadata.ttl.

```javascript
// 7 days
await cacheManagement.configure({
  defaultTTL: 7 * 24 * 60 * 60 * 1000
});

// 4 hours
await cacheManagement.configure({
  defaultTTL: 4 * 60 * 60 * 1000
});
```

### Eviction Strategy

#### evictionPolicy
Policy for evicting entries when limits are reached.

- **Default:** 'LRU' (Least Recently Used)
- **Options:** 'LRU' | 'LFU' | 'FIFO'
- **Type:** string

**LRU (Least Recently Used)** - Recommended for most scenarios
- Evicts entries accessed longest ago
- Good for typical access patterns
- Preserves frequently-used entries

**LFU (Least Frequently Used)**
- Evicts entries with fewest accesses
- Better for quality-based selection
- Useful when some entries are clearly more valuable

**FIFO (First In First Out)**
- Evicts oldest entries by creation time
- Most predictable
- Less optimal for performance

```javascript
await cacheManagement.configure({ evictionPolicy: 'LRU' });
```

## Environment-Specific Configurations

### Development Environment

**Goal:** Fast iteration, maximum debugging visibility, short retention.

```javascript
await cacheManagement.configure({
  maxSize: 50 * 1024 * 1024,              // 50 MB (small but sufficient)
  maxEntries: 1000,                        // Fewer entries
  defaultTTL: 1 * 60 * 60 * 1000,          // 1 hour
  evictionPolicy: 'FIFO'                   // Predictable, simple cleanup
});
```

**Rationale:**
- Small size reduces disk usage during development
- Short TTL avoids stale cached results during testing
- FIFO is simpler to reason about

### Testing Environment

**Goal:** Isolation, deterministic behavior, fast cleanup.

```javascript
await cacheManagement.configure({
  maxSize: 10 * 1024 * 1024,               // 10 MB
  maxEntries: 100,                         // Very limited
  defaultTTL: 5 * 60 * 1000,               // 5 minutes
  evictionPolicy: 'FIFO'                   // Predictable
});

// Clear cache between test suites
await cacheManagement.clear();
```

**Rationale:**
- Tiny cache prevents test interference
- Very short TTL ensures fresh state
- FIFO makes eviction timing predictable for assertions

### Production Environment

**Goal:** High performance, efficient resource usage, balanced retention.

```javascript
await cacheManagement.configure({
  maxSize: 2 * 1024 * 1024 * 1024,         // 2 GB
  maxEntries: 50000,                       // High capacity
  defaultTTL: 3 * 24 * 60 * 60 * 1000,     // 3 days (default)
  evictionPolicy: 'LRU'                    // Optimal performance
});
```

**Rationale:**
- Large size maximizes cache benefits
- LRU preserves valuable entries
- 3-day TTL balances freshness and reuse

### Research/Experimentation Environment

**Goal:** Maximize cache hits, long retention, quality-based selection.

```javascript
await cacheManagement.configure({
  maxSize: 5 * 1024 * 1024 * 1024,         // 5 GB (maximize storage)
  maxEntries: 100000,                      // Very high capacity
  defaultTTL: 7 * 24 * 60 * 60 * 1000,     // 7 days
  evictionPolicy: 'LFU'                    // Keep most-used results
});
```

**Rationale:**
- Large cache maximizes research continuity
- LFU prioritizes frequently-accessed (high-value) results
- Longer TTL preserves research decisions

### CI/CD Pipeline

**Goal:** Fast, lightweight, no persistence between runs.

```javascript
await cacheManagement.configure({
  maxSize: 100 * 1024 * 1024,              // 100 MB
  maxEntries: 5000,                        // Moderate
  defaultTTL: 2 * 60 * 60 * 1000,          // 2 hours (single run)
  evictionPolicy: 'FIFO'                   // Simple
});
```

**Rationale:**
- Cache only helps within a single run
- Small size keeps CI fast
- FIFO is simple and deterministic

## TTL Strategy by Task Type

Use different TTL values based on task characteristics:

### Simple Tasks (High Stability)
```javascript
// Code formatting, syntax checks, simple refactors
metadata: { ttl: 7 * 24 * 60 * 60 * 1000 } // 7 days
```

### Medium Tasks (Typical Work)
```javascript
// General refactoring, reviews, documentation
metadata: { ttl: 3 * 24 * 60 * 60 * 1000 } // 3 days (default)
```

### Complex Tasks (Research, Planning)
```javascript
// Design analysis, architecture decisions
metadata: { ttl: 24 * 60 * 60 * 1000 } // 1 day
```

### High-Risk Tasks (Sensitive)
```javascript
// Security decisions, breaking changes, migrations
metadata: { ttl: 4 * 60 * 60 * 1000 } // 4 hours
```

## Performance Tuning

### Optimizing Hit Rate

**Increase relevant entries:**
```javascript
// Store more entries before eviction
await cacheManagement.configure({
  maxSize: 1 * 1024 * 1024 * 1024,
  maxEntries: 50000
});
```

**Increase TTL to keep entries longer:**
```javascript
// Double the default TTL
await cacheManagement.configure({
  defaultTTL: 6 * 24 * 60 * 60 * 1000 // 6 days
});
```

**Use LFU for quality-based selection:**
```javascript
// Keeps high-value entries
await cacheManagement.configure({
  evictionPolicy: 'LFU'
});
```

### Reducing Memory Usage

**Decrease cache size:**
```javascript
await cacheManagement.configure({
  maxSize: 50 * 1024 * 1024,    // 50 MB
  maxEntries: 5000
});
```

**Reduce TTL to expire entries faster:**
```javascript
await cacheManagement.configure({
  defaultTTL: 24 * 60 * 60 * 1000 // 1 day instead of 3
});
```

**Use FIFO for predictable cleanup:**
```javascript
await cacheManagement.configure({
  evictionPolicy: 'FIFO' // Simpler than LRU
});
```

### Improving Query Speed

**Monitor statistics:**
```javascript
const stats = await cacheManagement.stats();
console.log(`Average retrieval time: ${stats.avgRetrievalTime}ms`);
```

**Use search with tags and limits:**
```javascript
// Faster: specific tags + limit
const results = await cacheManagement.search({
  tags: ['agent-tdd'],
  limit: 100
});

// Slower: pattern match across all entries
const results = await cacheManagement.search({
  pattern: 'refactor',
  limit: 10000
});
```

## Monitoring Configuration

### Check Current Configuration

```javascript
const stats = await cacheManagement.stats();

console.log('Cache Health Metrics:');
console.log(`  Utilization: ${stats.utilizationPercent}%`);
console.log(`  Hit Rate: ${(stats.hitRate * 100).toFixed(1)}%`);
console.log(`  Avg Retrieval: ${stats.avgRetrievalTime.toFixed(2)}ms`);
console.log(`  Entries: ${stats.totalEntries} / configured limit`);
```

### Alerts & Thresholds

**High utilization (>90%):**
```javascript
if (stats.utilizationPercent > 90) {
  // Increase maxSize or reduce TTL
  await cacheManagement.configure({
    maxSize: currentConfig.maxSize * 2
  });
}
```

**Low hit rate (<30%):**
```javascript
if (stats.hitRate < 0.3) {
  // Entries expire too quickly or not relevant
  await cacheManagement.configure({
    defaultTTL: currentConfig.defaultTTL * 2
  });
}
```

**High eviction rate:**
```javascript
if (stats.totalEvictions > stats.totalStores) {
  // Cache is thrashing, increase limits
  await cacheManagement.configure({
    maxSize: currentConfig.maxSize * 1.5,
    maxEntries: currentConfig.maxEntries * 1.5
  });
}
```

## Configuration via Environment Variables

Set configuration through environment variables:

```bash
# Cache size (bytes)
CACHE_MAX_SIZE=1073741824        # 1 GB

# Maximum entries
CACHE_MAX_ENTRIES=50000

# Default TTL (milliseconds)
CACHE_DEFAULT_TTL=259200000      # 3 days

# Eviction policy
CACHE_EVICTION_POLICY=LRU
```

**Example initialization:**
```javascript
const config = {
  maxSize: parseInt(process.env.CACHE_MAX_SIZE || '104857600'),
  maxEntries: parseInt(process.env.CACHE_MAX_ENTRIES || '10000'),
  defaultTTL: parseInt(process.env.CACHE_DEFAULT_TTL || '259200000'),
  evictionPolicy: process.env.CACHE_EVICTION_POLICY || 'LRU'
};

await cacheManagement.configure(config);
```

## Configuration Best Practices

1. **Start Conservative**: Begin with small limits and increase based on monitoring
2. **Match Environment**: Use environment-specific presets as starting point
3. **Monitor Metrics**: Track hit rate and utilization regularly
4. **Test Changes**: Make one change at a time and measure impact
5. **Document Reasoning**: Record why you chose specific values
6. **Plan Growth**: Anticipate usage growth and adjust proactively
7. **Consider Costs**: Large caches use more disk/memory; balance with benefits

## Troubleshooting Configuration

**High Memory Usage:**
- Check `maxSize` and `maxEntries`
- Reduce TTL to age out entries faster
- Switch to FIFO for faster cleanup

**Low Hit Rate:**
- Increase TTL so entries stay longer
- Increase `maxSize` and `maxEntries` to store more
- Check if entries are becoming stale quickly

**Frequent Evictions:**
- Increase `maxSize` or `maxEntries`
- Switch to LFU to keep high-value entries
- Adjust TTL strategy by task type

**Slow Retrieval:**
- Reduce `maxEntries` if cache is very large
- Use search filters (tags, limits) to reduce scan
- Consider switching to LFU for faster lookups

## Migration Between Configurations

When changing configuration in production:

1. **Backup current stats**:
   ```javascript
   const oldStats = await cacheManagement.stats();
   ```

2. **Apply new configuration**:
   ```javascript
   await cacheManagement.configure(newConfig);
   ```

3. **Monitor transition**:
   ```javascript
   const newStats = await cacheManagement.stats();
   // Compare metrics
   ```

4. **Revert if needed**:
   ```javascript
   await cacheManagement.configure(oldConfig);
   ```
