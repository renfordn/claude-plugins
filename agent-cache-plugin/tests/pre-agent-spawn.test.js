'use strict';
/**
 * M1 re-validation: pre-agent-spawn SQLite read path.
 *
 * Tests confirm the hook reads from SQLite and emits a permissionDecision.
 * If the hook cannot run cleanly (schema bug), tests fail and M1 is marked dropped.
 */

const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const { CacheManager } = require('../skills/sqlite-cache');
const crypto = require('crypto');

const HOOK = path.join(__dirname, '..', 'hooks', 'pre-agent-spawn.js');

function sha256(s) { return crypto.createHash('sha256').update(s).digest('hex'); }
function cacheKey(agentType, taskSlug, inputDigest) {
  return sha256(agentType + '\x00' + taskSlug + '\x00' + inputDigest);
}

function runHook(input, env = {}) {
  const result = spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    env: { ...process.env, ...env }
  });
  let stdout = null;
  try { stdout = JSON.parse(result.stdout.trim()); } catch { stdout = result.stdout; }
  return { stdout, stderr: result.stderr, status: result.status };
}

describe('pre-agent-spawn hook (M1 re-validation)', () => {
  let tmpDir, dbPath;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pre-test-'));
    dbPath = path.join(tmpDir, 'cache.db');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('cache miss: emits permissionDecision=allow passthrough', () => {
    // No DB seeded
    const input = {
      toolName: 'agent-tdd',
      input: { prompt: 'write a test' },
      metadata: { taskSlug: 'test-slug' }
    };
    const { stdout, status } = runHook(input, { CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.permissionDecision).toBe('allow');
    expect(stdout.tempFilePath).toBeUndefined();
  });

  test('cache hit: emits permissionDecision=allow with tempFilePath pointing to cached output', () => {
    const agentType = 'agent-tdd';
    const taskSlug = 'test-slug';
    const inputObj = { prompt: 'write a test' };
    const inputDigest = sha256(JSON.stringify(inputObj));
    const key = cacheKey(agentType, taskSlug, inputDigest);

    // Seed DB with the matching entry
    const cm = new CacheManager(dbPath);
    cm.store({
      key,
      agent_type: agentType,
      task_slug: taskSlug,
      output_digest: 'dig',
      output_blob: JSON.stringify({ result: 'cached!' }),
      token_count: 50,
      ttl: 72 * 60 * 60 * 1000
    });
    cm.close();

    const input = { toolName: agentType, input: inputObj, metadata: { taskSlug } };
    const { stdout, status } = runHook(input, { CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.permissionDecision).toBe('allow');
    expect(stdout.tempFilePath).toBeDefined();
    // Temp file must contain the cached output
    const content = JSON.parse(fs.readFileSync(stdout.tempFilePath, 'utf-8'));
    expect(content.result).toBe('cached!');
    // Cleanup temp file
    try { fs.unlinkSync(stdout.tempFilePath); } catch { /* ignore */ }
  });

  test('exits 0 even on DB error', () => {
    const { stdout, status } = runHook(
      { toolName: 'x', input: {}, metadata: {} },
      { CLAUDE_PLUGIN_DATA: '/nonexistent/totally/bad' }
    );
    expect(status).toBe(0);
    expect(stdout.permissionDecision).toBe('allow');
  });
});
