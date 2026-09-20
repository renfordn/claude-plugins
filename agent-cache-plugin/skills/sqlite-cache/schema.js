/**
 * SQLite schema for agent-cache-plugin.
 * Called once at DB open via runSchema().
 */

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS cache (
  key           TEXT PRIMARY KEY,
  agent_type    TEXT NOT NULL,
  task_slug     TEXT NOT NULL,
  output_digest TEXT NOT NULL,
  output_blob   TEXT NOT NULL,
  decisions     TEXT,
  warnings      TEXT,
  token_count   INTEGER DEFAULT 0,
  created_at    INTEGER NOT NULL,
  accessed_at   INTEGER NOT NULL,
  ttl           INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_accessed ON cache(accessed_at);
CREATE INDEX IF NOT EXISTS idx_cache_created  ON cache(created_at);

CREATE TABLE IF NOT EXISTS cache_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  cache_key   TEXT,
  event_type  TEXT NOT NULL,
  token_count INTEGER DEFAULT 0,
  ts          INTEGER NOT NULL
);
`;

module.exports = { SCHEMA_SQL };
