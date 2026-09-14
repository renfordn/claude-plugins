/**
 * Skill: Persistent Cache Storage
 *
 * Pluggable storage layer for cache entries.
 * Supports multiple backends (memory, SQLite, Redis, etc).
 * Manages entry storage, retrieval, search, TTL enforcement, and metrics tracking.
 *
 * This is an internal storage layer used by Cache Management skill.
 * Not typically called directly by user code.
 */

const { createBackend } = require('./backends');

class PersistentCacheStorage {
  constructor(options = {}) {
    this.backendType = options.backendType || 'memory';
    this.backendConfig = options.backendConfig || {};
    this.storageBackend = null;
    this.initialized = false;
  }

  /**
   * Initialize the storage backend
   * Must be called before using storage methods
   * @returns {Promise<void>}
   */
  async initialize() {
    if (this.initialized) return;

    try {
      this.storageBackend = createBackend(this.backendType, this.backendConfig);
      await this.storageBackend.initialize(this.backendConfig);
      this.initialized = true;
    } catch (err) {
      throw new Error(`Failed to initialize storage backend: ${err.message}`);
    }
  }

  /**
   * Store a cache entry
   *
   * Creates a new stored entry with internal tracking fields (createdAt, accessedAt, accessCount).
   * Metadata is deep-copied to prevent external mutations from affecting cached data.
   *
   * @param {Object} entry - Cache entry { id?, prompt, output, metadata }
   * @returns {Promise<{success: boolean, entryId: string}>}
   */
  async store(entry) {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.store(entry);
  }

  /**
   * Retrieve a cache entry by ID
   * @param {string} entryId - Entry ID
   * @returns {Promise<Object|null>} Entry or null if not found/expired
   */
  async retrieve(entryId) {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.retrieve(entryId);
  }

  /**
   * Search for entries matching criteria
   * @param {Object} criteria - Search criteria (agentType, taskType, tags)
   * @returns {Promise<Array>} Array of matching entries
   */
  async search(criteria = {}) {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.search(criteria);
  }

  /**
   * Invalidate entries by ID or criteria
   * @param {string|Object} idOrCriteria - Entry ID or search criteria
   * @returns {Promise<{count: number}>} Number of invalidated entries
   */
  async invalidate(idOrCriteria) {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.invalidate(idOrCriteria);
  }

  /**
   * Record a metrics event
   * @param {Object} event - Metrics event
   * @returns {Promise<{success: boolean}>}
   */
  async recordMetrics(event) {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.recordMetrics(event);
  }

  /**
   * Get aggregated statistics
   * @returns {Promise<Object>} Stats including totalEntries, totalHits, etc.
   */
  async stats() {
    if (!this.initialized) await this.initialize();
    return this.storageBackend.stats();
  }

  /**
   * Configure storage options
   * @param {Object} options - Configuration options
   * @returns {Promise<void>}
   */
  async configure(options) {
    this.backendConfig = { ...this.backendConfig, ...options };
    if (this.storageBackend) {
      await this.storageBackend.configure(options);
    }
  }

  /**
   * Shutdown the storage backend
   * @returns {Promise<void>}
   */
  async shutdown() {
    if (this.storageBackend) {
      await this.storageBackend.shutdown();
      this.initialized = false;
    }
  }
}

module.exports = PersistentCacheStorage;
