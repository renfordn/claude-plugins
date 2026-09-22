/**
 * Guard: the test suite must never touch the developer's real plugin data directory.
 *
 * sqlite-cache's getSingleton() and the hooks' resolveDataDir() fall back to
 * ~/.claude/plugin-data/agent-cache-plugin when CLAUDE_PLUGIN_DATA is unset. Before the jest
 * env isolation landed, running the suite appended to that CACHE.md and mutated that cache.db.
 */
const { execFileSync } = require('child_process');
const os = require('os');
const path = require('path');

const REAL_DATA_DIR = path.join(os.homedir(), '.claude', 'plugin-data', 'agent-cache-plugin');

describe('test data-dir isolation', () => {
  test('CLAUDE_PLUGIN_DATA is set and is not the real plugin data dir', () => {
    const dir = process.env.CLAUDE_PLUGIN_DATA;
    expect(dir).toBeTruthy();
    expect(path.resolve(dir)).not.toBe(path.resolve(REAL_DATA_DIR));
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
    expect(path.resolve(out)).not.toBe(path.resolve(REAL_DATA_DIR));
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
