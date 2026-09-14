/**
 * SQLite Backend Implementation
 *
 * Persistent storage using SQLite3 database.
 * Provides durability across process restarts.
 * Suitable for single-process deployments and development.
 *
 * Installation: npm install better-sqlite3
 * (or use 'sqlite3' package for async variant)
 */

const StorageBackend = require('./StorageBackend');
const path = require('path');
const fs = require('fs');

let Database;
try {
  Database = require('better-sqlite3');
} catch (err) {
  // Fallback to null if not installed
  Database = null;
}

class SQLiteBackend extends StorageBackend {
  constructor(config = {}) {
    super();
    this.config = config;
    this.dbPath = config.dbPath || path.join(process.cwd(), 'cache.db');
    this.db = null;
    this.ready = false;

    if (!Database) {
      throw new Error(
        'better-sqlite3 is not installed. Install with: npm install better-sqlite3'
      );
    }
  }

  async initialize(config) {
    this.config = config || this.config;
    this.dbPath = this.config.dbPath || this.dbPath;

    try {
      const dir = path.dirname(this.dbPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      this.db = new Database(this.dbPath);
      this.db.pragma('journal_mode = WAL');

      this._createTables();
      this.ready = true;
    } catch (err) {
      throw new Error(`Failed to initialize SQLite backend: ${err.message}`);
    }
  }

  async store(entry) {
    if (!this.ready) throw new Error('Backend not initialized');

    const entryId = entry.id || this._generateId();
    const metadata = JSON.stringify(entry.metadata);

    try {
      const stmt = this.db.prepare(`
        INSERT OR REPLACE INTO cache_entries
        (id, prompt, output, metadata, created_at, accessed_at, access_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      stmt.run(
        entryId,
        entry.prompt,
        entry.output,
        metadata,
        Date.now(),
        Date.now(),
        0
      );

      return { success: true, entryId };
    } catch (err) {
      throw new Error(`Store failed: ${err.message}`);
    }
  }

  async retrieve(entryId) {
    if (!this.ready) throw new Error('Backend not initialized');

    try {
      const stmt = this.db.prepare(`
        SELECT * FROM cache_entries WHERE id = ?
      `);

      const row = stmt.get(entryId);
      if (!row) {
        return null;
      }

      const entry = {
        id: row.id,
        prompt: row.prompt,
        output: row.output,
        metadata: JSON.parse(row.metadata),
        createdAt: row.created_at,
        accessedAt: row.accessed_at,
        accessCount: row.access_count
      };

      if (this._isExpired(entry)) {
        return null;
      }

      const updateStmt = this.db.prepare(`
        UPDATE cache_entries
        SET accessed_at = ?, access_count = access_count + 1
        WHERE id = ?
      `);
      updateStmt.run(Date.now(), entryId);

      entry.accessedAt = Date.now();
      entry.accessCount += 1;

      return entry;
    } catch (err) {
      throw new Error(`Retrieve failed: ${err.message}`);
    }
  }

  async search(criteria = {}) {
    if (!this.ready) throw new Error('Backend not initialized');

    try {
      let query = 'SELECT * FROM cache_entries';
      const params = [];

      if (criteria.agentType || criteria.taskType || criteria.tags) {
        query += ' WHERE';
        const conditions = [];

        if (criteria.agentType) {
          conditions.push("json_extract(metadata, '$.agentType') = ?");
          params.push(criteria.agentType);
        }

        if (criteria.taskType) {
          conditions.push("json_extract(metadata, '$.taskType') = ?");
          params.push(criteria.taskType);
        }

        if (criteria.tags && Array.isArray(criteria.tags)) {
          const tagConditions = criteria.tags.map(() =>
            "json_array_length(json_extract(metadata, '$.tags')) > 0"
          );
          conditions.push(tagConditions.join(' OR '));
        }

        query += ' ' + conditions.join(' AND ');
      }

      const stmt = this.db.prepare(query);
      const rows = params.length > 0 ? stmt.all(...params) : stmt.all();

      const results = [];
      for (const row of rows) {
        const entry = {
          id: row.id,
          prompt: row.prompt,
          output: row.output,
          metadata: JSON.parse(row.metadata),
          createdAt: row.created_at,
          accessedAt: row.accessed_at,
          accessCount: row.access_count
        };

        if (!this._isExpired(entry)) {
          if (this._matchesCriteria(entry, criteria)) {
            results.push(entry);
          }
        }
      }

      return results;
    } catch (err) {
      throw new Error(`Search failed: ${err.message}`);
    }
  }

  async invalidate(idOrCriteria) {
    if (!this.ready) throw new Error('Backend not initialized');

    try {
      if (typeof idOrCriteria === 'string') {
        const stmt = this.db.prepare('DELETE FROM cache_entries WHERE id = ?');
        const result = stmt.run(idOrCriteria);
        return { count: result.changes };
      } else if (typeof idOrCriteria === 'object') {
        let query = 'DELETE FROM cache_entries';
        const params = [];

        if (idOrCriteria.agentType) {
          query += " WHERE json_extract(metadata, '$.agentType') = ?";
          params.push(idOrCriteria.agentType);
        }

        if (idOrCriteria.taskType) {
          query += (params.length > 0 ? ' AND' : ' WHERE') +
            " json_extract(metadata, '$.taskType') = ?";
          params.push(idOrCriteria.taskType);
        }

        const stmt = this.db.prepare(query);
        const result = params.length > 0 ? stmt.run(...params) : stmt.run();
        return { count: result.changes };
      }

      return { count: 0 };
    } catch (err) {
      throw new Error(`Invalidate failed: ${err.message}`);
    }
  }

  async recordMetrics(event) {
    if (!this.ready) throw new Error('Backend not initialized');

    try {
      const stmt = this.db.prepare(`
        INSERT INTO metrics (type, tokens_used, recorded_at, data)
        VALUES (?, ?, ?, ?)
      `);

      stmt.run(
        event.type,
        event.tokensUsed || 0,
        Date.now(),
        JSON.stringify(event)
      );

      return { success: true };
    } catch (err) {
      throw new Error(`Record metrics failed: ${err.message}`);
    }
  }

  async stats() {
    if (!this.ready) throw new Error('Backend not initialized');

    try {
      const countStmt = this.db.prepare(`
        SELECT COUNT(*) as count FROM cache_entries
      `);
      const { count } = countStmt.get();

      const metricsStmt = this.db.prepare(`
        SELECT
          SUM(CASE WHEN type = 'hit' THEN 1 ELSE 0 END) as total_hits,
          SUM(CASE WHEN type = 'miss' THEN 1 ELSE 0 END) as total_misses,
          AVG(tokens_used) as avg_tokens_saved
        FROM metrics
      `);
      const metrics = metricsStmt.get();

      return {
        totalEntries: count,
        totalHits: metrics.total_hits || 0,
        totalMisses: metrics.total_misses || 0,
        avgTokensSaved: metrics.avg_tokens_saved || 0
      };
    } catch (err) {
      throw new Error(`Stats failed: ${err.message}`);
    }
  }

  async configure(options) {
    this.config = { ...this.config, ...options };
  }

  async shutdown() {
    if (this.db) {
      try {
        this.db.close();
      } catch (err) {
        // Ignore close errors
      }
    }
    this.ready = false;
  }

  async isReady() {
    return this.ready;
  }

  // Private helper methods

  _createTables() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS cache_entries (
        id TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        output TEXT NOT NULL,
        metadata TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        accessed_at INTEGER NOT NULL,
        access_count INTEGER DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        recorded_at INTEGER NOT NULL,
        data TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at);
      CREATE INDEX IF NOT EXISTS idx_accessed_at ON cache_entries(accessed_at);
      CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(type);
    `);
  }

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

module.exports = SQLiteBackend;
