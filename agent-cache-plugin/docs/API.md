# Cache Management API Documentation

## Overview

The agent-cache-plugin provides a comprehensive cache management API for storing, retrieving, searching, and managing cached agent outputs. The API is built around a singleton pattern, making it easy to access the cache from anywhere in your application.

## Core API Methods

### store(entry)

Stores a cache entry and returns an ID for later retrieval.

**Signature:**
```javascript
async store(entry: CacheEntry): Promise<StoreResult>
```

**Parameters:**
- `entry` (object): The entry to store
  - `prompt` (string, required): The input prompt/query that was cached
  - `output` (object, required): The output/response to cache (can be any serializable object)
  - `id` (string, optional): Custom ID for the entry. If not provided, an auto-generated ID is assigned
  - `metadata` (object, optional):
    - `agentType` (string): Name of the agent that produced this result
    - `taskType` (string): Type of task (e.g., 'research', 'refactor', 'analysis')
    - `ttl` (number): Time-to-live in milliseconds. Defaults to 3 days
    - `tags` (array): Custom tags for searching (agentType and taskType are auto-added)
    - `parameters` (object): Original parameters passed to the agent
    - `tokenCount` (number): Approximate tokens used

**Returns:**
```javascript
{
  success: true,
  entryId: "cache-1234567890-xyz123",
  size: 4096,
  stats: { ... }
}
```

**Example:**
```javascript
const result = await cacheManagement.store({
  prompt: 'Refactor this function...',
  output: { refactoredCode: '...', suggestions: [...] },
  metadata: {
    agentType: 'agent-refactor',
    taskType: 'code-refactor',
    ttl: 24 * 60 * 60 * 1000,
    parameters: { language: 'javascript', style: 'modern' }
  }
});

console.log(result.entryId); // Use to retrieve later
```

### retrieve(entryId)

Retrieves a cached entry by ID.

**Signature:**
```javascript
async retrieve(entryId: string): Promise<RetrieveResult>
```

**Parameters:**
- `entryId` (string): The ID of the entry to retrieve (returned by store())

**Returns:**
```javascript
// On successful retrieval:
{
  entry: {
    id: "cache-1234567890-xyz123",
    prompt: "...",
    output: { ... },
    metadata: { ... },
    stats: {
      hits: 5,
      createdAt: 1234567890000,
      lastAccessed: 1234567890000
    }
  },
  found: true,
  cached: true,
  retrievalTime: 2
}

// On miss or expiration:
{
  entry: null,
  found: false,
  cached: false,
  retrievalTime: 1,
  reason: "Entry expired" | undefined
}
```

**Example:**
```javascript
const result = await cacheManagement.retrieve('cache-1234567890-xyz123');

if (result.found) {
  console.log('Cache hit:', result.entry.output);
  console.log('Reused in', result.retrievalTime, 'ms');
} else {
  console.log('Cache miss:', result.reason || 'entry not found');
}
```

### search(query)

Searches for cache entries using tags, patterns, and age filters.

**Signature:**
```javascript
async search(query: SearchQuery): Promise<SearchResult[]>
```

**Parameters:**
- `query` (object, optional):
  - `tags` (array): Search for entries with these tags (agentType and taskType are tags)
  - `pattern` (string): Substring pattern to match in prompt/agentType (use '*' for all)
  - `maxAge` (number): Maximum age in milliseconds (defaults to no limit)
  - `limit` (number): Maximum results to return (defaults to 100)

**Returns:**
```javascript
[
  {
    id: "cache-1234567890-xyz123",
    prompt: "...",
    metadata: { agentType: "...", ... },
    stats: { hits: 5, ... },
    ageSec: 3600
  },
  ...
]
```

**Example:**
```javascript
// Find recent agent-tdd entries
const results = await cacheManagement.search({
  tags: ['agent-tdd'],
  maxAge: 24 * 60 * 60 * 1000, // Within 24 hours
  limit: 10
});

console.log(`Found ${results.length} recent entries`);
results.forEach(entry => {
  console.log(`${entry.id}: ${entry.ageSec}s old, ${entry.stats.hits} hits`);
});
```

### invalidate(idOrPattern)

Removes cache entries by ID or pattern.

**Signature:**
```javascript
async invalidate(idOrPattern: string | object): Promise<InvalidateResult>
```

**Parameters:**
- `idOrPattern` (string or object):
  - If string: exact ID or wildcard pattern (e.g., 'cache-*')
  - If object: same structure as search query (future extension)

**Returns:**
```javascript
{
  count: 3,
  details: ["Invalidated entry: cache-...", ...]
}
```

**Example:**
```javascript
// Remove a specific entry
const result = await cacheManagement.invalidate('cache-1234567890-xyz123');
console.log(`Removed ${result.count} entries`);

// Remove all agent-refactor entries (if using pattern)
const removed = await cacheManagement.invalidate('cache-agent-refactor-*');
```

### stats()

Returns cache statistics and metadata.

**Signature:**
```javascript
async stats(): Promise<CacheStats>
```

**Returns:**
```javascript
{
  totalEntries: 156,
  cacheSize: 52428800,
  maxSize: 104857600,
  utilizationPercent: 50,
  hitRate: 0.85,
  totalHits: 340,
  totalMisses: 60,
  totalStores: 156,
  totalEvictions: 12,
  avgRetrievalTime: 2.5,
  oldestEntry: 1234567890000,
  newestEntry: 1234567999000,
  topAgents: [
    { agent: 'agent-tdd', count: 45 },
    { agent: 'agent-refactor', count: 38 },
    ...
  ]
}
```

**Example:**
```javascript
const stats = await cacheManagement.stats();

console.log(`Cache Hit Rate: ${(stats.hitRate * 100).toFixed(1)}%`);
console.log(`Usage: ${stats.utilizationPercent}%`);
console.log(`Most active: ${stats.topAgents[0].agent} (${stats.topAgents[0].count} hits)`);
```

### configure(options)

Updates cache configuration settings.

**Signature:**
```javascript
async configure(options: ConfigOptions): Promise<ConfigResult>
```

**Parameters:**
- `options` (object):
  - `maxSize` (number): Maximum cache size in bytes (default: 100 MB)
  - `maxEntries` (number): Maximum number of entries (default: 10000)
  - `defaultTTL` (number): Default time-to-live in milliseconds (default: 3 days)
  - `evictionPolicy` (string): 'LRU', 'LFU', or 'FIFO' (default: 'LRU')

**Returns:**
```javascript
{
  success: true,
  applied: { maxSize: 500000000, ... },
  current: {
    maxSize: 500000000,
    maxEntries: 50000,
    defaultTTL: 259200000,
    evictionPolicy: 'LRU'
  }
}
```

**Example:**
```javascript
const result = await cacheManagement.configure({
  maxSize: 500 * 1024 * 1024, // 500 MB
  maxEntries: 50000,
  evictionPolicy: 'LFU'
});

if (result.success) {
  console.log('Cache configured:', result.applied);
}
```

## Advanced Usage

### Singleton vs. Direct Instance

The plugin exports both a singleton pattern and direct class access:

```javascript
// Singleton (recommended for plugins)
const result = await cacheManagement.store(entry);

// Direct instantiation (for testing or isolated instances)
const CacheManager = cacheManagement.CacheManager;
const manager = new CacheManager({ maxSize: 50 * 1024 * 1024 });
const result = await manager.store(entry);
```

### TTL and Expiration

Entries automatically expire based on their TTL:

```javascript
// Short-lived results (high-risk tasks)
metadata: { ttl: 4 * 60 * 60 * 1000 } // 4 hours

// Medium-lived (routine work)
metadata: { ttl: 3 * 24 * 60 * 60 * 1000 } // 3 days (default)

// Long-lived (stable outputs)
metadata: { ttl: 7 * 24 * 60 * 60 * 1000 } // 7 days
```

Expired entries are automatically cleaned up during retrieve() or enforce() operations.

### Eviction Policies

When cache limits are exceeded, entries are evicted based on the configured policy:

- **LRU (Least Recently Used)**: Removes entries accessed longest ago (best for typical caching)
- **LFU (Least Frequently Used)**: Removes entries with fewest accesses (good for quality-based caching)
- **FIFO (First In First Out)**: Removes oldest entries by creation time (simple, predictable)

### Performance Optimization

Use tags and search filters to optimize performance:

```javascript
// ✓ Good: Search with specific tags
const results = await cacheManagement.search({
  tags: ['agent-tdd', 'high-priority'],
  limit: 10
});

// ✗ Avoid: Loading all entries and filtering in application
const all = await cacheManagement.search({ limit: 10000 }); // CPU/memory intensive
```

## Error Handling

All methods return result objects with consistent error handling:

```javascript
const result = await cacheManagement.store(entry);

if (result.success === false) {
  console.error('Store failed:', result.error);
  // Handle error: missing fields, TTL validation, etc.
}

const retrieved = await cacheManagement.retrieve(entryId);
if (!retrieved.found) {
  console.log('Entry not found or expired:', retrieved.reason);
}
```

## Type Definitions (TypeScript)

```typescript
interface CacheEntry {
  prompt: string;
  output: any;
  id?: string;
  metadata?: {
    agentType?: string;
    taskType?: string;
    ttl?: number;
    tags?: string[];
    parameters?: Record<string, any>;
    tokenCount?: number;
  };
}

interface RetrieveResult {
  entry: CacheEntry | null;
  found: boolean;
  cached?: boolean;
  retrievalTime: number;
  reason?: string;
  error?: string;
}

interface CacheStats {
  totalEntries: number;
  cacheSize: number;
  maxSize: number;
  utilizationPercent: number;
  hitRate: number;
  totalHits: number;
  totalMisses: number;
  totalStores: number;
  totalEvictions: number;
  avgRetrievalTime: number;
  oldestEntry: number | null;
  newestEntry: number | null;
  topAgents: Array<{ agent: string; count: number }>;
}
```

## Integration with Hooks

The cache is typically populated via the `post-agent-completion` hook:

```javascript
// Hook automatically stores results
// Metadata is derived from agent/task context
await cacheManagement.store({
  prompt: agentContext.prompt,
  output: agentOutput,
  metadata: {
    agentType: agentContext.type,
    taskType: agentContext.taskType,
    ttl: calculateTTL(riskTier),
    parameters: sanitizeParameters(agentContext.parameters)
  }
});
```

And checked via the `pre-execution-check` hook:

```javascript
// Hook checks cache before agent execution
const cached = await cacheManagement.retrieve(cacheId);
if (cached.found && isRelevant(cached.entry, currentTask)) {
  return cached.entry.output; // Reuse cached result
}
```

## Monitoring and Maintenance

Regularly check cache stats and configure limits based on usage:

```javascript
const stats = await cacheManagement.stats();

if (stats.hitRate > 0.8) {
  console.log('Cache is performing well');
} else if (stats.hitRate < 0.3) {
  console.log('Consider adjusting TTL or relevance scoring');
}

if (stats.utilizationPercent > 90) {
  console.log('Cache is nearly full, evictions will increase');
  // Consider increasing maxSize or reducing TTL
}
```
