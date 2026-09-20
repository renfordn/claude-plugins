'use strict';
const { MetricsTracker, getSingleton, resetSingleton } = require('../skills/metrics-tracker');

describe('MetricsTracker (SQLite :memory:)', () => {
  let mt;
  beforeEach(() => { mt = new MetricsTracker(':memory:'); });
  afterEach(() => { mt.close(); });

  test('recordHit inserts a hit event; getHitRate returns correct rate', async () => {
    await mt.recordHit({ cache_key: 'k1', token_count: 100, agentType: 'agent-tdd' });
    await mt.recordMiss({ cache_key: 'k2', agentType: 'agent-tdd' });
    const r = await mt.getHitRate();
    expect(r.hitRate).toBeCloseTo(0.5);
    expect(r.totalHits).toBe(1);
    expect(r.totalMisses).toBe(1);
    expect(r.totalQueries).toBe(2);
  });

  test('getTokenSavings sums hit token_counts from DB', async () => {
    await mt.recordHit({ cache_key: 'k1', token_count: 100 });
    await mt.recordHit({ cache_key: 'k2', token_count: 200 });
    const s = await mt.getTokenSavings();
    expect(s.totalTokensSaved).toBe(300);
    expect(s.avgPerHit).toBe(150);
    expect(s.maxSingleSave).toBe(200);
  });

  test('getRecommendations suggests when hitRate < 0.1', async () => {
    // 0 hits, 10 misses → hitRate=0
    for (let i = 0; i < 10; i++) await mt.recordMiss({ cache_key: `k${i}` });
    const r = await mt.getRecommendations();
    const areas = r.suggestions.map(s => s.area);
    expect(areas).toContain('relevance-scoring');
  });

  test('getRecommendations suggests cache-value when hitRate > 0.25 and tokensSaved < 5000', async () => {
    // 5 hits, 5 misses → hitRate=0.5, tokensSaved=10
    for (let i = 0; i < 5; i++) await mt.recordHit({ cache_key: `h${i}`, token_count: 2 });
    for (let i = 0; i < 5; i++) await mt.recordMiss({ cache_key: `m${i}` });
    const r = await mt.getRecommendations();
    const areas = r.suggestions.map(s => s.area);
    expect(areas).toContain('cache-value');
  });

  test('getPerformanceMetrics returns totalEvents', async () => {
    await mt.recordHit({ cache_key: 'k1', token_count: 5 });
    const p = await mt.getPerformanceMetrics();
    expect(p.totalEvents).toBeGreaterThanOrEqual(1);
  });
});

describe('MetricsTracker singleton', () => {
  afterEach(() => resetSingleton());

  test('getSingleton returns same instance', () => {
    const a = getSingleton(':memory:');
    const b = getSingleton(':memory:');
    expect(a).toBe(b);
    a.close();
  });

  test('resetSingleton clears instance', () => {
    const a = getSingleton(':memory:');
    resetSingleton();
    const b = getSingleton(':memory:');
    expect(a).not.toBe(b);
    b.close();
  });
});
