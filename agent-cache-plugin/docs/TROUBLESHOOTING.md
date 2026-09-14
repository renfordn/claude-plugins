# Troubleshooting Guide

## Common Issues and Solutions

### Cache Hits Not Working

**Symptom:** Cache always reports misses even though entries were stored.

**Check 1: Entry has Expired**
```javascript
const result = await cacheManagement.retrieve(entryId);
if (!result.found && result.reason === 'Entry expired') {
  console.log('Entry TTL exceeded');
}
```

**Solution:** Increase TTL when storing:
```javascript
await cacheManagement.store({
  prompt: '...',
  output: '...',
  metadata: { ttl: 7 * 24 * 60 * 60 * 1000 } // 7 days
});
```

**Check 2: Wrong Entry ID**
```javascript
// Verify stored ID matches retrieve call
const stored = await cacheManagement.store(entry);
console.log('Stored ID:', stored.entryId);

const retrieved = await cacheManagement.retrieve('wrong-id');
console.log('Found:', retrieved.found); // Will be false
```

**Solution:** Store the ID returned by store():
```javascript
const { entryId } = await cacheManagement.store(entry);
const result = await cacheManagement.retrieve(entryId); // Use this ID
```

**Check 3: Entry was Invalidated**
```javascript
// Check if entry was deleted
const result = await cacheManagement.retrieve(entryId);
if (!result.found && !result.reason) {
  console.log('Entry may have been invalidated');
}
```

**Solution:** Verify invalidate() calls:
```javascript
// Don't accidentally invalidate needed entries
const invalidated = await cacheManagement.invalidate('cache-*'); // Too broad!
```

### Memory Usage Growing Unbounded

**Symptom:** Cache size keeps increasing; no eviction occurring.

**Check 1: Cache Limits Not Set**
```javascript
const stats = await cacheManagement.stats();
console.log('Max Size:', stats.maxSize);
console.log('Max Entries:', /* check configuration */);
```

**Solution:** Configure proper limits:
```javascript
await cacheManagement.configure({
  maxSize: 500 * 1024 * 1024,    // 500 MB limit
  maxEntries: 50000
});
```

**Check 2: TTL Never Expiring**
```javascript
const stats = await cacheManagement.stats();
const ageSeconds = (Date.now() - stats.oldestEntry) / 1000;
console.log('Oldest entry age:', ageSeconds / 86400, 'days');

// If entries are very old, they're not expiring
```

**Solution:** Set reasonable TTL values:
```javascript
// Default is 3 days - check if this is appropriate
const config = await cacheManagement.stats();
// Adjust based on actual usage patterns

await cacheManagement.configure({
  defaultTTL: 24 * 60 * 60 * 1000 // 1 day
});
```

**Check 3: Eviction Policy Not Working**
```javascript
const statsBefore = await cacheManagement.stats();
console.log('Before eviction:', statsBefore.totalEntries);

// Force eviction
await cacheManagement.enforce({
  maxSize: statsBefore.cacheSize / 2, // Request lower limit
  policy: 'LRU'
});

const statsAfter = await cacheManagement.stats();
console.log('After eviction:', statsAfter.totalEntries);
```

**Solution:** Verify eviction policy is set:
```javascript
const result = await cacheManagement.configure({
  evictionPolicy: 'LRU' // Must be LRU, LFU, or FIFO
});

if (!result.success) {
  console.error('Configuration failed:', result.error);
}
```

### Slow Cache Retrievals

**Symptom:** Retrieve operations taking >10ms consistently.

**Check 1: Cache is Very Large**
```javascript
const stats = await cacheManagement.stats();
console.log('Total entries:', stats.totalEntries);
console.log('Avg retrieval time:', stats.avgRetrievalTime, 'ms');

if (stats.totalEntries > 50000) {
  // Large cache may slow down even direct ID lookups
}
```

**Solution:** Limit cache size:
```javascript
await cacheManagement.configure({
  maxEntries: 20000 // Reduce from 50000
});

// Or clean up old entries
await cacheManagement.enforce({
  maxEntries: 20000
});
```

**Check 2: Search Queries Too Broad**
```javascript
// Slow: scanning entire cache
const results1 = await cacheManagement.search({
  pattern: '*',
  limit: 10000
});

// Fast: specific tags
const results2 = await cacheManagement.search({
  tags: ['agent-tdd'],
  limit: 100
});
```

**Solution:** Always use tags and limits:
```javascript
const results = await cacheManagement.search({
  tags: ['agent-tdd'],        // Specific
  maxAge: 24 * 60 * 60 * 1000, // Recent only
  limit: 100                   // Limited results
});
```

### High Cache Eviction Rate

**Symptom:** `totalEvictions` equals or exceeds `totalStores` frequently.

**Check 1: Cache Limits Too Small**
```javascript
const stats = await cacheManagement.stats();

const ratio = stats.totalEvictions / stats.totalStores;
console.log('Eviction ratio:', ratio); // > 0.5 is bad

if (stats.utilizationPercent === 100) {
  // Frequently at capacity = thrashing
}
```

**Solution:** Increase limits:
```javascript
await cacheManagement.configure({
  maxSize: currentSize * 2,        // Double capacity
  maxEntries: currentEntries * 2
});
```

**Check 2: Wrong Eviction Policy**
```javascript
const stats = await cacheManagement.stats();
console.log('Top agents:', stats.topAgents);

// If valuable entries are being evicted:
// - Switch from FIFO to LRU
// - Or use LFU to keep frequently-used
```

**Solution:** Choose appropriate policy:
```javascript
// For typical workloads
await cacheManagement.configure({ evictionPolicy: 'LRU' });

// For quality-based selection
await cacheManagement.configure({ evictionPolicy: 'LFU' });
```

### Cache Stores Failing

**Symptom:** store() returns `success: false`.

**Check 1: Missing Required Fields**
```javascript
const result = await cacheManagement.store({
  // Missing 'prompt' or 'output'
});

if (!result.success) {
  console.error('Store failed:', result.error);
  // Output: "Missing required fields: prompt, output"
}
```

**Solution:** Include required fields:
```javascript
const result = await cacheManagement.store({
  prompt: 'The input query',      // Required
  output: { data: 'result' },     // Required
  metadata: { ... }
});
```

**Check 2: Invalid TTL**
```javascript
const result = await cacheManagement.store({
  prompt: '...',
  output: '...',
  metadata: { ttl: -1000 } // Negative TTL
});

if (!result.success) {
  console.error(result.error); // "TTL must be positive"
}
```

**Solution:** Use positive TTL values:
```javascript
// Milliseconds, must be > 0
const ttlMs = 24 * 60 * 60 * 1000; // 1 day
```

**Check 3: Cache Full and Can't Evict**
```javascript
// Rare but possible if:
// - maxEntries is 1 but cache is locked
// - Eviction policy can't free enough space

const result = await cacheManagement.store(entry);
if (!result.success) {
  const stats = await cacheManagement.stats();
  console.log('Cache utilization:', stats.utilizationPercent, '%');
}
```

**Solution:** Enforce limits manually:
```javascript
const enforced = await cacheManagement.enforce({
  maxSize: stats.cacheSize / 2, // Force half-size
  policy: 'LRU'
});
console.log('Evicted:', enforced.evictedCount);

// Then retry store
const result = await cacheManagement.store(entry);
```

### Search Returns No Results

**Symptom:** search() always returns empty array even when entries exist.

**Check 1: Using Wrong Query Parameter**
```javascript
// Wrong: agentType is not a query parameter
const results = await cacheManagement.search({
  agentType: 'agent-tdd'  // This doesn't work
});

// Correct: agentType becomes a tag during store
const results = await cacheManagement.search({
  tags: ['agent-tdd']  // Use tags parameter
});
```

**Check 2: Entries Expired Before Search**
```javascript
const results = await cacheManagement.search({
  tags: ['agent-tdd']
});

// Check stats for age of entries
const stats = await cacheManagement.stats();
const ageSeconds = (Date.now() - stats.newestEntry) / 1000;
console.log('Newest entry age:', ageSeconds, 'seconds');

if (results.length === 0 && ageSeconds > 0) {
  // Entries exist but are expired
}
```

**Solution:** Check maxAge or adjust TTL:
```javascript
// Increase TTL when storing
metadata: { ttl: 7 * 24 * 60 * 60 * 1000 }

// Or search recently-stored entries
const results = await cacheManagement.search({
  tags: ['agent-tdd'],
  maxAge: 1 * 60 * 60 * 1000  // Within 1 hour
});
```

**Check 3: Case Sensitivity in Tags**
```javascript
// Stored with tag: 'Agent-TDD'
await cacheManagement.store({
  metadata: { agentType: 'Agent-TDD' }
});

// Searching with different case
const results = await cacheManagement.search({
  tags: ['agent-tdd']  // Lowercase - won't match!
});
```

**Solution:** Normalize tags:
```javascript
// Store with lowercase
metadata: { agentType: 'agent-tdd' }

// Search with lowercase
tags: ['agent-tdd']

// Or normalize during search
tags: [userInput.toLowerCase()]
```

### Cache Not Persisting (In-Memory Only)

**Symptom:** Cache is lost when process restarts.

**Note:** The default implementation is in-memory only. This is intentional.

**Solution for Persistence:**
```javascript
// Current: In-memory cache
const result = await cacheManagement.retrieve(id);

// For persistence, implement:
// 1. Periodic snapshot to disk
async function snapshotCache() {
  const stats = await cacheManagement.stats();
  // Save stats to file
  fs.writeFileSync('cache-snapshot.json', JSON.stringify(stats));
}

// 2. Or connect external storage
// - Database for durable cache
// - Redis for distributed cache
// - See docs/ARCHITECTURE.md for storage options
```

### High CPU Usage During Search

**Symptom:** Search operations consuming excessive CPU.

**Check 1: Searching Without Limits**
```javascript
// Very expensive: scanning all entries
const results = await cacheManagement.search({
  pattern: '*',  // Match everything
  // No limit specified - defaults to 100
});

// Console: "CPU spike while searching 100k+ entries"
```

**Solution:** Always limit results:
```javascript
const results = await cacheManagement.search({
  tags: ['agent-tdd'],
  maxAge: 24 * 60 * 60 * 1000,
  limit: 50  // Keep results small
});
```

**Check 2: Complex Pattern Matching**
```javascript
// Slow: regex on large dataset
const results = await cacheManagement.search({
  pattern: '.*complex.*regex.*pattern.*'
});
```

**Solution:** Use simple patterns or tags:
```javascript
// Better: tag-based search
const results = await cacheManagement.search({
  tags: ['high-priority']  // Direct lookup
});
```

## Performance Diagnostic Checklist

Use this checklist when experiencing performance issues:

- [ ] Check `cacheManagement.stats()` for health metrics
- [ ] Verify `hitRate` is > 30% (< 20% suggests misconfiguration)
- [ ] Verify `utilizationPercent` is 50-90% (not 100% or near 0%)
- [ ] Check `avgRetrievalTime` is < 5ms (> 10ms suggests large cache)
- [ ] Verify entries are stored with correct TTL
- [ ] Check search queries use tags and limits
- [ ] Verify evictionPolicy matches workload (LRU for most cases)
- [ ] Monitor `totalEvictions` vs `totalStores` ratio (< 50% is healthy)
- [ ] Check for circular dependencies in cache usage

## Getting More Help

**Enable Debug Logging:**
```javascript
// Add this during cache operations
const result = await cacheManagement.store(entry);
console.log('Store result:', JSON.stringify(result, null, 2));

const stats = await cacheManagement.stats();
console.log('Cache stats:', JSON.stringify(stats, null, 2));
```

**Collect Diagnostics:**
```javascript
async function getCacheDiagnostics() {
  const stats = await cacheManagement.stats();
  
  return {
    totalEntries: stats.totalEntries,
    hitRate: (stats.hitRate * 100).toFixed(1) + '%',
    utilizationPercent: stats.utilizationPercent,
    topAgents: stats.topAgents,
    avgRetrievalTime: stats.avgRetrievalTime + 'ms',
    totalEvictions: stats.totalEvictions,
    oldestEntryAge: Math.round((Date.now() - stats.oldestEntry) / 1000 / 60) + ' min'
  };
}

const diag = await getCacheDiagnostics();
console.log(JSON.stringify(diag, null, 2));
```

## Known Limitations

1. **In-Memory Only**: Cache is lost on process restart (by design)
2. **Single Process**: Not shared across multiple processes (use external store for that)
3. **Search Performance**: Large caches (>50k entries) may have slower searches
4. **No Persistence**: No built-in backup or recovery mechanism
5. **Synchronous Indices**: Index updates are not atomic (rare race conditions possible)

For production deployments requiring persistence, consider implementing external storage as described in the Architecture Guide.
