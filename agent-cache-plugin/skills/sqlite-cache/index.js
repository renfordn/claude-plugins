/**
 * SQLite-backed CacheManager.
 *
 * Replaces the in-memory Map singleton from skills/cache-management/index.js.
 * Uses better-sqlite3 (synchronous API) — no Promises needed at the DB layer.
 *
 * Public API (matches Map-based predecessor where feasible):
 *   store(entry)        → { success, key }
 *   retrieve(key)       → entry | null
 *   invalidate(key)     → { success, count }
 *   stats()             → { totalEntries, hitCount, missCount, hitRate, oldestTs, newestTs, avgTokenSaved }
 *   enforce(opts)       → { evictedCount }
 *   getSingleton(path)  → CacheManager  (module-level singleton)
 *   resetSingleton()    → void          (test helper)
 */

const path = require('path');
const os = require('os');
const fs = require('fs');
const Database = require('better-sqlite3');
const { SCHEMA_SQL } = require('./schema');

const DEFAULT_TTL = 72 * 60 * 60 * 1000; // 72 hours in ms
const DEFAULT_MAX_ENTRIES = 10_000;

class CacheManager {
  /**
   * @param {string} dbPath - File path or ':memory:' for tests.
   * @param {object} [opts]
   * @param {number} [opts.maxEntries=10000]
   * @param {number} [opts.defaultTTL=72h]
   */
  constructor(dbPath, opts = {}) {
    this.dbPath = dbPath;
    this.maxEntries = opts.maxEntries || DEFAULT_MAX_ENTRIES;
    this.defaultTTL = opts.defaultTTL || DEFAULT_TTL;

    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    if (dbPath !== ':memory:') {
      try { fs.chmodSync(dbPath, 0o600); } catch { /* non-fatal on read-only FS */ }
    }
    this._runSchema();
    this._prepareStatements();
  }

  _runSchema() {
    this.db.exec(SCHEMA_SQL);
  }

  _prepareStatements() {
    this._stmtGet = this.db.prepare(
      'SELECT * FROM cache WHERE key = ? AND (created_at + ttl) > ?'
    );
    this._stmtInsert = this.db.prepare(`
      INSERT OR REPLACE INTO cache
        (key, agent_type, task_slug, output_digest, output_blob, decisions, warnings, token_count, created_at, accessed_at, ttl)
      VALUES
        (@key, @agent_type, @task_slug, @output_digest, @output_blob, @decisions, @warnings, @token_count, @created_at, @accessed_at, @ttl)
    `);
    this._stmtTouch = this.db.prepare(
      'UPDATE cache SET accessed_at = ? WHERE key = ?'
    );
    this._stmtDelete = this.db.prepare('DELETE FROM cache WHERE key = ?');
    this._stmtCount = this.db.prepare('SELECT COUNT(*) AS n FROM cache');
    this._stmtLruEvict = this.db.prepare(`
      DELETE FROM cache WHERE key IN (
        SELECT key FROM cache ORDER BY accessed_at ASC LIMIT ?
      )
    `);
    this._stmtStats = this.db.prepare(`
      SELECT
        COUNT(*) AS totalEntries,
        MIN(created_at) AS oldestTs,
        MAX(created_at) AS newestTs
      FROM cache
    `);
    this._stmtEventInsert = this.db.prepare(
      'INSERT INTO cache_events (cache_key, event_type, token_count, ts) VALUES (?, ?, ?, ?)'
    );
    this._stmtHitCount = this.db.prepare(
      "SELECT COUNT(*) AS n FROM cache_events WHERE event_type = 'hit'"
    );
    this._stmtMissCount = this.db.prepare(
      "SELECT COUNT(*) AS n FROM cache_events WHERE event_type = 'miss'"
    );
    this._stmtAvgTokenSaved = this.db.prepare(
      "SELECT AVG(token_count) AS avg FROM cache_events WHERE event_type = 'hit'"
    );
  }

  /**
   * Store an entry. Performs LRU eviction first if at capacity.
   * @param {object} entry
   * @param {string} entry.key
   * @param {string} entry.agent_type
   * @param {string} entry.task_slug
   * @param {string} entry.output_blob   JSON string
   * @param {string} [entry.output_digest]
   * @param {string} [entry.decisions]
   * @param {string} [entry.warnings]
   * @param {number} [entry.token_count=0]
   * @param {number} [entry.ttl]         ms
   */
  store(entry) {
    const now = Date.now();
    const row = {
      key: entry.key,
      agent_type: entry.agent_type || '',
      task_slug: entry.task_slug || '',
      output_digest: entry.output_digest || '',
      output_blob: entry.output_blob,
      decisions: entry.decisions || null,
      warnings: entry.warnings || null,
      token_count: entry.token_count || 0,
      created_at: now,
      accessed_at: now,
      ttl: entry.ttl || this.defaultTTL
    };

    // LRU eviction before insert
    const { n } = this._stmtCount.get();
    if (n >= this.maxEntries) {
      const excess = n - this.maxEntries + 1;
      this._stmtLruEvict.run(excess);
    }

    this._stmtInsert.run(row);
    this._stmtEventInsert.run(entry.key, 'store', row.token_count, now);
    return { success: true, key: entry.key };
  }

  /**
   * Retrieve a non-expired entry, updating accessed_at.
   * @param {string} key
   * @returns {object|null}
   */
  retrieve(key) {
    const now = Date.now();
    const row = this._stmtGet.get(key, now);
    if (!row) {
      this._stmtEventInsert.run(key, 'miss', 0, now);
      return null;
    }
    this._stmtTouch.run(now, key);
    this._stmtEventInsert.run(key, 'hit', row.token_count, now);
    return row;
  }

  /**
   * Delete an entry by key.
   */
  invalidate(key) {
    const info = this._stmtDelete.run(key);
    return { success: true, count: info.changes };
  }

  /**
   * Return aggregate stats.
   */
  stats() {
    const { totalEntries, oldestTs, newestTs } = this._stmtStats.get();
    const { n: hitCount } = this._stmtHitCount.get();
    const { n: missCount } = this._stmtMissCount.get();
    const total = hitCount + missCount;
    const hitRate = total > 0 ? hitCount / total : 0;
    const { avg: avgTokenSaved } = this._stmtAvgTokenSaved.get();
    return {
      totalEntries,
      hitCount,
      missCount,
      hitRate,
      avgTokenSaved: avgTokenSaved || 0,
      oldestTs: oldestTs || null,
      newestTs: newestTs || null
    };
  }

  /**
   * Alias for stats() — matches the interface expected by commands and orchestrator.
   */
  getStats() {
    return this.stats();
  }

  /**
   * Delete all entries. Returns { deletedCount }.
   */
  clear() {
    const info = this.db.prepare('DELETE FROM cache').run();
    return { deletedCount: info.changes };
  }

  /**
   * Search entries by optional pattern, tags, maxAge, and limit.
   * @param {object} [opts]
   * @param {string}   [opts.pattern]  - Substring match against key
   * @param {string[]} [opts.tags]     - agent_type values to include
   * @param {number}   [opts.maxAge]   - Max age in ms (entries older than this are excluded)
   * @param {number}   [opts.limit]    - Max rows to return
   * @returns {object[]}
   */
  search(opts = {}) {
    const { pattern, tags, maxAge, limit } = opts;
    const conditions = ['(created_at + ttl) > ?'];
    const params = [Date.now()];

    if (pattern) {
      conditions.push('key LIKE ?');
      params.push(`%${pattern}%`);
    }
    if (tags && tags.length > 0) {
      conditions.push(`agent_type IN (${tags.map(() => '?').join(',')})`);
      params.push(...tags);
    }
    if (maxAge != null) {
      conditions.push('created_at > ?');
      params.push(Date.now() - maxAge);
    }

    const sql = `SELECT * FROM cache WHERE ${conditions.join(' AND ')} ORDER BY accessed_at DESC${limit ? ' LIMIT ?' : ''}`;
    if (limit) params.push(limit);

    return this.db.prepare(sql).all(...params);
  }

  /**
   * Enforce maxEntries by LRU eviction.
   */
  enforce(opts = {}) {
    const maxEntries = opts.maxEntries || this.maxEntries;
    const { n } = this._stmtCount.get();
    if (n <= maxEntries) return { evictedCount: 0 };
    const excess = n - maxEntries;
    const info = this._stmtLruEvict.run(excess);
    return { evictedCount: info.changes };
  }

  /** Close the underlying DB (useful in tests). */
  close() {
    this.db.close();
  }
}

// Module-level singleton
let _singleton = null;

/**
 * @param {string} [dbPath] - Path to cache.db; defaults to env var or fallback.
 *   Pass ':memory:' for in-process test use. Any other explicit path must resolve
 *   within the plugin data directory; paths outside are rejected to prevent traversal.
 */
function getSingleton(dbPath) {
  if (!_singleton) {
    const resolvedPath = dbPath || _resolveDbPath();
    _assertAllowedPath(resolvedPath);
    _singleton = new CacheManager(resolvedPath);
  }
  return _singleton;
}

function _assertAllowedPath(dbPath) {
  if (dbPath === ':memory:') return;
  const resolved = path.resolve(dbPath);
  const allowedBase = process.env.CLAUDE_PLUGIN_DATA
    ? path.resolve(process.env.CLAUDE_PLUGIN_DATA)
    : path.join(os.homedir(), '.claude', 'plugin-data');
  if (!resolved.startsWith(allowedBase + path.sep) && resolved !== allowedBase) {
    throw new Error(`DB path outside allowed directory: ${resolved}`);
  }
}

function resetSingleton() {
  if (_singleton) {
    try { _singleton.close(); } catch { /* ignore */ }
    _singleton = null;
  }
}

function _resolveDbPath() {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA;
  if (!dataDir) {
    const fallback = path.join(os.homedir(), '.claude', 'plugin-data', 'agent-cache-plugin');
    fs.mkdirSync(fallback, { recursive: true });
    process.stderr.write(
      '[agent-cache-plugin] CLAUDE_PLUGIN_DATA unset; falling back to ' + fallback + '\n'
    );
    return path.join(fallback, 'cache.db');
  }
  const resolved = path.resolve(dataDir);
  fs.mkdirSync(resolved, { recursive: true });
  return path.join(resolved, 'cache.db');
}

module.exports = { CacheManager, getSingleton, resetSingleton };
