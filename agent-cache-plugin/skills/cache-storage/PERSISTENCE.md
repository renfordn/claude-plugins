# Persistent Storage Backend System

## Overview

The cache storage layer now supports pluggable backends, enabling persistence across sessions and process restarts. The system maintains backward compatibility while adding support for durable storage options.

## Available Backends

### 1. Memory Backend (Default)
- **Module**: `MemoryBackend`
- **Pros**: Fast, no dependencies, ideal for testing
- **Cons**: Data lost on process restart
- **Use Case**: Development, testing, single-session scenarios
- **Setup**: No additional configuration needed

```javascript
const storage = new PersistentCacheStorage({ 
  backendType: 'memory' 
});
await storage.initialize();
```

### 2. SQLite Backend
- **Module**: `SQLiteBackend`
- **Dependency**: `better-sqlite3` npm package
- **Pros**: Persistent, single-file DB, good for single-process deployments
- **Cons**: Not suitable for multi-process/distributed scenarios
- **Use Case**: Production single-process deployments, edge cases
- **Performance**: <1ms lookups, <50ms searches

```javascript
const storage = new PersistentCacheStorage({ 
  backendType: 'sqlite',
  backendConfig: {
    dbPath: './cache.db'  // Optional, defaults to process.cwd()/cache.db
  }
});
await storage.initialize();
```

## Backend Interface

All backends implement the `StorageBackend` abstract class:

```javascript
class StorageBackend {
  async store(entry)        // Store cache entry
  async retrieve(entryId)   // Get entry by ID
  async search(criteria)    // Find entries by criteria
  async invalidate(id|criteria) // Delete entries
  async recordMetrics(event)    // Track usage
  async stats()             // Get aggregated stats
  async configure(options)  // Update configuration
  async initialize(config)  // Setup backend
  async shutdown()          // Cleanup
  async isReady()           // Check status
}
```

## Usage Pattern

### Basic Setup
```javascript
const PersistentCacheStorage = require('./skills/cache-storage');

// Create storage with desired backend
const storage = new PersistentCacheStorage({
  backendType: 'sqlite',
  backendConfig: {
    dbPath: './var/cache.db'
  }
});

// Initialize (creates DB, tables, connects, etc)
await storage.initialize();

// Use normally - backend is transparent
const result = await storage.store({
  prompt: 'What is AI?',
  output: 'AI is...',
  metadata: { /* ... */ }
});

// Clean up
await storage.shutdown();
```

### Error Handling
```javascript
try {
  const storage = new PersistentCacheStorage({ backendType: 'sqlite' });
  await storage.initialize();
} catch (err) {
  console.error('Backend failed:', err.message);
  // Fall back to memory backend
  const fallback = new PersistentCacheStorage({ backendType: 'memory' });
  await fallback.initialize();
}
```

## Custom Backends

Implement a custom backend by extending `StorageBackend`:

```javascript
const { StorageBackend, registerBackend } = require('./backends');

class RedisBackend extends StorageBackend {
  async initialize(config) {
    this.client = redis.createClient(config);
    await this.client.connect();
  }
  
  async store(entry) {
    const id = entry.id || this._generateId();
    await this.client.set(`cache:${id}`, JSON.stringify(entry));
    return { success: true, entryId: id };
  }
  
  // ... implement other methods ...
}

registerBackend('redis', RedisBackend);
```

## Configuration

### Backend-Specific Options

**Memory Backend**:
- No configuration required

**SQLite Backend**:
```javascript
{
  dbPath: '/path/to/cache.db',    // Database file location
  // WAL mode enabled by default for concurrency
}
```

### Common Options
```javascript
{
  maxSize: 100 * 1024 * 1024,      // Max total size (100 MB)
  maxEntries: 5000,                // Max number of entries
  defaultTTL: 7 * 24 * 60 * 60 * 1000  // Default TTL (7 days)
}
```

## Performance Characteristics

| Operation | Memory | SQLite |
|-----------|--------|--------|
| Store     | <1ms   | 1-5ms  |
| Retrieve  | <1ms   | 1-3ms  |
| Search    | <50ms  | 10-100ms* |
| Stats     | <50ms  | <100ms |

*Varies with dataset size and index efficiency

## Persistence Guarantees

### Memory Backend
- **Durability**: None - data lost on process exit
- **Atomicity**: Per-entry (metadata is copied)
- **Isolation**: Single-threaded (no concurrent access)

### SQLite Backend
- **Durability**: Full ACID compliance (WAL mode)
- **Atomicity**: Transactions support
- **Isolation**: Serializable isolation level
- **Consistency**: Foreign keys and constraints enforced

## Migration Between Backends

```javascript
// Export from one backend
const oldStorage = new PersistentCacheStorage({ backendType: 'memory' });
const entries = await oldStorage.search({});

// Import to another
const newStorage = new PersistentCacheStorage({ backendType: 'sqlite' });
await newStorage.initialize();

for (const entry of entries) {
  await newStorage.store(entry);
}
```

## Future Backends (Roadmap)

- **Redis**: Distributed caching, high-performance
- **DynamoDB**: Serverless, AWS-native
- **PostgreSQL**: Enterprise database integration
- **MongoDB**: Document-based persistence

## Troubleshooting

### SQLite Lock Errors
If you see "database is locked", check:
- Multiple processes accessing same DB file (SQLite limitation)
- File system issues (NFS, SMB)
- Solution: Use WAL mode (already enabled) or switch to Redis

### Memory Leaks with Memory Backend
Metrics array grows unbounded. Consider:
- Regular archival of old metrics
- Periodic stats reset
- Implement metrics lifecycle strategy

### Slow Searches
- Check database indices (SQLite backend)
- Limit search result sets
- Consider pre-filtering client-side
- Use tag-based searches instead of full scans

## Testing

Run backend-specific tests:
```bash
npm test -- tests/storage-backends.test.js
npm test -- tests/cache-storage.test.js
```

Both backend implementations must pass all interface tests to ensure compatibility.
