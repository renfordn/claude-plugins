'use strict';
const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const Database = require('better-sqlite3');
const { CacheManager } = require('../skills/sqlite-cache');

const HOOK = path.join(__dirname, '..', 'hooks', 'cache-invalidation.js');

function runHook(env = {}) {
  const result = spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify({ sessionId: 'test-session' }),
    encoding: 'utf8',
    env: { ...process.env, ...env }
  });
  let stdout = null;
  try { stdout = JSON.parse(result.stdout.trim()); } catch { stdout = result.stdout; }
  return { stdout, stderr: result.stderr, status: result.status };
}

describe('cache-invalidation hook (SQLite)', () => {
  let tmpDir, dbPath;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'inv-test-'));
    dbPath = path.join(tmpDir, 'cache.db');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('deletes expired TTL entries and emits entriesRemoved count', () => {
    // Seed DB directly with an expired entry
    const cm = new CacheManager(dbPath);
    const now = Date.now();
    cm.db.prepare(`INSERT INTO cache VALUES (?,?,?,?,?,?,?,?,?,?,?)`).run(
      'expired-key', 'agent', 'slug', 'dig', '{}', null, null, 0,
      now - 10000, now - 10000, 1 // ttl=1ms, already expired
    );
    cm.db.prepare(`INSERT INTO cache VALUES (?,?,?,?,?,?,?,?,?,?,?)`).run(
      'fresh-key', 'agent', 'slug2', 'dig2', '{}', null, null, 0,
      now, now, 72 * 60 * 60 * 1000 // 72h TTL
    );
    cm.close();

    const { stdout, status } = runHook({ CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.invalidated).toBe(true);
    expect(stdout.entriesRemoved).toBeGreaterThanOrEqual(1);

    // Verify expired row gone
    const db = new Database(dbPath, { readonly: true });
    const rows = db.prepare('SELECT key FROM cache').all();
    db.close();
    expect(rows.map(r => r.key)).not.toContain('expired-key');
    expect(rows.map(r => r.key)).toContain('fresh-key');
  });

  test('when nothing to remove, entriesRemoved=0 and invalidated=false', () => {
    // Empty DB
    const cm = new CacheManager(dbPath);
    cm.close();

    const { stdout, status } = runHook({ CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.entriesRemoved).toBe(0);
    expect(stdout.invalidated).toBe(false);
  });

  test('exits 0 even when DB open fails', () => {
    // Point to a non-writable path
    const { stdout, status } = runHook({ CLAUDE_PLUGIN_DATA: '/nonexistent/totally/bad' });
    expect(status).toBe(0);
    // Should emit some JSON
    expect(stdout).toBeTruthy();
  });
});
