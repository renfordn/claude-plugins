# Redis Storage Backend

## Overview

The Redis backend enables distributed cache sharing across multiple processes and servers. It provides:

- **Cross-process caching**: Share cache entries between independent processes
- **Cross-server caching**: Deploy cache across microservices or multiple instances
- **Real-time invalidation**: Pub/Sub for instant cache updates across instances
- **High performance**: Sub-millisecond reads with persistent optional snapshots
- **Flexible deployment**: Works with Redis Cloud, self-hosted, or containerized Redis

**Best For**:
- Distributed systems and microservices
- High-concurrency scenarios (1000s of requests/sec)
- Multi-tenant SaaS applications
- Systems requiring cache persistence

**Performance**: <5ms average latency (network dependent)

## Installation

### 1. Install Redis Client

```bash
npm install redis
```

### 2. Set Up Redis Server

**Option A: Docker (Recommended for Development)**
```bash
docker run -d -p 6379:6379 redis:latest
```

**Option B: Local Installation**
```bash
# macOS
brew install redis
redis-server

# Ubuntu/Debian
sudo apt-get install redis-server
redis-server

# Windows (via WSL or Docker)
```

**Option C: Redis Cloud (Managed Service)**
- Sign up at https://redis.com/try-free/
- Create a database and get connection details

## Configuration

### Basic Setup

```javascript
const CacheManager = require('./skills/cache-storage');

const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'localhost',
    port: 6379
  }
});

await cache.initialize();
```

### With Authentication

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis.example.com',
    port: 6380,
    password: 'your-secure-password',
    db: 0  // Select database 0-15
  }
});
```

### Production Configuration

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: process.env.REDIS_HOST,
    port: parseInt(process.env.REDIS_PORT),
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_DB) || 0,
    keyPrefix: process.env.CACHE_KEY_PREFIX || 'cache:',
    maxRetries: 3,
    retryDelay: 1000,
    connectionTimeout: 5000,
    enablePubSub: true,
    metricsInterval: 60000
  }
});
```

### Environment Variables

```bash
# Basic connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=optional-password

# For Redis Cloud (use full connection URL if needed)
REDIS_URL=redis://user:password@host:port
REDIS_DB=0

# Cache configuration
CACHE_KEY_PREFIX=cache:
CACHE_BACKEND=redis
```

## Usage Examples

### Basic Caching

```javascript
const CacheManager = require('./skills/cache-storage');
const cache = new CacheManager({
  backend: 'redis',
  config: { host: 'localhost' }
});

await cache.initialize();

// Store entry
const entry = {
  prompt: 'What is machine learning?',
  output: { answer: '...' },
  ttl: 3600000  // 1 hour
};

const { entryId } = await cache.store(entry);

// Retrieve entry
const cached = await cache.retrieve(entryId);

// Search entries
const results = await cache.search({
  tags: ['ml', 'ai'],
  agentType: 'analyzer'
});

// Invalidate entries
await cache.invalidate(entryId);  // By ID
await cache.invalidate({ agentType: 'analyzer' });  // By criteria
```

### Cross-Service Sharing

With Redis, multiple services can share the same cache:

```javascript
// Service A
const cacheA = new CacheManager({
  backend: 'redis',
  config: { host: 'shared-redis.internal', keyPrefix: 'service-a:' }
});

// Service B
const cacheB = new CacheManager({
  backend: 'redis',
  config: { host: 'shared-redis.internal', keyPrefix: 'service-b:' }
});

// Entries stored by Service A are accessible to Service B
const results = await cacheB.retrieve(idStoredByA);
```

### Real-time Invalidation

When Pub/Sub is enabled (default), cache invalidations propagate instantly:

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'localhost',
    enablePubSub: true  // Enable Pub/Sub invalidation
  }
});

await cache.initialize();

// When any instance invalidates an entry, all instances are notified
await cache.invalidate(entryId);  // Broadcast to all instances
```

### Monitoring Cache Health

```javascript
const stats = await cache.stats();

console.log({
  totalEntries: stats.totalEntries,
  metrics: stats.metrics,
  connected: stats.connected,
  redisInfo: stats.redisInfo
});

// Output:
// {
//   totalEntries: 1250,
//   metrics: {
//     reads: 45000,
//     writes: 2500,
//     deletes: 200,
//     errors: 5,
//     hitRate: 0.95
//   },
//   connected: true,
//   redisInfo: "# Server\nredis_version:7.0.0\n..."
// }
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | `localhost` | Redis server hostname/IP |
| `port` | number | `6379` | Redis server port |
| `password` | string | undefined | Redis auth password |
| `db` | number | `0` | Redis database number (0-15) |
| `keyPrefix` | string | `cache:` | Prefix for all keys |
| `maxRetries` | number | `3` | Max connection retry attempts |
| `retryDelay` | number | `1000` | Initial retry delay (ms), exponential backoff |
| `connectionTimeout` | number | `5000` | Connection timeout (ms) |
| `enablePubSub` | boolean | `true` | Enable Pub/Sub for invalidation |
| `metricsInterval` | number | `60000` | Metrics recording interval (ms) |

## Deployment Scenarios

### Scenario 1: Single-Server Web App

```
Client Requests
      ↓
  Web Server (Node.js)
      ↓
   Redis Cache
      ↓
  Database
```

**Configuration**:
```javascript
new CacheManager({
  backend: 'redis',
  config: { host: 'localhost' }
});
```

### Scenario 2: Load-Balanced Microservices

```
Load Balancer
    ↙  ↓  ↘
  API1  API2  API3
    ↘  ↓  ↙
  Shared Redis
    ↓
  Database
```

**Configuration**:
```javascript
new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis-cluster.internal',
    enablePubSub: true  // Cross-instance invalidation
  }
});
```

### Scenario 3: Multi-Tenant SaaS

```
Client A   Client B   Client C
    ↓          ↓          ↓
  Tenant A   Tenant B   Tenant C
    ↘  ↓  ↙
  Shared Redis (with namespace isolation)
```

**Configuration**:
```javascript
new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis.cloud.internal',
    keyPrefix: `tenant-${tenantId}:`,  // Namespace by tenant
    password: process.env.REDIS_PASSWORD
  }
});
```

## Performance Tuning

### For High Throughput (1000+ req/sec)

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis-optimized.internal',
    connectionTimeout: 2000,
    maxRetries: 1,  // Fail fast
    enablePubSub: false  // Reduce overhead if not needed
  }
});
```

### For Reliability (Critical Operations)

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis-reliable.internal',
    maxRetries: 5,
    retryDelay: 500,
    connectionTimeout: 10000,
    enablePubSub: true  // Enable all features
  }
});
```

## Monitoring & Observability

### Redis INFO Command

```javascript
const stats = await cache.stats();
const redisInfo = stats.redisInfo;  // Raw Redis info output

// Parse specific metrics
const lines = redisInfo.split('\n');
const memory = lines.find(l => l.includes('used_memory_human'));
console.log('Redis Memory:', memory);
```

### Metrics Tracking

```javascript
const stats = await cache.stats();
const metrics = stats.metrics;

console.log({
  totalReads: metrics.reads,
  totalWrites: metrics.writes,
  totalDeletes: metrics.deletes,
  errorCount: metrics.errors,
  readWriteRatio: metrics.reads / metrics.writes
});
```

### Health Check

```javascript
async function healthCheck() {
  try {
    const stats = await cache.stats();
    return {
      healthy: stats.connected && stats.totalEntries >= 0,
      entries: stats.totalEntries,
      lastCheck: new Date()
    };
  } catch (err) {
    return { healthy: false, error: err.message };
  }
}
```

## Troubleshooting

### Issue: Connection Refused

**Cause**: Redis server not running  
**Solution**:
```bash
# Start Redis
redis-server

# Or check if running on different port
redis-cli ping
```

### Issue: Authentication Failed

**Cause**: Wrong password or no auth required  
**Solution**:
```bash
# Test connection with redis-cli
redis-cli -h localhost -p 6379 -a yourpassword ping

# Update config with correct password
```

### Issue: High Memory Usage

**Cause**: Too many entries or large values  
**Solution**:
```javascript
// Monitor memory
const stats = await cache.stats();
console.log(stats.redisInfo);

// Implement aggressive eviction
redis.configSet('maxmemory-policy', 'allkeys-lru');

// Or increase max memory
redis.configSet('maxmemory', '2gb');
```

### Issue: Slow Performance

**Cause**: Network latency or slow Redis  
**Solution**:
```javascript
// 1. Run Redis locally or in same datacenter
// 2. Reduce connection overhead
config: {
  connectionTimeout: 2000,
  maxRetries: 1
}

// 3. Use pipelining for batch operations
```

## Comparison with Other Backends

| Feature | Memory | SQLite | Redis |
|---------|--------|--------|-------|
| Speed | ⚡⚡⚡ | ⚡⚡ | ⚡⚡⚡ |
| Persistence | ✗ | ✓ | ✓* |
| Multi-process | ✗ | ✓ | ✓ |
| Multi-server | ✗ | ✗ | ✓ |
| Real-time sync | ✗ | ✗ | ✓ |
| Memory usage | High | Low | Medium |
| Setup | None | File | Server |
| Cost | Free | Free | Free/Paid |

*Redis can be configured with persistence (RDB, AOF)

## Migration from Other Backends

### From Memory to Redis

```javascript
// 1. Create Redis backend
const redisCache = new CacheManager({
  backend: 'redis',
  config: { host: 'localhost' }
});

// 2. Migrate existing entries
for (const entry of memoryCache.entries) {
  await redisCache.store(entry);
}

// 3. Switch to Redis backend
cacheManager = redisCache;
```

### From SQLite to Redis

```javascript
// Same migration pattern, but source is SQLite backend
```

## Best Practices

1. **Always use key prefixes** to avoid collisions in shared Redis
2. **Set appropriate TTLs** to prevent unlimited growth
3. **Monitor memory** and set eviction policies
4. **Enable Pub/Sub** for multi-instance deployments
5. **Use connection pooling** for high-concurrency apps
6. **Set up Redis persistence** for critical caches
7. **Test failover behavior** before production deployment
8. **Implement health checks** in application startup

## Advanced Topics

### Redis Clustering

For very high concurrency or large datasets:

```javascript
const cache = new CacheManager({
  backend: 'redis',
  config: {
    host: 'redis-cluster-node-1',
    port: 6379,
    // Redis cluster connection (requires cluster support in client)
  }
});
```

### Redis Sentinel (High Availability)

For automatic failover:

```bash
# Set up Redis Sentinel for HA
# https://redis.io/topics/sentinel
```

### Cache Warming

Pre-populate cache on startup:

```javascript
async function warmCache() {
  const frequentQueries = await getFrequentQueries();
  for (const query of frequentQueries) {
    const result = await computeExpensiveQuery(query);
    await cache.store({
      prompt: query,
      output: result,
      ttl: 86400000  // 24 hours
    });
  }
}
```

## See Also

- [PERSISTENCE.md](./PERSISTENCE.md) - All storage backend options
- [API.md](../API.md) - Full cache API reference
- [Redis Documentation](https://redis.io/documentation)
- [Redis Client JS](https://github.com/redis/node-redis)
