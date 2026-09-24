/**
 * Guard: the test suite must never touch the developer's real plugin data directory.
 *
 * sqlite-cache's getSingleton() and the hooks' resolveDataDir() require CLAUDE_PLUGIN_DATA and
 * throw without it (no guessed fallback). The jest env pins it to a per-worker temp dir so the
 * suite never reads or writes a real ~/.claude/plugins/data/ directory.
 */
const { execFileSync } = require('child_process');
const os = require('os');
const path = require('path');

const REAL_DATA_ROOT = path.join(os.homedir(), '.claude', 'plugins', 'data');

describe('test data-dir isolation', () => {
  test('CLAUDE_PLUGIN_DATA is set and is not the real plugin data dir', () => {
    const dir = process.env.CLAUDE_PLUGIN_DATA;
    expect(dir).toBeTruthy();
    expect(path.resolve(dir).startsWith(path.resolve(REAL_DATA_ROOT))).toBe(false);
    expect(path.resolve(dir).startsWith(path.resolve(os.tmpdir()))).toBe(true);
  });

  test('spawned child processes inherit the throwaway dir', () => {
    // Jest hands each test environment its own copy of process.env, so a value set in
    // setupFiles alone would NOT reach a child. global-setup.js sets it in the worker's real
    // env for exactly this reason; this asserts that keeps working.
    const out = execFileSync('node', ['-p', 'process.env.CLAUDE_PLUGIN_DATA || ""'], {
      encoding: 'utf-8'
    }).trim();
    expect(out).toBeTruthy();
    expect(path.resolve(out).startsWith(path.resolve(REAL_DATA_ROOT))).toBe(false);
  });

  test('a hook run without CLAUDE_PLUGIN_DATA reports a clear error instead of guessing a dir', () => {
    const { spawnSync } = require('child_process');
    const env = { ...process.env };
    delete env.CLAUDE_PLUGIN_DATA;
    const res = spawnSync('node', [path.join(__dirname, '..', 'hooks', 'cache-invalidation.js')], {
      input: '{}', encoding: 'utf-8', env
    });
    expect(res.status).toBe(0);
    expect(res.stderr).toContain('CLAUDE_PLUGIN_DATA is not set');
  });

  test('sqlite-cache resolves its DB inside the throwaway dir', () => {
    const { getSingleton, resetSingleton } = require('../skills/sqlite-cache');
    resetSingleton();
    const cm = getSingleton();
    try {
      expect(path.resolve(cm.dbPath).startsWith(path.resolve(process.env.CLAUDE_PLUGIN_DATA))).toBe(true);
    } finally {
      resetSingleton();
    }
  });
});
