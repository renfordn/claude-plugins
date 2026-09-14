/**
 * Fallback Storage Backend
 *
 * Automatically falls back from primary backend (Redis) to secondary backend (SQLite)
 * on connection failures or operation errors. Ensures cache continues working even if
 * primary backend is unavailable.
 *
 * Features:
 * - Transparent fallback on connection loss
 * - Health checks to detect recovery
 * - Automatic switch back when primary recovers
 * - Metrics tracking for both backends
 * - No data loss during failover
 */

const StorageBackend = require('./StorageBackend');
const RedisBackend = require('./RedisBackend');
const SQLiteBackend = require('./SQLiteBackend');

class FallbackBackend extends StorageBackend {
  constructor(config = {}) {
    super();
    this.config = {
      primaryBackend: config.primaryBackend || 'redis',
      fallbackBackend: config.fallbackBackend || 'sqlite',
      primaryConfig: config.primaryConfig || {},
      fallbackConfig: config.fallbackConfig || {},
      healthCheckInterval: config.healthCheckInterval || 30000, // Check every 30s
      maxConsecutiveErrors: config.maxConsecutiveErrors || 3,
      autoRecovery: config.autoRecovery !== false
    };

    this.primary = null;
    this.fallback = null;
    this.activBackend = 'primary'; // Which backend is active
    this.primaryHealthy = true;
    this.fallbackHealthy = true;
    this.consecutiveErrors = 0;
    this.healthCheckTimer = null;
    this.failoverTimestamp = null;

    this.metrics = {
      reads: 0,
      writes: 0,
      deletes: 0,
      errors: 0,
      failovers: 0,
      recoveries: 0,
      primaryReads: 0,
      primaryWrites: 0,
      fallbackReads: 0,
      fallbackWrites: 0
    };

    this.subscribers = new Set();
  }

  /**
   * Initialize both backends
   */
  async initialize() {
    try {
      // Initialize primary backend
      if (this.config.primaryBackend === 'redis') {
        try {
          this.primary = new RedisBackend(this.config.primaryConfig);
          await this.primary.initialize();
          this.primaryHealthy = this.primary.isReady?.() ?? this.primary.connected ?? true;
        } catch (err) {
          console.warn('[FallbackBackend] Primary backend (Redis) failed to initialize:', err.message);
          this.primaryHealthy = false;
        }
      }

      // Initialize fallback backend
      if (this.config.fallbackBackend === 'sqlite') {
        try {
          this.fallback = new SQLiteBackend(this.config.fallbackConfig);
          await this.fallback.initialize();
          this.fallbackHealthy = this.fallback.isReady?.() ?? true;
        } catch (err) {
          console.error('[FallbackBackend] Fallback backend (SQLite) failed to initialize:', err.message);
          this.fallbackHealthy = false;
        }
      }

      // Start health check
      if (this.config.autoRecovery) {
        this._startHealthCheck();
      }

      return true;
    } catch (err) {
      console.error('[FallbackBackend] Init error:', err.message);
      throw err;
    }
  }

  /**
   * Store entry, with fallback if primary fails
   */
  async store(entry) {
    try {
      if (this.activBackend === 'primary' && this.primary) {
        const result = await this.primary.store(entry);
        if (result.success) {
          this.metrics.writes++;
          this.metrics.primaryWrites++;
          this.consecutiveErrors = 0;
          return result;
        }
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary store failed:', err.message);
      this._recordError();
    }

    // Fallback to secondary backend
    if (this.fallback && this.activBackend !== 'fallback') {
      console.log('[FallbackBackend] Failing over to fallback for store');
      this.activBackend = 'fallback';
      this.metrics.failovers++;
      this.failoverTimestamp = Date.now();
    }

    try {
      const result = await this.fallback.store(entry);
      this.metrics.writes++;
      this.metrics.fallbackWrites++;
      return result;
    } catch (err) {
      console.error('[FallbackBackend] Fallback store failed:', err.message);
      this.metrics.errors++;
      return { success: false, error: err.message };
    }
  }

  /**
   * Retrieve entry, with fallback if primary fails
   */
  async retrieve(entryId) {
    try {
      if (this.activBackend === 'primary' && this.primary) {
        const entry = await this.primary.retrieve(entryId);
        if (entry !== null && entry !== undefined) {
          this.metrics.reads++;
          this.metrics.primaryReads++;
          this.consecutiveErrors = 0;
          return entry;
        }
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary retrieve failed:', err.message);
      this._recordError();
    }

    // Try fallback
    if (this.fallback) {
      if (this.activBackend !== 'fallback') {
        console.log('[FallbackBackend] Failing over to fallback for retrieve');
        this.activBackend = 'fallback';
        this.metrics.failovers++;
        this.failoverTimestamp = Date.now();
      }

      try {
        const entry = await this.fallback.retrieve(entryId);
        this.metrics.reads++;
        this.metrics.fallbackReads++;
        return entry;
      } catch (err) {
        console.error('[FallbackBackend] Fallback retrieve failed:', err.message);
        this.metrics.errors++;
        return null;
      }
    }

    return null;
  }

  /**
   * Search entries, with fallback if primary fails
   */
  async search(criteria = {}) {
    try {
      if (this.activBackend === 'primary' && this.primary) {
        const results = await this.primary.search(criteria);
        if (Array.isArray(results) && results.length > 0) {
          this.consecutiveErrors = 0;
          return results;
        }
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary search failed:', err.message);
      this._recordError();
    }

    // Try fallback
    if (this.fallback) {
      if (this.activBackend !== 'fallback') {
        console.log('[FallbackBackend] Failing over to fallback for search');
        this.activBackend = 'fallback';
        this.metrics.failovers++;
        this.failoverTimestamp = Date.now();
      }

      try {
        const results = await this.fallback.search(criteria);
        return results || [];
      } catch (err) {
        console.error('[FallbackBackend] Fallback search failed:', err.message);
        this.metrics.errors++;
        return [];
      }
    }

    return [];
  }

  /**
   * Invalidate entries, with fallback if primary fails
   */
  async invalidate(idOrCriteria) {
    try {
      if (this.activBackend === 'primary' && this.primary) {
        const result = await this.primary.invalidate(idOrCriteria);
        if (result && result.count !== undefined) {
          this.metrics.deletes++;
          this.consecutiveErrors = 0;
          return result;
        }
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary invalidate failed:', err.message);
      this._recordError();
    }

    // Try fallback
    if (this.fallback) {
      if (this.activBackend !== 'fallback') {
        console.log('[FallbackBackend] Failing over to fallback for invalidate');
        this.activBackend = 'fallback';
        this.metrics.failovers++;
        this.failoverTimestamp = Date.now();
      }

      try {
        const result = await this.fallback.invalidate(idOrCriteria);
        this.metrics.deletes++;
        return result;
      } catch (err) {
        console.error('[FallbackBackend] Fallback invalidate failed:', err.message);
        this.metrics.errors++;
        return { count: 0 };
      }
    }

    return { count: 0 };
  }

  /**
   * Record metrics
   */
  async recordMetrics(event) {
    try {
      if (this.primary) {
        await this.primary.recordMetrics(event);
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary recordMetrics failed');
    }

    try {
      if (this.fallback) {
        await this.fallback.recordMetrics(event);
      }
    } catch (err) {
      console.warn('[FallbackBackend] Fallback recordMetrics failed');
    }
  }

  /**
   * Get aggregated statistics
   */
  async stats() {
    const primaryStats = this.primary ? await this.primary.stats().catch(() => ({})) : {};
    const fallbackStats = this.fallback ? await this.fallback.stats().catch(() => ({})) : {};

    return {
      activeBackend: this.activBackend,
      primaryHealthy: this.primaryHealthy,
      fallbackHealthy: this.fallbackHealthy,
      consecutiveErrors: this.consecutiveErrors,
      failoverCount: this.metrics.failovers,
      recoveryCount: this.metrics.recoveries,
      failoverTimestamp: this.failoverTimestamp,
      metrics: this.metrics,
      primaryStats,
      fallbackStats
    };
  }

  /**
   * Get backend status
   */
  getStatus() {
    return {
      activeBackend: this.activBackend,
      primary: {
        healthy: this.primaryHealthy,
        type: this.config.primaryBackend
      },
      fallback: {
        healthy: this.fallbackHealthy,
        type: this.config.fallbackBackend
      },
      failovers: this.metrics.failovers,
      recoveries: this.metrics.recoveries
    };
  }

  /**
   * Manual backend switch
   */
  switchBackend(backend) {
    if (['primary', 'fallback'].includes(backend)) {
      this.activBackend = backend;
      console.log(`[FallbackBackend] Switched to ${backend} backend`);
      return true;
    }
    return false;
  }

  /**
   * Shutdown
   */
  async shutdown() {
    this._stopHealthCheck();

    try {
      if (this.primary && this.primary.shutdown) {
        await this.primary.shutdown();
      }
    } catch (err) {
      console.warn('[FallbackBackend] Primary shutdown error:', err.message);
    }

    try {
      if (this.fallback && this.fallback.shutdown) {
        await this.fallback.shutdown();
      }
    } catch (err) {
      console.warn('[FallbackBackend] Fallback shutdown error:', err.message);
    }
  }

  // Private methods

  /**
   * Record operation error
   */
  _recordError() {
    this.consecutiveErrors++;
    this.metrics.errors++;

    if (this.consecutiveErrors >= this.config.maxConsecutiveErrors) {
      this.primaryHealthy = false;
      if (this.activBackend === 'primary') {
        console.log('[FallbackBackend] Too many errors, marking primary unhealthy');
      }
    }
  }

  /**
   * Start periodic health check
   */
  _startHealthCheck() {
    this.healthCheckTimer = setInterval(async () => {
      try {
        // Check primary
        if (this.primary && !this.primaryHealthy) {
          try {
            const testEntry = { id: '_health_check_', data: 'test' };
            await this.primary.store(testEntry);
            await this.primary.retrieve('_health_check_');

            // Primary recovered
            this.primaryHealthy = true;
            this.consecutiveErrors = 0;
            console.log('[FallbackBackend] Primary backend recovered');

            if (this.activBackend === 'fallback') {
              this.activBackend = 'primary';
              this.metrics.recoveries++;
              console.log('[FallbackBackend] Switched back to primary backend');
            }
          } catch (err) {
            // Still unhealthy
          }
        }

        // Check fallback
        if (this.fallback) {
          try {
            const testEntry = { id: '_health_check_', data: 'test' };
            await this.fallback.store(testEntry);
            await this.fallback.retrieve('_health_check_');
            this.fallbackHealthy = true;
          } catch (err) {
            this.fallbackHealthy = false;
            console.warn('[FallbackBackend] Fallback backend unhealthy');
          }
        }
      } catch (err) {
        console.error('[FallbackBackend] Health check error:', err.message);
      }
    }, this.config.healthCheckInterval);
  }

  /**
   * Stop health check
   */
  _stopHealthCheck() {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }
}

module.exports = FallbackBackend;
