/**
 * Redis Storage Backend
 *
 * Distributed cache implementation using Redis for:
 * - Multi-process/multi-server cache sharing
 * - Fast in-memory storage with persistence options
 * - Pub/Sub for cross-instance cache invalidation
 * - Atomic operations and TTL management
 *
 * Requires: redis (npm install redis)
 * Usage: new RedisBackend({ host, port, db, keyPrefix })
 */

const StorageBackend = require('./StorageBackend');

class RedisBackend extends StorageBackend {
  constructor(config = {}) {
    super();
    this.config = {
      host: config.host || process.env.REDIS_HOST || 'localhost',
      port: config.port || parseInt(process.env.REDIS_PORT) || 6379,
      password: config.password || process.env.REDIS_PASSWORD,
      db: config.db || 0,
      keyPrefix: config.keyPrefix || 'cache:',
      maxRetries: config.maxRetries || 3,
      retryDelay: config.retryDelay || 1000,
      connectionTimeout: config.connectionTimeout || 5000,
      enablePubSub: config.enablePubSub !== false,
      metricsInterval: config.metricsInterval || 60000
    };

    this.client = null;
    this.pubsubClient = null;
    this.connected = false;
    this.metrics = {
      reads: 0,
      writes: 0,
      deletes: 0,
      errors: 0,
      hitRate: 0
    };
    this.subscribers = new Set();
  }

  /**
   * Initialize Redis connection
   */
  async initialize() {
    try {
      const redis = require('redis');

      const clientConfig = {
        socket: {
          host: this.config.host,
          port: this.config.port,
          connectTimeout: this.config.connectionTimeout,
          retryStrategy: (retries) => {
            if (retries > this.config.maxRetries) {
              console.error('[RedisBackend] Max retries exceeded');
              return new Error('Max Redis connection retries exceeded');
            }
            return this.config.retryDelay * Math.pow(2, retries);
          }
        }
      };

      if (this.config.password) {
        clientConfig.password = this.config.password;
      }

      if (this.config.db && this.config.db !== 0) {
        clientConfig.database = this.config.db;
      }

      this.client = redis.createClient(clientConfig);

      this.client.on('error', (err) => {
        console.error('[RedisBackend] Connection error:', err.message);
        this.connected = false;
        this.metrics.errors++;
      });

      this.client.on('connect', () => {
        console.log('[RedisBackend] Connected to Redis');
        this.connected = true;
      });

      await this.client.connect();
      this.connected = true;

      if (this.config.enablePubSub) {
        await this._initPubSub();
      }

      return true;
    } catch (err) {
      console.error('[RedisBackend] Initialization failed:', err.message);
      throw err;
    }
  }

  /**
   * Initialize Pub/Sub for cache invalidation
   */
  async _initPubSub() {
    try {
      const redis = require('redis');
      this.pubsubClient = redis.createClient({
        socket: {
          host: this.config.host,
          port: this.config.port
        }
      });

      if (this.config.password) {
        this.pubsubClient.password = this.config.password;
      }

      await this.pubsubClient.connect();

      this.pubsubClient.subscribe(`${this.config.keyPrefix}invalidate`, (message) => {
        this._handleInvalidation(message);
      });
    } catch (err) {
      console.warn('[RedisBackend] Pub/Sub initialization failed:', err.message);
    }
  }

  /**
   * Store a cache entry
   */
  async store(entry) {
    if (!this.connected || !this.client) {
      return { success: false, error: 'Redis not connected' };
    }

    try {
      const entryId = entry.id || this._generateId();
      const key = `${this.config.keyPrefix}entry:${entryId}`;
      const data = JSON.stringify({
        ...entry,
        id: entryId,
        storedAt: Date.now()
      });

      const ttlSeconds = entry.ttl ? Math.ceil(entry.ttl / 1000) : 86400; // Default 24h

      await this.client.set(key, data, {
        EX: ttlSeconds
      });

      this.metrics.writes++;
      return { success: true, entryId };
    } catch (err) {
      console.error('[RedisBackend] Store error:', err.message);
      this.metrics.errors++;
      return { success: false, error: err.message };
    }
  }

  /**
   * Retrieve a cache entry by ID
   */
  async retrieve(entryId) {
    if (!this.connected || !this.client) {
      return null;
    }

    try {
      const key = `${this.config.keyPrefix}entry:${entryId}`;
      const data = await this.client.get(key);

      if (!data) {
        return null;
      }

      this.metrics.reads++;
      const entry = JSON.parse(data);

      if (entry.expiresAt && Date.now() > entry.expiresAt) {
        await this.client.del(key);
        return null;
      }

      return entry;
    } catch (err) {
      console.error('[RedisBackend] Retrieve error:', err.message);
      this.metrics.errors++;
      return null;
    }
  }

  /**
   * Search for entries matching criteria
   */
  async search(criteria = {}) {
    if (!this.connected || !this.client) {
      return [];
    }

    try {
      const pattern = `${this.config.keyPrefix}entry:*`;
      const keys = await this.client.keys(pattern);
      const results = [];

      for (const key of keys) {
        const data = await this.client.get(key);
        if (!data) continue;

        const entry = JSON.parse(data);

        if (this._matchesCriteria(entry, criteria)) {
          results.push(entry);
        }
      }

      this.metrics.reads += keys.length;
      return results;
    } catch (err) {
      console.error('[RedisBackend] Search error:', err.message);
      this.metrics.errors++;
      return [];
    }
  }

  /**
   * Invalidate entries by ID or criteria
   */
  async invalidate(idOrCriteria) {
    if (!this.connected || !this.client) {
      return { count: 0 };
    }

    try {
      let keysToDelete = [];

      if (typeof idOrCriteria === 'string') {
        keysToDelete = [`${this.config.keyPrefix}entry:${idOrCriteria}`];
      } else if (typeof idOrCriteria === 'object') {
        const entries = await this.search(idOrCriteria);
        keysToDelete = entries.map(e => `${this.config.keyPrefix}entry:${e.id}`);
      }

      if (keysToDelete.length > 0) {
        await this.client.del(keysToDelete);
        this.metrics.deletes += keysToDelete.length;

        if (this.config.enablePubSub && this.client) {
          await this.client.publish(
            `${this.config.keyPrefix}invalidate`,
            JSON.stringify({ keys: keysToDelete })
          );
        }
      }

      return { count: keysToDelete.length };
    } catch (err) {
      console.error('[RedisBackend] Invalidate error:', err.message);
      this.metrics.errors++;
      return { count: 0 };
    }
  }

  /**
   * Record metrics
   */
  async recordMetrics(metrics) {
    try {
      const key = `${this.config.keyPrefix}metrics:${Date.now()}`;
      const data = JSON.stringify({
        ...metrics,
        timestamp: Date.now()
      });

      await this.client.setEx(key, 86400, data); // Keep for 24h
    } catch (err) {
      console.error('[RedisBackend] Metrics recording failed:', err.message);
    }
  }

  /**
   * Get storage statistics
   */
  async stats() {
    if (!this.connected || !this.client) {
      return { error: 'Redis not connected' };
    }

    try {
      const pattern = `${this.config.keyPrefix}entry:*`;
      const keys = await this.client.keys(pattern);
      const info = await this.client.info('stats');

      return {
        totalEntries: keys.length,
        totalSize: 0, // Redis doesn't provide easy size tracking
        metrics: this.metrics,
        redisInfo: info,
        connected: this.connected
      };
    } catch (err) {
      console.error('[RedisBackend] Stats error:', err.message);
      return { error: err.message };
    }
  }

  /**
   * Configure backend
   */
  configure(options) {
    this.config = { ...this.config, ...options };
  }

  /**
   * Shutdown connection
   */
  async shutdown() {
    try {
      if (this.pubsubClient) {
        await this.pubsubClient.quit();
      }
      if (this.client) {
        await this.client.quit();
      }
      this.connected = false;
      console.log('[RedisBackend] Disconnected from Redis');
    } catch (err) {
      console.error('[RedisBackend] Shutdown error:', err.message);
    }
  }

  /**
   * Check if backend is ready
   */
  isReady() {
    return this.connected && this.client !== null;
  }

  // Private methods

  /**
   * Generate unique entry ID
   */
  _generateId() {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Check if entry matches search criteria
   */
  _matchesCriteria(entry, criteria) {
    if (!criteria || Object.keys(criteria).length === 0) {
      return true;
    }

    for (const [key, value] of Object.entries(criteria)) {
      if (key === 'tags' && Array.isArray(value)) {
        if (!entry.tags || !value.some(t => entry.tags.includes(t))) {
          return false;
        }
      } else if (key === 'pattern' && value instanceof RegExp) {
        if (!value.test(entry.prompt || '')) {
          return false;
        }
      } else if (entry[key] !== value) {
        return false;
      }
    }

    return true;
  }

  /**
   * Handle cache invalidation from Pub/Sub
   */
  _handleInvalidation(message) {
    try {
      const { keys } = JSON.parse(message);
      this.subscribers.forEach(callback => {
        callback({ type: 'invalidate', keys });
      });
    } catch (err) {
      console.error('[RedisBackend] Invalidation handling error:', err.message);
    }
  }

  /**
   * Subscribe to cache events
   */
  subscribe(callback) {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }
}

module.exports = RedisBackend;
