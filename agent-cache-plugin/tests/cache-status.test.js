'use strict';
const { CacheStatusCommand } = require('../commands/cache-status');
const { CacheManager, resetSingleton: resetCache } = require('../skills/sqlite-cache');
const { MetricsTracker, resetSingleton: resetMetrics } = require('../skills/metrics-tracker');

describe('CacheStatusCommand (SQLite)', () => {
  let cm, mt, cmd;

  beforeEach(() => {
    resetCache();
    resetMetrics();
    cm = new CacheManager(':memory:');
    mt = new MetricsTracker(':memory:');
    // Inject test instances
    cmd = new CacheStatusCommand({ cache: cm, metrics: mt });
  });

  afterEach(() => {
    cm.close();
    mt.close();
    resetCache();
    resetMetrics();
  });

  test('execute() returns success with totalEntries=0 on empty DB', async () => {
    const result = await cmd.execute({});
    expect(result.status).toBe('success');
    expect(result.metrics.entries).toBe(0);
  });

  test('execute() returns correct entry count after store', async () => {
    cm.store({
      key: 'k1', agent_type: 'agent-tdd', task_slug: 's', output_digest: 'd',
      output_blob: '{}', token_count: 50, ttl: 72 * 60 * 60 * 1000
    });
    const result = await cmd.execute({});
    expect(result.status).toBe('success');
    expect(result.metrics.entries).toBe(1);
  });

  test('execute() hitRate comes from metrics DB', async () => {
    await mt.recordHit({ cache_key: 'k', token_count: 10 });
    await mt.recordMiss({ cache_key: 'k2' });
    const result = await cmd.execute({});
    expect(result.metrics.hitRate).toBeCloseTo(0.5);
  });

  test('report field is a non-empty string', async () => {
    const result = await cmd.execute({});
    expect(typeof result.report).toBe('string');
    expect(result.report.length).toBeGreaterThan(10);
  });

  test('export json returns data field', async () => {
    const result = await cmd.execute({ export: 'json' });
    expect(result.status).toBe('success');
    expect(result.format).toBe('json');
    expect(result.data).toBeDefined();
  });
});
