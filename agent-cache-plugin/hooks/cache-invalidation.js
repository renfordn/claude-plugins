'use strict';
/**
 * Hook: cache-invalidation (PostToolUse)
 *
 * stdin  → any JSON (ignored; no required fields)
 * stdout → { invalidated, entriesRemoved }
 * exit   → always 0
 */

const fs = require('fs');
const path = require('path');

const MAX_ENTRIES = 10_000;
const EVENT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

function resolveDbPath() {
  const d = process.env.CLAUDE_PLUGIN_DATA;
  if (!d) {
    throw new Error('[agent-cache-plugin] CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code, or set CLAUDE_PLUGIN_DATA to this plugin\'s data directory.');
  }
  fs.mkdirSync(d, { recursive: true });
  return path.join(d, 'cache.db');
}

function main() {
  const result = { invalidated: false, entriesRemoved: 0 };
  try {
    const dbPath = resolveDbPath();
    const Database = require('better-sqlite3');
    const db = new Database(dbPath);
    db.pragma('journal_mode = WAL');

    const now = Date.now();

    // 1. TTL expiry
    const { changes: ttlRemoved } = db
      .prepare('DELETE FROM cache WHERE (created_at + ttl) < ?')
      .run(now);

    // 2. LRU trim to MAX_ENTRIES
    const { n: count } = db.prepare('SELECT COUNT(*) AS n FROM cache').get();
    let lruRemoved = 0;
    if (count > MAX_ENTRIES) {
      const excess = count - MAX_ENTRIES;
      const info = db
        .prepare('DELETE FROM cache WHERE key IN (SELECT key FROM cache ORDER BY accessed_at ASC LIMIT ?)')
        .run(excess);
      lruRemoved = info.changes;
    }

    // 3. Prune old cache_events
    db.prepare('DELETE FROM cache_events WHERE ts < ?').run(now - EVENT_TTL_MS);

    db.close();

    result.entriesRemoved = ttlRemoved + lruRemoved;
    result.invalidated = result.entriesRemoved > 0;
  } catch (err) {
    process.stderr.write('[agent-cache-plugin] cache-invalidation error: ' + err.message + '\n');
  }

  process.stdout.write(JSON.stringify(result) + '\n');
  process.exit(0);
}

main();
