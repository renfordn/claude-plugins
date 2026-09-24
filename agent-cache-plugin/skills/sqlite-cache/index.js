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
 *   search(opts)        → row[]            (pattern / tags / taskSlug / maxAge / before / limit)
 *   invalidateWhere(o)  → { success, count } (same filters as search, bulk delete)
 *   configure(opts)     → { success, config } persisted in the `config` table; see CONFIG_KEYS
 *   getConfig()         → { maxEntries, defaultTTL, relevanceThreshold, stalenessThreshold }
 *   getSingleton(path)  → CacheManager  (module-level singleton)
 *   resetSingleton()    → void          (test helper)
 */

const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');
const { SCHEMA_SQL } = require('./schema');

const DEFAULT_TTL = 72 * 60 * 60 * 1000; // 72 hours in ms
const DEFAULT_MAX_ENTRIES = 10_000;

/**
 * Persisted, user-tunable settings. `maxEntries` and `defaultTTL` are applied by this class;
 * `relevanceThreshold` and `stalenessThreshold` are read by the cache orchestrator. Storing all
 * four here (in the `config` table) is what lets `/cache-config --set` survive across the
 * one-process-per-invocation CLI and hook runs.
 */
const CONFIG_KEYS = {
  maxEntries: { default: DEFAULT_MAX_ENTRIES, type: 'integer', min: 100 },
  defaultTTL: { default: DEFAULT_TTL, type: 'integer', min: 60 * 1000 },
  relevanceThreshold: { default: 75, type: 'integer', min: 50, max: 95 },
  stalenessThreshold: { default: 24 * 60 * 60 * 1000, type: 'integer', min: 60 * 1000 }
};

class CacheManager {
  /**
   * @param {string} dbPath - File path or ':memory:' for tests.
   * @param {object} [opts]
   * @param {number} [opts.maxEntries=10000]
   * @param {number} [opts.defaultTTL=72h]
   */
  constructor(dbPath, opts = {}) {
    this.dbPath = dbPath;

    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    if (dbPath !== ':memory:') {
      try { fs.chmodSync(dbPath, 0o600); } catch { /* non-fatal on read-only FS */ }
    }
    this._runSchema();
    this._prepareStatements();

    // Persisted config first, then constructor opts override for this instance only.
    const persisted = this.getConfig();
    this.maxEntries = opts.maxEntries || persisted.maxEntries;
    this.defaultTTL = opts.defaultTTL || persisted.defaultTTL;
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
   * Build the WHERE clause shared by search() and invalidateWhere().
   * @param {object} opts
   * @param {string}   [opts.pattern]         - Substring match against key
   * @param {string[]} [opts.tags]            - agent_type values to include
   * @param {string}   [opts.taskSlug]        - Exact task_slug match
   * @param {number}   [opts.maxAge]          - Only entries younger than this many ms
   * @param {number}   [opts.olderThan]       - Only entries older than this many ms
   * @param {number}   [opts.before]          - Only entries created before this epoch-ms
   * @param {boolean}  [opts.includeExpired]  - Include TTL-expired rows (default false)
   */
  _buildWhere(opts = {}) {
    const { pattern, tags, taskSlug, maxAge, olderThan, before, includeExpired } = opts;
    const now = Date.now();
    const conditions = [];
    const params = [];

    if (!includeExpired) {
      conditions.push('(created_at + ttl) > ?');
      params.push(now);
    }
    if (pattern) {
      conditions.push('key LIKE ?');
      params.push(`%${pattern}%`);
    }
    if (tags && tags.length > 0) {
      conditions.push(`agent_type IN (${tags.map(() => '?').join(',')})`);
      params.push(...tags);
    }
    if (taskSlug) {
      conditions.push('task_slug = ?');
      params.push(taskSlug);
    }
    if (maxAge != null) {
      conditions.push('created_at > ?');
      params.push(now - maxAge);
    }
    if (olderThan != null) {
      conditions.push('created_at < ?');
      params.push(now - olderThan);
    }
    if (before != null) {
      conditions.push('created_at < ?');
      params.push(before);
    }

    return { where: conditions.length ? `WHERE ${conditions.join(' AND ')}` : '', params };
  }

  /**
   * Search entries. See _buildWhere() for filters; plus `limit`.
   * @returns {object[]}
   */
  search(opts = {}) {
    const { limit } = opts;
    const { where, params } = this._buildWhere(opts);
    const sql = `SELECT * FROM cache ${where} ORDER BY accessed_at DESC${limit ? ' LIMIT ?' : ''}`;
    if (limit) params.push(limit);
    return this.db.prepare(sql).all(...params);
  }

  /**
   * Bulk delete entries matching the same filters search() accepts. Expired rows are included
   * by default here (deleting them is never wrong). Refuses to run with no filters at all --
   * use clear() for that, explicitly.
   * @returns {{success: boolean, count: number}}
   */
  invalidateWhere(opts = {}) {
    const { where, params } = this._buildWhere({ includeExpired: true, ...opts });
    if (!where) {
      throw new Error('invalidateWhere() requires at least one filter; use clear() to delete everything');
    }
    const info = this.db.prepare(`DELETE FROM cache ${where}`).run(...params);
    return { success: true, count: info.changes };
  }

  /**
   * Read persisted config, falling back to defaults for unset keys.
   * @returns {{maxEntries: number, defaultTTL: number, relevanceThreshold: number, stalenessThreshold: number}}
   */
  getConfig() {
    const rows = this.db.prepare('SELECT key, value FROM config').all();
    const stored = Object.fromEntries(rows.map(r => [r.key, r.value]));
    const out = {};
    for (const [key, spec] of Object.entries(CONFIG_KEYS)) {
      const raw = stored[key];
      const parsed = raw == null ? NaN : Number(raw);
      out[key] = Number.isFinite(parsed) ? parsed : spec.default;
    }
    return out;
  }

  /**
   * Validate, persist, and apply config. Unknown keys and out-of-range values are rejected as a
   * whole (nothing is written). Pass `null` for a key to reset it to its default.
   * @param {object} opts - subset of CONFIG_KEYS
   * @returns {{success: boolean, config?: object, error?: string}}
   */
  configure(opts = {}) {
    const updates = {};
    for (const [key, value] of Object.entries(opts)) {
      const spec = CONFIG_KEYS[key];
      if (!spec) {
        return { success: false, error: `Unknown config key: ${key}`, validKeys: Object.keys(CONFIG_KEYS) };
      }
      if (value === null) { updates[key] = null; continue; }
      const n = Number(value);
      if (!Number.isInteger(n)) {
        return { success: false, error: `${key} must be an integer` };
      }
      if (spec.min != null && n < spec.min) {
        return { success: false, error: `${key} must be at least ${spec.min}` };
      }
      if (spec.max != null && n > spec.max) {
        return { success: false, error: `${key} must be at most ${spec.max}` };
      }
      updates[key] = n;
    }

    const upsert = this.db.prepare('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)');
    const del = this.db.prepare('DELETE FROM config WHERE key = ?');
    this.db.transaction(() => {
      for (const [key, value] of Object.entries(updates)) {
        if (value === null) del.run(key);
        else upsert.run(key, String(value));
      }
    })();

    const config = this.getConfig();
    this.maxEntries = config.maxEntries;
    this.defaultTTL = config.defaultTTL;
    return { success: true, config };
  }

  /** Reset every persisted config key to its default. */
  resetConfig() {
    const all = Object.fromEntries(Object.keys(CONFIG_KEYS).map(k => [k, null]));
    return this.configure(all);
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
 * @param {string} [dbPath] - Path to cache.db; defaults to ${CLAUDE_PLUGIN_DATA}/cache.db.
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
  if (!process.env.CLAUDE_PLUGIN_DATA) throw new Error('[agent-cache-plugin] CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code, or set CLAUDE_PLUGIN_DATA to this plugin\'s data directory.');
  const allowedBase = path.resolve(process.env.CLAUDE_PLUGIN_DATA);
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
    throw new Error('[agent-cache-plugin] CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code, or set CLAUDE_PLUGIN_DATA to this plugin\'s data directory.');
  }
  const resolved = path.resolve(dataDir);
  fs.mkdirSync(resolved, { recursive: true });
  return path.join(resolved, 'cache.db');
}

module.exports = { CacheManager, getSingleton, resetSingleton, CONFIG_KEYS };
