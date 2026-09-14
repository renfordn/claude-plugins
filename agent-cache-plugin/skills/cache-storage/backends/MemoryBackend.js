/**
 * Memory Backend Implementation
 *
 * In-memory storage backend using JavaScript Map for O(1) lookups.
 * No persistence - cache is lost when process exits.
 * Ideal for single-session or testing scenarios.
 */

const StorageBackend = require('./StorageBackend');

class MemoryBackend extends StorageBackend {
  constructor(config = {}) {
    super();
    this.config = config;
    this.entries = new Map();
    this.metrics = [];
    this.ready = true;
  }

  async store(entry) {
    const entryId = entry.id || this._generateId();
    const stored = {
      id: entryId,
      prompt: entry.prompt,
      output: entry.output,
      metadata: JSON.parse(JSON.stringify(entry.metadata)),
      createdAt: Date.now(),
      accessedAt: Date.now(),
      accessCount: 0
    };
    this.entries.set(entryId, stored);
    return { success: true, entryId };
  }

  async retrieve(entryId) {
    const entry = this.entries.get(entryId);
    if (!entry) {
      return null;
    }

    if (this._isExpired(entry)) {
      return null;
    }

    entry.accessedAt = Date.now();
    entry.accessCount += 1;
    return entry;
  }

  async search(criteria = {}) {
    const results = [];
    for (const entry of this.entries.values()) {
      if (this._isExpired(entry)) {
        continue;
      }
      if (!this._matchesCriteria(entry, criteria)) {
        continue;
      }
      results.push(entry);
    }
    return results;
  }

  async invalidate(idOrCriteria) {
    let count = 0;

    if (typeof idOrCriteria === 'string') {
      if (this.entries.has(idOrCriteria)) {
        this.entries.delete(idOrCriteria);
        count = 1;
      }
    } else if (typeof idOrCriteria === 'object') {
      const entriesToDelete = [];
      for (const [id, entry] of this.entries) {
        if (this._matchesCriteria(entry, idOrCriteria)) {
          entriesToDelete.push(id);
        }
      }
      entriesToDelete.forEach(id => this.entries.delete(id));
      count = entriesToDelete.length;
    }

    return { count };
  }

  async recordMetrics(event) {
    this.metrics.push({
      ...event,
      recordedAt: Date.now()
    });
    return { success: true };
  }

  async stats() {
    let totalEntries = 0;
    for (const entry of this.entries.values()) {
      if (!this._isExpired(entry)) {
        totalEntries += 1;
      }
    }

    let totalHits = 0;
    let totalMisses = 0;
    const tokensSavedList = [];

    for (const metric of this.metrics) {
      if (metric.type === 'hit') {
        totalHits += 1;
        if (metric.tokensUsed !== undefined) {
          tokensSavedList.push(metric.tokensUsed);
        }
      } else if (metric.type === 'miss') {
        totalMisses += 1;
      }
    }

    const avgTokensSaved = tokensSavedList.length > 0
      ? tokensSavedList.reduce((a, b) => a + b, 0) / tokensSavedList.length
      : 0;

    return {
      totalEntries,
      totalHits,
      totalMisses,
      avgTokensSaved
    };
  }

  async configure(options) {
    this.config = { ...this.config, ...options };
  }

  async initialize(config) {
    this.config = config || this.config;
    this.ready = true;
  }

  async shutdown() {
    this.entries.clear();
    this.metrics = [];
    this.ready = false;
  }

  async isReady() {
    return this.ready;
  }

  // Private helper methods

  _isExpired(entry) {
    const { metadata } = entry;
    if (metadata.ttl === null || metadata.ttl === undefined) {
      return false;
    }

    if (metadata.timestamp < 1704067200000) {
      return false;
    }

    const expirationTime = metadata.timestamp + metadata.ttl;
    return expirationTime <= Date.now();
  }

  _matchesCriteria(entry, criteria) {
    const { metadata } = entry;

    if (criteria.agentType !== undefined && metadata.agentType !== criteria.agentType) {
      return false;
    }

    if (criteria.taskType !== undefined && metadata.taskType !== criteria.taskType) {
      return false;
    }

    if (criteria.tags !== undefined && Array.isArray(criteria.tags)) {
      const hasMatchingTag = criteria.tags.some(tag =>
        metadata.tags && metadata.tags.includes(tag)
      );
      if (!hasMatchingTag) {
        return false;
      }
    }

    return true;
  }

  _generateId() {
    return `entry-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

module.exports = MemoryBackend;
