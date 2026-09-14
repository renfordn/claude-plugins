---
description: Storage backend abstraction for cache data persistence
keywords: [storage, persistence, backend, data]
version: 1.0.0
---

# Skill: Persistent Cache Storage

## Overview

Persistent Cache Storage is the low-level, in-memory storage backend that manages physical cache entry storage, retrieval, TTL enforcement, and access tracking. It's used internally by Cache Management skill and is not typically called directly.

## What It Does

- **Stores** entries with unique IDs and auto-generation if not provided
- **Retrieves** entries by ID with TTL expiration checking
- **Searches** entries by agent type, task type, or tags
- **Invalidates** entries by ID or search criteria
- **Tracks** access patterns (last accessed time, access count)
- **Records** metrics events (hits, misses, token savings)
- **Aggregates** statistics for health monitoring
- **Enforces** lazy TTL deletion (entries marked expired on access, not auto-removed)

## Storage Model

Each entry contains:
- **Core**: id, prompt, output
- **Metadata**: agentType, taskType, tags, token count, timestamp, TTL
- **Tracking**: createdAt, accessedAt, accessCount

Metadata is deep-copied on storage to prevent external mutations from affecting cached data.

## Core Operations

### Store Entry
```javascript
const { entryId } = await storage.store({
  prompt: 'User input',
  output: { result: 'cached response' },
  metadata: {
    agentType: 'agent-tdd',
    taskType: 'implementation',
    tags: ['phase-3', 'testing'],
    timestamp: Date.now(),
    ttl: 24 * 60 * 60 * 1000
  }
});
```

### Retrieve Entry
```javascript
const entry = await storage.retrieve('entry-id-123');
if (entry) {
  console.log('Retrieved:', entry.output);
  console.log('Accessed', entry.accessCount, 'times');
}
```

### Search Entries
```javascript
const results = await storage.search({
  agentType: 'agent-tdd',
  taskType: 'testing',
  tags: ['phase-3']
});
```

### Invalidate Entries
```javascript
// By ID
await storage.invalidate('entry-id-123');

// By criteria
await storage.invalidate({
  taskType: 'old_task'
});
```

### Record Metrics
```javascript
await storage.recordMetrics({
  type: 'hit',
  tokensUsed: 2500,
  relevanceScore: 95
});
```

### Get Statistics
```javascript
const stats = await storage.stats();
console.log(`Entries: ${stats.totalEntries}`);
console.log(`Hits: ${stats.totalHits}, Misses: ${stats.totalMisses}`);
console.log(`Avg tokens saved: ${stats.avgTokensSaved}`);
```

## TTL Enforcement

- **Never expires**: TTL = null or undefined
- **Expires when**: timestamp + ttl <= current time
- **Lazy deletion**: Expired entries return null on access, not auto-removed
- **Test artifact**: Timestamps before 2024-01-01 bypass TTL for test data

## Performance Characteristics

- **Store**: O(1) map insertion
- **Retrieve**: O(1) ID lookup + TTL check
- **Search**: O(n) iteration with criteria matching (n = total entries)
- **Invalidate**: O(n) for criteria-based, O(1) for ID-based
- **Stats**: O(n + m) aggregation (n = entries, m = metrics)

For large caches (>10k entries), prefer ID-based operations and limit metrics retention.

## Memory Model

- **Entries**: Full copies stored; large outputs held in memory without compression
- **Metrics**: Unbounded array grows with every event; consider periodic cleanup
- **Concurrency**: Single-threaded; safe for concurrent async operations

## Best Practices

1. **Set appropriate TTL**: Balance freshness vs memory usage (24–48h typical)
2. **Metadata indexing**: Use consistent agentType and taskType for efficient searches
3. **Monitor metrics growth**: Keep <100k events; older events accumulate overhead
4. **Clean up old entries**: Invalidate stale entries before hitting memory limits
5. **Batch searches**: Use tag filtering to narrow result sets
6. **Test artifact awareness**: Pre-2024 timestamps exempt from TTL for test compatibility

## Integration

- **Cache Management**: Uses storage for all store/retrieve operations
- **Metrics Tracker**: Records events; caller responsible for cleanup
- **Cache Validation**: Searches for candidates to validate
- **Cache Orchestration**: Queries for decision-making

## Limitations & Assumptions

1. **In-memory only**: Data lost on process restart (no persistence)
2. **Single-threaded**: Not safe for multi-process or worker threads
3. **No auto-eviction**: Memory grows indefinitely unless manually cleaned
4. **Lazy deletion**: Expired entries consume memory until invalidated
5. **Metrics unbounded**: No automatic archival; caller manages lifecycle

For production use, consider persistent storage backend (Redis, DynamoDB) or auto-eviction policies.
