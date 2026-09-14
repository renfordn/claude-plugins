# Fallback Storage Backend

## Overview

Automatic fallback mechanism that transparently switches from a primary storage backend (Redis) to a secondary backend (SQLite) when the primary becomes unavailable. Ensures cache operations continue even during primary backend failures.

**Key Features**:
- 🔄 Automatic failover to secondary backend
- 📊 Separate metrics for each backend
- 💚 Health monitoring and recovery detection
- 🔗 Seamless switching without data loss
- 📈 Failover and recovery tracking
- 🔌 Pluggable backend architecture

## Installation

No additional setup required - FallbackBackend is included with cache-storage.

```bash
# Already installed with cache-storage
npm install @claude/agent-cache-plugin
```

## Quick Start

```javascript
const CacheManager = require('./skills/cache-storage');

// Auto-fallback from Redis to SQLite
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',
    fallbackBackend: 'sqlite',
    primaryConfig: {
      host: 'localhost',
      port: 6379
    },
    fallbackConfig: {
      db: './cache-fallback.db'
    },
    autoRecovery: true
  }
});

await cache.initialize();

// Works even if Redis is down
const { entryId } = await cache.store({
  prompt: 'Analyze this...',
  output: { result: '...' }
});

// Automatically uses SQLite if Redis unavailable
const entry = await cache.retrieve(entryId);
```

## Configuration

### Basic Setup

```javascript
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',
    fallbackBackend: 'sqlite'
  }
});
```

### Advanced Configuration

```javascript
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',
    fallbackBackend: 'sqlite',
    
    // Primary backend config (Redis)
    primaryConfig: {
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT) || 6379,
      password: process.env.REDIS_PASSWORD,
      maxRetries: 3
    },
    
    // Fallback backend config (SQLite)
    fallbackConfig: {
      db: process.env.CACHE_DB || './cache.db'
    },
    
    // Failover behavior
    healthCheckInterval: 30000,        // Check every 30 seconds
    maxConsecutiveErrors: 3,           // Fail over after 3 errors
    autoRecovery: true                 // Auto-switch back when primary recovers
  }
});
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `primaryBackend` | string | `'redis'` | Primary backend type |
| `fallbackBackend` | string | `'sqlite'` | Secondary backend type |
| `primaryConfig` | object | `{}` | Primary backend configuration |
| `fallbackConfig` | object | `{}` | Fallback backend configuration |
| `healthCheckInterval` | number | `30000` | Health check interval (ms) |
| `maxConsecutiveErrors` | number | `3` | Errors before failover |
| `autoRecovery` | boolean | `true` | Auto-recover when primary healthy |

## How It Works

### Operation Flow

1. **Normal Operation**: All operations use primary backend
2. **Error Detection**: Track consecutive errors
3. **Failover**: After `maxConsecutiveErrors`, switch to fallback
4. **Health Check**: Periodically test primary backend
5. **Recovery**: Switch back when primary becomes healthy

### Failover Sequence

```
Store entry
  ↓
Try primary backend (Redis)
  ↓
Success → Track metric, reset error counter → Return result
  ↓
Failure → Increment error counter
  ↓
Errors < maxConsecutiveErrors → Return error
  ↓
Errors >= maxConsecutiveErrors → Switch to fallback backend
  ↓
Try fallback backend (SQLite)
  ↓
Success → Return result
  ↓
Failure → Return error
```

### Recovery Sequence

Health check runs every `healthCheckInterval`:

```
Health check running...
  ↓
Primary healthy? No → Stay on fallback
  ↓
Primary healthy? Yes
  ↓
Switch to primary
  ↓
Increment recovery count
  ↓
Reset error counter
```

## Usage Examples

### Store During Outage

```javascript
// Redis is down, but cache still works
const result = await cache.store({
  prompt: 'Analyze customer data',
  output: { insights: [...] }
});

console.log('Stored via:', result.backend); // 'sqlite'
```

### Monitor Failover Status

```javascript
const stats = await cache.stats();

console.log({
  activeBackend: stats.activeBackend,        // 'fallback' if Redis down
  primaryHealthy: stats.primaryHealthy,      // false if down
  fallbackHealthy: stats.fallbackHealthy,    // true if up
  failoverCount: stats.failoverCount,        // Times failed over
  recoveryCount: stats.recoveryCount         // Times recovered
});
```

### Manual Backend Switch

```javascript
const storage = cache.storageBackend;

// Force use of fallback
storage.switchBackend('fallback');

// Switch back to primary
storage.switchBackend('primary');

// Check current status
const status = storage.getStatus();
console.log('Active backend:', status.activeBackend);
```

### Track Operation by Backend

```javascript
const stats = await cache.stats();

console.log({
  primaryReads: stats.metrics.primaryReads,
  primaryWrites: stats.metrics.primaryWrites,
  fallbackReads: stats.metrics.fallbackReads,
  fallbackWrites: stats.metrics.fallbackWrites
});
```

## Deployment Scenarios

### Scenario 1: High Availability

```
┌─────────────────┐
│   Application   │
└────────┬────────┘
         │
    ┌────┴────┐
    │Fallback │
    │ Backend │
    └────┬────┘
         │
    ┌────┴──────┐
    │            │
  ┌─┴──┐      ┌─┴──┐
  │Redis│(fail)│SQLite│(active)
  └──┬──┘      └──────┘
     │
  (Recovering...)
```

When Redis fails, automatically uses SQLite. Once Redis recovers, switches back.

### Scenario 2: Cost Optimization

```javascript
// Use cheaper SQLite by default, fallback to fast Redis
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'sqlite',  // Fast local storage
    fallbackBackend: 'redis',  // Cloud cache fallback
    healthCheckInterval: 60000,
    autoRecovery: true
  }
});
```

### Scenario 3: Gradual Rollout

```javascript
// Start with Redis → SQLite fallback
// Gradually shift to SQLite as primary
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',
    fallbackBackend: 'sqlite',
    // In a few versions, switch to:
    // primaryBackend: 'sqlite',
    // fallbackBackend: 'redis'
  }
});
```

## Monitoring & Observability

### Health Status

```javascript
async function checkCacheHealth() {
  const stats = await cache.stats();
  
  return {
    healthy: stats.primaryHealthy || stats.fallbackHealthy,
    primary: stats.primaryHealthy ? '✓' : '✗',
    fallback: stats.fallbackHealthy ? '✓' : '✗',
    activeBackend: stats.activeBackend,
    failovers: stats.metrics.failovers,
    recoveries: stats.metrics.recoveries
  };
}
```

### Metrics Dashboard

```javascript
// Every minute, log fallback metrics
setInterval(async () => {
  const stats = await cache.stats();
  console.log(`[Cache] Primary: ${stats.primaryHealthy ? '✓' : '✗'} | ` +
              `Fallback: ${stats.fallbackHealthy ? '✓' : '✗'} | ` +
              `Failovers: ${stats.metrics.failovers}`);
}, 60000);
```

### Alert on Repeated Failures

```javascript
const stats = await cache.stats();

if (stats.metrics.failovers > 10 && !stats.primaryHealthy) {
  // Primary backend failing repeatedly
  sendAlert('Redis connection issues detected');
  // Could trigger: restart Redis, page on-call, etc.
}
```

## Troubleshooting

### Primary Backend Not Recovering

**Symptom**: Always using fallback even after Redis restarts

**Solution**:
```javascript
// Check health check is running
const storage = cache.storageBackend;
if (storage.healthCheckTimer) {
  console.log('Health check active');
} else {
  console.warn('Health check not running - restart cache');
}
```

### High Fallback Usage

**Symptom**: Most operations using SQLite

**Check**:
```javascript
const stats = await cache.stats();
console.log('Primary healthy:', stats.primaryHealthy);
console.log('Primary errors:', stats.metrics.errors);

// If primary not healthy, check Redis
redis-cli ping  // Should return PONG
```

### Slow Performance on Fallback

**Cause**: SQLite is slower than Redis for high concurrency

**Solution**:
```javascript
// Reduce primary error threshold for faster fallback
config: {
  maxConsecutiveErrors: 1  // Fail over immediately
}

// Or increase backend pool size
config: {
  primaryConfig: {
    maxRetries: 5  // Retry more before giving up
  }
}
```

## Performance Impact

### Operation Overhead
- **Health check**: <5ms every 30 seconds
- **Failover decision**: <1ms per operation
- **Error tracking**: <0.1ms per operation

### Latency During Failover
- First error: Redis latency (e.g., 5ms timeout)
- Errors 1-2: Fast fail (~1ms each)
- Error 3: Switch to SQLite, first op slower (~50ms)
- Subsequent ops: SQLite speed (~20-50ms)

### Storage Overhead
- Health check entries: ~200 bytes each (auto-deleted)
- Failover metrics: <1KB per cache instance
- No duplication between backends

## Migration Guide

### From Redis Only to Fallback

```javascript
// Before: Redis only
const cache = new CacheManager({
  backendType: 'redis'
});

// After: Redis with SQLite fallback
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',
    fallbackBackend: 'sqlite'
  }
});

// Data persists in Redis
// SQLite acts as emergency backup
```

### From SQLite Only to Fallback

```javascript
// Before: SQLite only
const cache = new CacheManager({
  backendType: 'sqlite'
});

// After: SQLite with Redis acceleration
const cache = new CacheManager({
  backendType: 'fallback',
  backendConfig: {
    primaryBackend: 'redis',  // New fast layer
    fallbackBackend: 'sqlite' // Keeps existing data
  }
});

// Gradual migration as Redis fills
```

## Best Practices

1. **Set appropriate error threshold**
   ```javascript
   maxConsecutiveErrors: 3  // Balance responsiveness vs false positives
   ```

2. **Use health checks for confidence**
   ```javascript
   autoRecovery: true  // Auto-switch back when primary recovers
   healthCheckInterval: 30000  // Check every 30 seconds
   ```

3. **Monitor fallback usage**
   ```javascript
   if (stats.metrics.fallbackWrites > 0) {
     console.warn('Primary backend failed, using fallback');
   }
   ```

4. **Size fallback backend appropriately**
   ```javascript
   // SQLite should be large enough to handle peak load
   fallbackConfig: {
     db: '/var/cache/large-capacity.db'  // SSD recommended
   }
   ```

5. **Test failover**
   ```bash
   # Test by stopping Redis
   redis-cli shutdown
   # Cache should continue working via SQLite
   ```

## See Also

- [REDIS.md](./REDIS.md) - Redis backend details
- [PERSISTENCE.md](./PERSISTENCE.md) - Storage options
- [API.md](../API.md) - Full cache API
