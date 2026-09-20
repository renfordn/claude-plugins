'use strict';
const { execFileSync, spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const Database = require('better-sqlite3');

const HOOK = path.join(__dirname, '..', 'hooks', 'post-agent-completion.js');

function run(input, env = {}) {
  const result = spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    env: { ...process.env, ...env }
  });
  let stdout = null;
  try { stdout = JSON.parse(result.stdout.trim()); } catch { stdout = result.stdout; }
  return { stdout, stderr: result.stderr, status: result.status };
}

describe('post-agent-completion hook (SQLite)', () => {
  let tmpDir, dbPath, mdPath;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cache-test-'));
    dbPath = path.join(tmpDir, 'cache.db');
    mdPath = path.join(tmpDir, 'CACHE.md');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('valid input writes to SQLite and appends CACHE.md', () => {
    const input = {
      toolName: 'agent-tdd',
      sessionId: 'sess-1',
      input: { prompt: 'write a test' },
      output: { result: 'done' },
      metadata: { taskSlug: 'write-a-test', inputTokens: 10, outputTokens: 20 }
    };

    const { stdout, status } = run(input, { CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.hookSpecificOutput.hookEventName).toBe('PostToolUse');

    // DB row must exist
    const db = new Database(dbPath, { readonly: true });
    const rows = db.prepare('SELECT * FROM cache').all();
    db.close();
    expect(rows.length).toBe(1);
    expect(rows[0].agent_type).toBe('agent-tdd');

    // CACHE.md must exist and contain structured block
    const md = fs.readFileSync(mdPath, 'utf8');
    expect(md).toMatch(/## \[.*\] agent-tdd \/ write-a-test/);
    expect(md).toMatch(/Key:/);
    expect(md).toMatch(/Tokens:/);
  });

  test('uncacheable input (noCache=true) emits passthrough, writes nothing to DB', () => {
    const input = {
      toolName: 'agent-tdd',
      sessionId: 'sess-2',
      input: { prompt: 'x' },
      output: { result: 'y' },
      metadata: { parameters: { noCache: true } }
    };

    const { stdout, status } = run(input, { CLAUDE_PLUGIN_DATA: tmpDir });
    expect(status).toBe(0);
    expect(stdout.hookSpecificOutput.hookEventName).toBe('PostToolUse');

    // No DB written
    expect(fs.existsSync(dbPath)).toBe(false);
  });

  test('missing toolName emits passthrough and exits 0', () => {
    const { stdout, status } = run(
      { sessionId: 's', input: {}, output: {} },
      { CLAUDE_PLUGIN_DATA: tmpDir }
    );
    expect(status).toBe(0);
    expect(stdout.hookSpecificOutput.hookEventName).toBe('PostToolUse');
  });

  test('DB write error (bad path) emits passthrough and exits 0', () => {
    // Point data dir to a file (not a dir) so mkdirSync succeeds but db open fails
    const badFile = path.join(tmpDir, 'notadir');
    fs.writeFileSync(badFile, 'x');
    const badPath = path.join(badFile, 'cache.db');

    const input = {
      toolName: 'agent-tdd',
      sessionId: 's',
      input: { p: 1 },
      output: { r: 1 },
      metadata: { taskSlug: 'slug' }
    };
    // This will fail to open DB — hook must still exit 0 with passthrough
    const result = spawnSync(process.execPath, [HOOK], {
      input: JSON.stringify(input),
      encoding: 'utf8',
      env: { ...process.env, CLAUDE_PLUGIN_DATA: badFile }
    });
    expect(result.status).toBe(0);
    const out = JSON.parse(result.stdout.trim());
    expect(out.hookSpecificOutput.hookEventName).toBe('PostToolUse');
  });

  test('output blob does not contain raw API key after sanitization', () => {
    const input = {
      toolName: 'agent-tdd',
      sessionId: 'sess-3',
      input: { prompt: 'task' },
      output: { api_key: 'sk-secret-123', result: 'done' },
      metadata: { taskSlug: 'sanitize-check' }
    };

    run(input, { CLAUDE_PLUGIN_DATA: tmpDir });

    const db = new Database(dbPath, { readonly: true });
    const row = db.prepare('SELECT * FROM cache').get();
    db.close();
    expect(row).not.toBeNull();
    const blob = JSON.parse(row.output_blob);
    expect(blob.api_key).toBe('[REDACTED]');
  });
});
