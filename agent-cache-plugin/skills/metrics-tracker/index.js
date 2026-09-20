'use strict';
/**
 * MetricsTracker — SQLite-backed.
 *
 * All metrics read from cache_events table; no in-memory accumulators.
 *
 * Public API:
 *   recordHit(event)          → { success, eventId }
 *   recordMiss(event)         → { success, eventId }
 *   getHitRate()              → { hitRate, totalHits, totalMisses, totalQueries }
 *   getTokenSavings()         → { totalTokensSaved, avgPerHit, maxSingleSave, hitCount, estimatedCostReduction }
 *   getPerformanceMetrics()   → { totalEvents, ... }
 *   getRecommendations()      → { suggestions }
 *   recordInvalidation(event) → { success }
 *   getSingleton(path)        → MetricsTracker
 *   resetSingleton()          → void
 *   close()                   → void
 */

const Database = require('better-sqlite3');
const { SCHEMA_SQL } = require('../sqlite-cache/schema');

class MetricsTracker {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.exec(SCHEMA_SQL);
    this._prepare();
  }

  _prepare() {
    this._stmtInsertEvent = this.db.prepare(
      'INSERT INTO cache_events (cache_key, event_type, token_count, ts) VALUES (?, ?, ?, ?)'
    );
    this._stmtHits = this.db.prepare(
      "SELECT COUNT(*) AS n FROM cache_events WHERE event_type = 'hit'"
    );
    this._stmtMisses = this.db.prepare(
      "SELECT COUNT(*) AS n FROM cache_events WHERE event_type = 'miss'"
    );
    this._stmtTotal = this.db.prepare('SELECT COUNT(*) AS n FROM cache_events');
    this._stmtTokenSum = this.db.prepare(
      "SELECT SUM(token_count) AS total, AVG(token_count) AS avg, MAX(token_count) AS max, COUNT(*) AS cnt FROM cache_events WHERE event_type = 'hit'"
    );
  }

  async recordHit(event) {
    try {
      const id = this._stmtInsertEvent.run(
        event.cache_key || null, 'hit', event.token_count || 0, Date.now()
      ).lastInsertRowid;
      return { success: true, eventId: id };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  async recordMiss(event) {
    try {
      const id = this._stmtInsertEvent.run(
        event.cache_key || null, 'miss', 0, Date.now()
      ).lastInsertRowid;
      return { success: true, eventId: id };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  async recordInvalidation(event) {
    try {
      const id = this._stmtInsertEvent.run(
        null, 'evict', event.entriesRemoved || 0, Date.now()
      ).lastInsertRowid;
      return { success: true, eventId: id };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  async getHitRate() {
    const hits = this._stmtHits.get().n;
    const misses = this._stmtMisses.get().n;
    const total = hits + misses;
    return {
      hitRate: total > 0 ? hits / total : 0,
      totalHits: hits,
      totalMisses: misses,
      totalQueries: total,
      timeWindow: 'All time'
    };
  }

  async getTokenSavings() {
    const { total, avg, max, cnt } = this._stmtTokenSum.get();
    const totalTokensSaved = total || 0;
    const avgPerHit = avg ? Math.round(avg) : 0;
    const maxSingleSave = max || 0;
    const estimatedCostReduction = `$${(totalTokensSaved * 0.000004).toFixed(4)}`;
    return { totalTokensSaved, avgPerHit, maxSingleSave, hitCount: cnt, estimatedCostReduction };
  }

  async getPerformanceMetrics() {
    const total = this._stmtTotal.get().n;
    return {
      totalEvents: total,
      period: 'All time',
      cacheRetrievalTime: { avg: 0, median: 0, p95: 0, p99: 0 },
      taskBreakdown: {},
      agentBreakdown: {},
      relevanceScores: { avg: 0, min: 0, max: 0 }
    };
  }

  async getRecommendations() {
    const suggestions = [];
    const total = this._stmtTotal.get().n;
    if (total === 0) return { suggestions: [] };

    const hits = this._stmtHits.get().n;
    const hitRate = total > 0 ? hits / total : 0;

    if (hitRate < 0.1) {
      suggestions.push({
        area: 'relevance-scoring',
        finding: 'Hit rate below 10%',
        impact: 'high',
        action: 'Consider lowering relevance threshold from 75% to 65%, or implement embedding-based scoring'
      });
    }

    const { total: tokenTotal } = this._stmtTokenSum.get();
    const totalTokensSaved = tokenTotal || 0;
    if (hitRate > 0.25 && totalTokensSaved < 5000) {
      suggestions.push({
        area: 'cache-value',
        finding: 'Good hit rate but low token savings per hit',
        impact: 'medium',
        action: 'Focus cache on complex tasks (research, design) with longer outputs'
      });
    }

    return { suggestions };
  }

  async clear() {
    const { n } = this._stmtTotal.get();
    this.db.prepare('DELETE FROM cache_events').run();
    return { count: n, success: true };
  }

  close() {
    this.db.close();
  }
}

// Module-level singleton
let _singleton = null;

function getSingleton(dbPath) {
  if (!_singleton) {
    const { _resolveDbPath } = module.exports;
    const p = dbPath || _resolveDbPath();
    _singleton = new MetricsTracker(p);
  }
  return _singleton;
}

function resetSingleton() {
  if (_singleton) {
    try { _singleton.close(); } catch { /* ignore */ }
    _singleton = null;
  }
}

function _resolveDbPath() {
  const path = require('path');
  const os = require('os');
  const fs = require('fs');
  const d = process.env.CLAUDE_PLUGIN_DATA;
  if (!d) {
    const fallback = path.join(os.homedir(), '.claude', 'plugin-data', 'agent-cache-plugin');
    fs.mkdirSync(fallback, { recursive: true });
    return path.join(fallback, 'cache.db');
  }
  fs.mkdirSync(d, { recursive: true });
  return path.join(d, 'cache.db');
}

module.exports = {
  MetricsTracker,
  getSingleton,
  resetSingleton,
  _resolveDbPath,
  // Legacy compat shim for any callers that used the old module.exports.getSingleton()
  name: 'metrics-tracker',
  version: '2.0.0'
};
