'use strict';
const { CacheManager, getSingleton, resetSingleton } = require('../skills/sqlite-cache');

function makeEntry(overrides = {}) {
  return {
    key: 'k1',
    agent_type: 'agent-tdd',
    task_slug: 'test-slug',
    output_digest: 'abc123',
    output_blob: JSON.stringify({ result: 'hello' }),
    decisions: 'did stuff',
    warnings: null,
    token_count: 42,
    ttl: 72 * 60 * 60 * 1000,
    ...overrides
  };
}

describe('CacheManager (SQLite :memory:)', () => {
  let cm;
  beforeEach(() => { cm = new CacheManager(':memory:'); });
  afterEach(() => { cm.close(); });

  test('store() then retrieve() returns the row', () => {
    cm.store(makeEntry());
    const row = cm.retrieve('k1');
    expect(row).not.toBeNull();
    expect(row.agent_type).toBe('agent-tdd');
    expect(row.output_blob).toBe(JSON.stringify({ result: 'hello' }));
  });

  test('retrieve() returns null for unknown key', () => {
    expect(cm.retrieve('no-such-key')).toBeNull();
  });

  test('retrieve() returns null for expired entry', () => {
    const pastTTL = 1; // 1 ms TTL
    cm.store(makeEntry({ key: 'exp', ttl: pastTTL }));
    // Wait a tick so created_at + ttl < now
    return new Promise(r => setTimeout(r, 5)).then(() => {
      expect(cm.retrieve('exp')).toBeNull();
    });
  });

  test('LRU eviction removes oldest-accessed row when at capacity', () => {
    const small = new CacheManager(':memory:', { maxEntries: 2 });
    small.store(makeEntry({ key: 'a', agent_type: 'a' }));
    small.store(makeEntry({ key: 'b', agent_type: 'b' }));
    // Touch 'b' so 'a' is least recently accessed
    small.retrieve('b');
    // Adding 'c' should evict 'a'
    small.store(makeEntry({ key: 'c', agent_type: 'c' }));
    expect(small.retrieve('a')).toBeNull();
    expect(small.retrieve('c')).not.toBeNull();
    small.close();
  });

  test('stats() returns correct totalEntries and hitCount', () => {
    cm.store(makeEntry({ key: 'x' }));
    cm.retrieve('x'); // hit
    cm.retrieve('missing'); // miss
    const s = cm.stats();
    expect(s.totalEntries).toBe(1);
    expect(s.hitCount).toBe(1);
    expect(s.missCount).toBe(1);
    expect(s.hitRate).toBeCloseTo(0.5);
  });

  test('invalidate() removes the entry', () => {
    cm.store(makeEntry());
    cm.invalidate('k1');
    expect(cm.retrieve('k1')).toBeNull();
  });

  test('enforce() evicts excess entries by LRU', () => {
    cm.store(makeEntry({ key: 'e1' }));
    cm.store(makeEntry({ key: 'e2' }));
    cm.store(makeEntry({ key: 'e3' }));
    const res = cm.enforce({ maxEntries: 1 });
    expect(res.evictedCount).toBe(2);
    expect(cm.stats().totalEntries).toBe(1);
  });
});

describe('CacheManager — getStats()', () => {
  let cm;
  beforeEach(() => { cm = new CacheManager(':memory:'); });
  afterEach(() => { cm.close(); });

  test('getStats() returns same shape as stats()', () => {
    cm.store(makeEntry());
    cm.retrieve('k1');
    const s = cm.stats();
    const gs = cm.getStats();
    expect(gs).toEqual(s);
  });

  test('getStats() on empty cache returns zero counts', () => {
    const gs = cm.getStats();
    expect(gs.totalEntries).toBe(0);
    expect(gs.hitRate).toBe(0);
  });
});

describe('CacheManager — clear()', () => {
  let cm;
  beforeEach(() => { cm = new CacheManager(':memory:'); });
  afterEach(() => { cm.close(); });

  test('clear() removes all entries and returns deletedCount', () => {
    cm.store(makeEntry({ key: 'a' }));
    cm.store(makeEntry({ key: 'b' }));
    const result = cm.clear();
    expect(result.deletedCount).toBe(2);
    expect(cm.stats().totalEntries).toBe(0);
  });

  test('clear() on empty cache returns deletedCount 0', () => {
    expect(cm.clear()).toEqual({ deletedCount: 0 });
  });
});

describe('CacheManager — search()', () => {
  let cm;
  beforeEach(() => {
    cm = new CacheManager(':memory:');
    cm.store(makeEntry({ key: 'tdd:task-a', agent_type: 'agent-tdd', task_slug: 'task-a' }));
    cm.store(makeEntry({ key: 'isdd:task-b', agent_type: 'agent-isdd', task_slug: 'task-b' }));
    cm.store(makeEntry({ key: 'tdd:task-c', agent_type: 'agent-tdd', task_slug: 'task-c' }));
  });
  afterEach(() => { cm.close(); });

  test('search() with no args returns all entries', () => {
    const results = cm.search({});
    expect(results.length).toBe(3);
  });

  test('search() with pattern filters by key prefix', () => {
    const results = cm.search({ pattern: 'tdd' });
    expect(results.length).toBe(2);
    results.forEach(r => expect(r.key).toMatch('tdd'));
  });

  test('search() with tags filters by agent_type', () => {
    const results = cm.search({ tags: ['agent-isdd'] });
    expect(results.length).toBe(1);
    expect(results[0].agent_type).toBe('agent-isdd');
  });

  test('search() with limit caps results', () => {
    const results = cm.search({ limit: 2 });
    expect(results.length).toBe(2);
  });

  test('search() with maxAge excludes old entries', () => {
    return new Promise(r => setTimeout(r, 10)).then(() => {
      const results = cm.search({ maxAge: 1 }); // 1ms — all entries are older
      expect(results.length).toBe(0);
    });
  });

  test('search() returns empty array (not null) when no matches', () => {
    const results = cm.search({ pattern: 'no-match-xyz' });
    expect(Array.isArray(results)).toBe(true);
    expect(results.length).toBe(0);
  });
});

describe('getSingleton / resetSingleton', () => {
  afterEach(() => resetSingleton());

  test('getSingleton returns same instance on repeated calls', () => {
    const a = getSingleton(':memory:');
    const b = getSingleton(':memory:');
    expect(a).toBe(b);
  });

  test('resetSingleton clears the singleton', () => {
    const a = getSingleton(':memory:');
    resetSingleton();
    const b = getSingleton(':memory:');
    expect(a).not.toBe(b);
    b.close();
  });
});

describe('Security — path sanitization', () => {
  // NB: these must not `delete process.env.CLAUDE_PLUGIN_DATA` to force the homedir fallback --
  // that fallback is the developer's real cache, and a later getSingleton() in the same worker
  // would write to it. Both paths below are outside the allowed base either way.
  afterEach(() => {
    resetSingleton();
  });

  test('getSingleton rejects a relative path traversal', () => {
    expect(() => getSingleton('../../../etc/evil')).toThrow(/outside allowed/);
  });

  test('getSingleton rejects an absolute path outside the allowed base', () => {
    expect(() => getSingleton('/tmp/attacker/cache.db')).toThrow(/outside allowed/);
  });

  test('getSingleton accepts :memory: (test sentinel)', () => {
    expect(() => getSingleton(':memory:')).not.toThrow();
    getSingleton(':memory:').close();
  });
});

describe('Security — DB file permissions', () => {
  const fs = require('fs');
  const os = require('os');
  const path = require('path');
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cache-sec-test-'));
    resetSingleton();
    process.env.CLAUDE_PLUGIN_DATA = tmpDir;
  });
  afterEach(() => {
    resetSingleton();
    // setup-after-env.js re-pins CLAUDE_PLUGIN_DATA to this worker's dir; never delete it.
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('DB file is created with mode 0o600', () => {
    const cm = getSingleton();
    cm.store(makeEntry());
    const dbFile = path.join(tmpDir, 'cache.db');
    const mode = fs.statSync(dbFile).mode & 0o777;
    expect(mode).toBe(0o600);
  });
});

describe('CacheManager config persistence', () => {
  let cm;
  beforeEach(() => { cm = new CacheManager(':memory:'); });
  afterEach(() => { cm.close(); });

  test('getConfig() returns defaults on a fresh DB', () => {
    expect(cm.getConfig()).toEqual({
      maxEntries: 10000,
      defaultTTL: 72 * 60 * 60 * 1000,
      relevanceThreshold: 75,
      stalenessThreshold: 24 * 60 * 60 * 1000
    });
  });

  test('configure() persists and applies maxEntries/defaultTTL on the live instance', () => {
    const r = cm.configure({ maxEntries: 200, defaultTTL: 60 * 1000 });
    expect(r.success).toBe(true);
    expect(cm.maxEntries).toBe(200);
    expect(cm.defaultTTL).toBe(60 * 1000);
    expect(cm.getConfig().maxEntries).toBe(200);
  });

  test('configure() rejects unknown keys and out-of-range values atomically', () => {
    expect(cm.configure({ nope: 1 }).success).toBe(false);
    expect(cm.configure({ relevanceThreshold: 10 }).success).toBe(false);
    expect(cm.configure({ maxEntries: 500, relevanceThreshold: 200 }).success).toBe(false);
    expect(cm.getConfig().maxEntries).toBe(10000);
  });

  test('configure() with null resets one key; resetConfig() resets all', () => {
    cm.configure({ maxEntries: 200, relevanceThreshold: 90 });
    cm.configure({ maxEntries: null });
    expect(cm.getConfig().maxEntries).toBe(10000);
    expect(cm.getConfig().relevanceThreshold).toBe(90);
    cm.resetConfig();
    expect(cm.getConfig().relevanceThreshold).toBe(75);
  });

  test('constructor opts override persisted config for that instance only', () => {
    cm.configure({ maxEntries: 200 });
    const other = new CacheManager(':memory:', { maxEntries: 5 });
    expect(other.maxEntries).toBe(5);
    other.close();
    expect(cm.maxEntries).toBe(200);
  });
});

describe('CacheManager.invalidateWhere()', () => {
  let cm;
  beforeEach(() => {
    cm = new CacheManager(':memory:');
    cm.store(makeEntry({ key: 'a1', agent_type: 'A', task_slug: 't1' }));
    cm.store(makeEntry({ key: 'a2', agent_type: 'A', task_slug: 't2' }));
    cm.store(makeEntry({ key: 'b1', agent_type: 'B', task_slug: 't1' }));
  });
  afterEach(() => { cm.close(); });

  test('refuses to run with no filters', () => {
    expect(() => cm.invalidateWhere({})).toThrow(/at least one filter/);
    expect(cm.stats().totalEntries).toBe(3);
  });

  test('filters AND together', () => {
    const r = cm.invalidateWhere({ tags: ['A'], taskSlug: 't1' });
    expect(r.count).toBe(1);
    expect(cm.retrieve('a1')).toBeNull();
    expect(cm.retrieve('a2')).not.toBeNull();
    expect(cm.retrieve('b1')).not.toBeNull();
  });

  test('pattern matches key substring', () => {
    expect(cm.invalidateWhere({ pattern: 'a' }).count).toBe(2);
  });

  test('olderThan / before select by created_at; expired rows are included', async () => {
    cm.store(makeEntry({ key: 'exp', ttl: 1 }));
    await new Promise(r => setTimeout(r, 5));
    expect(cm.search({ pattern: 'exp' })).toHaveLength(0); // hidden from search
    expect(cm.invalidateWhere({ olderThan: 0 }).count).toBe(4); // but deleted here
    expect(cm.invalidateWhere({ before: Date.now() }).count).toBe(0);
  });

  test('search() supports taskSlug', () => {
    expect(cm.search({ taskSlug: 't1' }).map(r => r.key).sort()).toEqual(['a1', 'b1']);
  });
});
