/**
 * Abstract Storage Backend Interface
 *
 * Defines the contract for implementing different storage backends.
 * All backends must implement these methods to support the cache storage layer.
 *
 * Implementations should handle:
 * - Async operations (even memory backend returns Promises for consistency)
 * - Entry TTL validation
 * - Atomic operations where possible
 * - Error handling and recovery
 */

class StorageBackend {
  /**
   * Store a cache entry
   *
   * @param {Object} entry - Cache entry { id?, prompt, output, metadata }
   * @returns {Promise<{success: boolean, entryId: string}>}
   */
  async store(entry) {
    throw new Error('store() must be implemented by subclass');
  }

  /**
   * Retrieve a cache entry by ID
   *
   * @param {string} entryId - Entry ID
   * @returns {Promise<Object|null>} Entry or null if not found/expired
   */
  async retrieve(entryId) {
    throw new Error('retrieve() must be implemented by subclass');
  }

  /**
   * Search for entries matching criteria
   *
   * @param {Object} criteria - Search criteria (agentType, taskType, tags, etc)
   * @returns {Promise<Array>} Array of matching entries
   */
  async search(criteria = {}) {
    throw new Error('search() must be implemented by subclass');
  }

  /**
   * Invalidate entries by ID or criteria
   *
   * @param {string|Object} idOrCriteria - Entry ID or search criteria
   * @returns {Promise<{count: number}>} Number of invalidated entries
   */
  async invalidate(idOrCriteria) {
    throw new Error('invalidate() must be implemented by subclass');
  }

  /**
   * Record a metrics event
   *
   * @param {Object} event - Metrics event
   * @returns {Promise<{success: boolean}>}
   */
  async recordMetrics(event) {
    throw new Error('recordMetrics() must be implemented by subclass');
  }

  /**
   * Get aggregated statistics
   *
   * @returns {Promise<Object>} Stats including totalEntries, totalHits, avgTokensSaved, etc
   */
  async stats() {
    throw new Error('stats() must be implemented by subclass');
  }

  /**
   * Configure storage options
   *
   * @param {Object} options - Configuration options
   * @returns {Promise<void>}
   */
  async configure(options) {
    throw new Error('configure() must be implemented by subclass');
  }

  /**
   * Initialize backend (connect, create tables, etc)
   *
   * @param {Object} config - Initialization config
   * @returns {Promise<void>}
   */
  async initialize(config) {
    throw new Error('initialize() must be implemented by subclass');
  }

  /**
   * Shutdown/cleanup backend (close connections, etc)
   *
   * @returns {Promise<void>}
   */
  async shutdown() {
    throw new Error('shutdown() must be implemented by subclass');
  }

  /**
   * Check if backend is ready
   *
   * @returns {Promise<boolean>}
   */
  async isReady() {
    throw new Error('isReady() must be implemented by subclass');
  }
}

module.exports = StorageBackend;
