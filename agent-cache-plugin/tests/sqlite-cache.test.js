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
