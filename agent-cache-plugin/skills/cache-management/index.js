/**
 * Cache Management Skill
 *
 * Core implementation of cache storage, retrieval, and management operations.
 * Provides in-memory caching with TTL, eviction policies, and search capabilities.
 */

class CacheManager {
  constructor(options = {}) {
    // Configuration
    this.maxSize = options.maxSize || 100 * 1024 * 1024; // 100 MB
    this.maxEntries = options.maxEntries || 10000;
    this.defaultTTL = options.defaultTTL || 3 * 24 * 60 * 60 * 1000; // 3 days
    this.evictionPolicy = options.evictionPolicy || 'LRU'; // LRU, LFU, FIFO

    // Storage
    this.entries = new Map(); // id -> entry
    this.index = new Map(); // tag -> Set of entry ids
    this.currentSize = 0; // bytes
    this.stats = {
      hits: 0,
      misses: 0,
      evictions: 0,
      stores: 0
    };
  }

  /**
   * Store a cache entry
   */
  async store(entry) {
    try {
      // Validate entry
      if (!entry.prompt || !entry.output) {
        return { success: false, error: 'Missing required fields: prompt, output' };
      }

      // Generate ID if not provided
      const id = entry.id || this._generateId();

      // Ensure TTL is set
      const ttl = entry.metadata?.ttl || this.defaultTTL;
      if (ttl <= 0) {
        return { success: false, error: 'TTL must be positive' };
      }

      // Serialize entry
      const serialized = JSON.stringify(entry);
      const entrySize = Buffer.byteLength(serialized, 'utf8');

      // Check if adding would exceed limits
      if (this.entries.size >= this.maxEntries ||
          (this.currentSize + entrySize) > this.maxSize) {
        await this.evict(entrySize);
      }

      // Create cache entry with metadata
      const cacheEntry = {
        ...entry,
        id,
        metadata: {
          ...entry.metadata,
          ttl,
          timestamp: Date.now(),
          tokenCount: entry.metadata?.tokenCount || 0
        },
        stats: {
          hits: 0,
          lastAccessed: Date.now(),
          createdAt: Date.now()
        },
        size: entrySize
      };

      // Store entry
      this.entries.set(id, cacheEntry);
      this.currentSize += entrySize;

      // Update indices - include agentType and taskType as tags automatically
      let tags = entry.metadata?.tags || [];
      if (entry.metadata?.agentType && !tags.includes(entry.metadata.agentType)) {
        tags = [...tags, entry.metadata.agentType];
      }
      if (entry.metadata?.taskType && !tags.includes(entry.metadata.taskType)) {
        tags = [...tags, entry.metadata.taskType];
      }

      tags.forEach(tag => {
        if (!this.index.has(tag)) {
          this.index.set(tag, new Set());
        }
        this.index.get(tag).add(id);
      });

      // Update statistics
      this.stats.stores++;

      return {
        success: true,
        entryId: id,
        size: entrySize,
        stats: this.getStats()
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Retrieve a cache entry by ID
   */
  async retrieve(entryId) {
    const start = Date.now();

    try {
      const entry = this.entries.get(entryId);

      if (!entry) {
        this.stats.misses++;
        return {
          entry: null,
          found: false,
          retrievalTime: Date.now() - start,
          cached: false
        };
      }

      // Check if expired
      if (this._isExpired(entry)) {
        await this.invalidate(entryId);
        this.stats.misses++;
        return {
          entry: null,
          found: false,
          retrievalTime: Date.now() - start,
          reason: 'Entry expired'
        };
      }

      // Update access stats
      entry.stats.hits++;
      entry.stats.lastAccessed = Date.now();
      this.stats.hits++;

      return {
        entry: {
          id: entry.id,
          prompt: entry.prompt,
          output: entry.output,
          metadata: entry.metadata,
          stats: entry.stats
        },
        found: true,
        retrievalTime: Date.now() - start,
        cached: true
      };
    } catch (error) {
      return {
        entry: null,
        found: false,
        retrievalTime: Date.now() - start,
        error: error.message
      };
    }
  }

  /**
   * Search cache entries by pattern and tags
   */
  async search(query = {}) {
    try {
      const pattern = query.pattern || '*';
      const tags = query.tags || [];
      const maxAge = query.maxAge || Infinity;
      const limit = query.limit || 100;

      const now = Date.now();
      let results = [];

      // Start with all entries or tag-filtered entries
      let candidates;
      if (tags.length > 0) {
        // Find entries matching all tags
        const tagSets = tags.map(tag => this.index.get(tag) || new Set());
        candidates = tagSets.length > 0
          ? [...tagSets[0]].filter(id =>
              tagSets.every(set => set.has(id)))
          : [];
      } else {
        candidates = [...this.entries.keys()];
      }

      // Filter by pattern, age, and validity
      for (const id of candidates) {
        if (results.length >= limit) break;

        const entry = this.entries.get(id);
        if (!entry) continue;

        // Skip expired entries
        if (this._isExpired(entry)) {
          continue;
        }

        // Check age
        const age = now - entry.metadata.timestamp;
        if (age > maxAge) {
          continue;
        }

        // Check pattern match (simple substring matching)
        if (pattern !== '*') {
          const matchStr = `${entry.prompt} ${entry.metadata.agentType || ''}`;
          if (!matchStr.toLowerCase().includes(pattern.toLowerCase())) {
            continue;
          }
        }

        results.push({
          id: entry.id,
          prompt: entry.prompt,
          metadata: entry.metadata,
          stats: entry.stats,
          ageSec: Math.round(age / 1000)
        });
      }

      return results;
    } catch (error) {
      console.error('Search error:', error);
      return [];
    }
  }

  /**
   * Invalidate cache entries by ID or pattern
   */
  async invalidate(idOrPattern) {
    try {
      const removed = [];

      if (typeof idOrPattern === 'string') {
        if (idOrPattern.includes('*')) {
          // Pattern-based invalidation
          for (const id of this.entries.keys()) {
            if (this._matchPattern(id, idOrPattern)) {
              removed.push(id);
            }
          }
        } else {
          // Direct ID invalidation
          if (this.entries.has(idOrPattern)) {
            removed.push(idOrPattern);
          }
        }
      }

      // Remove entries and update indices
      for (const id of removed) {
        const entry = this.entries.get(id);
        if (entry) {
          this.currentSize -= entry.size;
          this.entries.delete(id);

          // Remove from indices
          const tags = entry.metadata?.tags || [];
          tags.forEach(tag => {
            const tagSet = this.index.get(tag);
            if (tagSet) {
              tagSet.delete(id);
              if (tagSet.size === 0) {
                this.index.delete(tag);
              }
            }
          });
        }
      }

      return {
        count: removed.length,
        details: removed.map(id => `Invalidated entry: ${id}`)
      };
    } catch (error) {
      return { count: 0, error: error.message };
    }
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const entries = [...this.entries.values()];
    const retrievalTimes = entries
      .filter(e => e.stats.hits > 0)
      .map(e => e.stats.hits);

    return {
      totalEntries: this.entries.size,
      cacheSize: this.currentSize,
      maxSize: this.maxSize,
      utilizationPercent: Math.round((this.currentSize / this.maxSize) * 100),
      hitRate: this.stats.hits + this.stats.misses > 0
        ? this.stats.hits / (this.stats.hits + this.stats.misses)
        : 0,
      totalHits: this.stats.hits,
      totalMisses: this.stats.misses,
      totalStores: this.stats.stores,
      totalEvictions: this.stats.evictions,
      avgRetrievalTime: retrievalTimes.length > 0
        ? retrievalTimes.reduce((a, b) => a + b, 0) / retrievalTimes.length
        : 0,
      oldestEntry: entries.length > 0
        ? Math.min(...entries.map(e => e.metadata.timestamp))
        : null,
      newestEntry: entries.length > 0
        ? Math.max(...entries.map(e => e.metadata.timestamp))
        : null,
      topAgents: this._getTopAgents(entries)
    };
  }

  /**
   * Configure cache settings
   */
  async configure(options) {
    try {
      const updated = {};

      if (options.maxSize !== undefined) {
        this.maxSize = options.maxSize;
        updated.maxSize = options.maxSize;
      }

      if (options.maxEntries !== undefined) {
        this.maxEntries = options.maxEntries;
        updated.maxEntries = options.maxEntries;
      }

      if (options.defaultTTL !== undefined) {
        this.defaultTTL = options.defaultTTL;
        updated.defaultTTL = options.defaultTTL;
      }

      if (options.evictionPolicy !== undefined) {
        if (!['LRU', 'LFU', 'FIFO'].includes(options.evictionPolicy)) {
          return {
            success: false,
            error: 'Invalid eviction policy. Must be LRU, LFU, or FIFO'
          };
        }
        this.evictionPolicy = options.evictionPolicy;
        updated.evictionPolicy = options.evictionPolicy;
      }

      return {
        success: true,
        applied: updated,
        current: {
          maxSize: this.maxSize,
          maxEntries: this.maxEntries,
          defaultTTL: this.defaultTTL,
          evictionPolicy: this.evictionPolicy
        }
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Enforce cache limits and evict entries
   */
  async enforce(options = {}) {
    const maxSize = options.maxSize || this.maxSize;
    const maxEntries = options.maxEntries || this.maxEntries;
    const policy = options.policy || this.evictionPolicy;

    const evicted = [];

    // Remove expired entries first (passive cleanup)
    const now = Date.now();
    for (const [id, entry] of this.entries.entries()) {
      if (this._isExpired(entry)) {
        evicted.push(id);
      }
    }

    for (const id of evicted) {
      await this.invalidate(id);
    }

    // Active eviction if still over limits
    while ((this.entries.size > maxEntries || this.currentSize > maxSize) &&
           this.entries.size > 0) {
      const toEvict = this._selectForEviction(policy);
      if (toEvict) {
        evicted.push(toEvict);
        const entry = this.entries.get(toEvict);
        if (entry) {
          this.currentSize -= entry.size;
          this.entries.delete(toEvict);
          this.stats.evictions++;
        }
      } else {
        break;
      }
    }

    return {
      evictedCount: evicted.length,
      details: evicted,
      finalSize: this.currentSize,
      finalCount: this.entries.size
    };
  }

  /**
   * Clear all cache entries
   */
  async clear() {
    const count = this.entries.size;
    this.entries.clear();
    this.index.clear();
    this.currentSize = 0;
    return { count, success: true };
  }

  // Private methods

  _generateId() {
    return `cache-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  _isExpired(entry) {
    const age = Date.now() - entry.metadata.timestamp;
    const ttl = entry.metadata.ttl || this.defaultTTL;
    return age > ttl;
  }

  _matchPattern(id, pattern) {
    const regex = new RegExp(pattern.replace(/\*/g, '.*'));
    return regex.test(id);
  }

  async evict(sizeNeeded) {
    const maxSize = this.maxSize - sizeNeeded;
    const maxEntries = Math.max(1, this.maxEntries - 10);

    return this.enforce({
      maxSize,
      maxEntries,
      policy: this.evictionPolicy
    });
  }

  _selectForEviction(policy) {
    if (this.entries.size === 0) return null;

    const entries = [...this.entries.entries()];

    if (policy === 'LRU') {
      // Least Recently Used
      const lruEntry = entries.reduce((min, [, entry]) =>
        entry.stats.lastAccessed < min[1].stats.lastAccessed ? [min[0], entry] : min
      );
      return lruEntry[0];
    } else if (policy === 'LFU') {
      // Least Frequently Used
      const lfuEntry = entries.reduce((min, [, entry]) =>
        entry.stats.hits < min[1].stats.hits ? [min[0], entry] : min
      );
      return lfuEntry[0];
    } else {
      // FIFO - First In First Out
      const fifoEntry = entries.reduce((min, [, entry]) =>
        entry.metadata.timestamp < min[1].metadata.timestamp ? [min[0], entry] : min
      );
      return fifoEntry[0];
    }
  }

  _getTopAgents(entries) {
    const agentCounts = {};
    entries.forEach(entry => {
      const agent = entry.metadata?.agentType || 'unknown';
      agentCounts[agent] = (agentCounts[agent] || 0) + 1;
    });

    return Object.entries(agentCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([agent, count]) => ({ agent, count }));
  }
}

// Singleton instance
let singletonInstance = null;

// Export as skill
module.exports = {
  name: 'cache-management',
  version: '1.0.0',
  description: 'Core cache storage and retrieval skill',

  createManager: (options) => {
    // Return singleton if no options, otherwise return new instance
    if (!options && singletonInstance) {
      return singletonInstance;
    }
    const manager = new CacheManager(options);
    if (!options) {
      singletonInstance = manager;
    }
    return manager;
  },

  getSingleton: () => {
    if (!singletonInstance) {
      singletonInstance = new CacheManager();
    }
    return singletonInstance;
  },

  resetSingleton: () => {
    singletonInstance = new CacheManager();
    return singletonInstance;
  },

  // Skill methods (called by Cowork) - use singleton
  async store(entry) {
    const manager = module.exports.getSingleton();
    return manager.store(entry);
  },

  async retrieve(entryId) {
    const manager = module.exports.getSingleton();
    return manager.retrieve(entryId);
  },

  async search(query) {
    const manager = module.exports.getSingleton();
    return manager.search(query);
  },

  async invalidate(idOrPattern) {
    const manager = module.exports.getSingleton();
    return manager.invalidate(idOrPattern);
  },

  async stats() {
    const manager = module.exports.getSingleton();
    return manager.getStats();
  },

  async configure(options) {
    const manager = module.exports.getSingleton();
    return manager.configure(options);
  },

  // Export class for testing and direct use
  CacheManager
};
