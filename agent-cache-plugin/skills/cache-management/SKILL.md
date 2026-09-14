---
description: Core cache storage and retrieval system with O(1) lookups, TTL expiration, and multiple eviction policies
keywords: [cache, storage, retrieval, TTL, eviction, LRU, LFU]
version: 1.0.0
---

# Skill: Cache Management

## Overview

Cache Management is the core storage and retrieval system for the plugin. It manages the complete lifecycle of cached entries: storing agent outputs and reasoning results, retrieving them by ID or pattern, searching with filters, invalidating stale data, and monitoring cache health.

## What It Does

- **Stores** new cache entries with automatic ID generation, TTL tracking, and metadata tagging
- **Retrieves** entries by ID or query, with access timing metrics
- **Searches** cache using pattern matching, tag filtering, age limits, and result limits
- **Invalidates** entries by ID, pattern, staleness criteria, or session
- **Monitors** cache health with hit rates, size metrics, and freshness statistics
- **Configures** eviction policies (LRU, LFU, FIFO), size limits, and TTL defaults
- **Manages** automatic eviction when cache exceeds size or entry limits

## Core Operations

### Store Entry
Saves an agent output or reasoning result for future reuse. Auto-generates a unique ID if not provided. Captures metadata (agent type, task type, tags, token count, timestamp, TTL).

```javascript
const entryId = await cache.store({
  prompt: 'User question or task prompt',
  output: { result: 'cached answer or reasoning' },
  metadata: {
    agentType: 'agent-tdd',
    taskType: 'implementation',
    tags: ['phase-3', 'testing']
  },
  ttl: 24 * 60 * 60 * 1000  // 24 hours
});
```

### Retrieve Entry
Fetches a single cached entry by ID. Returns the full entry, found status, and retrieval time.

```javascript
const { entry, found, retrievalTime } = await cache.retrieve('entry-id-123');
if (found) {
  console.log(`Retrieved in ${retrievalTime}ms:`, entry.output);
}
```

### Search Cache
Queries cache with filters: pattern matching on prompt/output, tag filtering, age limits, result count limits. Useful for finding candidates before validation.

```javascript
const candidates = await cache.search({
  pattern: 'agent-tdd',           // Match prompt/tags
  tags: ['testing', 'phase-3'],   // Required tags
  maxAge: 24 * 60 * 60 * 1000,    // Last 24 hours
  limit: 10                        // Top 10 results
});
```

### Invalidate Entries
Removes entries by ID, pattern, staleness, or session. Returns count of removed entries.

```javascript
// Remove by ID
await cache.invalidate('entry-id-123');

// Remove all entries with pattern "test"
await cache.invalidate({ pattern: 'test' });

// Remove entries older than 7 days
await cache.invalidate({ olderThan: 7 * 24 * 60 * 60 * 1000 });
```

### Get Statistics
Returns cache health metrics: total entries, size in bytes, hit rate, average retrieval time, oldest/newest entry timestamps.

```javascript
const stats = await cache.stats();
console.log(`Cache: ${stats.totalEntries} entries, ${stats.cacheSize} bytes`);
console.log(`Hit rate: ${(stats.hitRate * 100).toFixed(1)}%`);
```

### Configure Settings
Updates cache behavior: size/entry limits, default TTL, eviction policy.

```javascript
await cache.configure({
  maxSize: 100 * 1024 * 1024,      // 100MB limit
  maxEntries: 10000,                // Max 10k entries
  defaultTTL: 48 * 60 * 60 * 1000,  // 48 hour default
  evictionPolicy: 'LRU'             // Least Recently Used
});
```

## Data Structure

Each cached entry contains:

- **Core fields**: id (unique identifier), prompt (user query), output (cached result)
- **Metadata**: agent type, task type, tags for searching, token count, creation timestamp, TTL
- **Statistics**: access count, last accessed time, creation time

## Storage Backends

- **In-memory** (default): Fast, session-scoped; lost on restart
- **Persistent** (optional): Redis, DynamoDB, or local filesystem; survives restarts
- **Eviction**: LRU (Least Recently Used—default), LFU (Least Frequently Used), or FIFO (First In First Out)

## Integration

Used by:
- **Orchestration**: Searches for cache candidates before deciding cache vs fresh
- **Validation**: Retrieves entries for validation checks
- **Metrics**: Tracks access patterns for analytics
- **Hooks**: Stores outputs after execution completes

## Usage Patterns

### Pattern 1: Search + Validate + Use
```javascript
// Find candidates
const candidates = await cache.search({ pattern: 'agent-tdd', limit: 5 });

// Validate each
for (const entry of candidates) {
  const validation = await validator.validate(entry, context);
  if (validation.recommendation === 'use') {
    return entry.output;  // Cache hit
  }
}

// No valid cache found
return await freshReasoning();
```

### Pattern 2: Store After Execution
```javascript
const output = await agent.execute(prompt, parameters);

await cache.store({
  prompt,
  output,
  metadata: {
    agentType: 'agent-tdd',
    taskType: parameters.taskType,
    tags: ['executed', parameters.taskType]
  },
  ttl: calculateTTL(output)
});
```

### Pattern 3: Monitor and Cleanup
```javascript
const stats = await cache.stats();
if (stats.hitRate < 0.2) {
  console.warn('Low hit rate; consider adjusting relevance threshold');
}

if (stats.totalEntries > 8000) {
  // Approaching limit; invalidate old entries
  await cache.invalidate({ olderThan: 7 * 24 * 60 * 60 * 1000 });
}
```

## Performance Characteristics

- **Store**: O(1) average; faster than retrieval
- **Retrieve**: O(1) by ID, O(n) by pattern
- **Search**: O(n) with filter operations; limited by result count
- **Invalidate**: O(k) where k = entries to remove
- **Stats**: O(n) aggregation across all entries

For large caches (>10k entries), prefer ID-based operations over searches.

## Best Practices

1. **Set appropriate TTLs**: Default to 24–48 hours; use shorter TTLs for time-sensitive outputs
2. **Tag consistently**: Use agent type and task type as base tags for better searchability
3. **Monitor metrics**: Track hit rate and cache size; adjust thresholds if trends show issues
4. **Invalidate proactively**: Remove old entries before hitting size limits
5. **Batch operations**: Use search with limits rather than loading entire cache
6. **Use persistent storage** for production: In-memory cache is lost on restart
7. **Eviction policy**: LRU works well for most cases; LFU for tracking working sets

## Configuration Tuning

| Setting | Low | Medium | High |
|---------|-----|--------|------|
| maxSize | 10MB | 100MB | 1GB+ |
| maxEntries | 1000 | 10000 | 100000+ |
| defaultTTL | 6h | 24h | 7d |
| evictionPolicy | LRU | LRU | LFU |

Start with defaults; increase limits based on observed hit rates and storage availability.
