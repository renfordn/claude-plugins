'use strict';
/**
 * Test Suite: Cache Dashboard
 *
 * Uses real in-memory CacheManager/MetricsTracker instances (matching
 * cache-status.test.js's pattern) so the dashboard is checked against
 * actual computed values, not mocked/fabricated ones.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { CacheDashboard, execute } = require('../commands/cache-dashboard');
const { CacheManager, resetSingleton: resetCache } = require('../skills/sqlite-cache');
const { MetricsTracker, resetSingleton: resetMetrics } = require('../skills/metrics-tracker');

describe('CacheDashboard (SQLite)', () => {
  let cm, mt, dashboard;

  beforeEach(() => {
    resetCache();
    resetMetrics();
    cm = new CacheManager(':memory:');
    mt = new MetricsTracker(':memory:');
    dashboard = new CacheDashboard({ cache: cm, metrics: mt, validator: null });
  });

  afterEach(() => {
    cm.close();
    mt.close();
    resetCache();
    resetMetrics();
  });

  describe('Initialization', () => {
    test('should initialize with injected dependencies', () => {
      expect(dashboard.cache).toBe(cm);
      expect(dashboard.metrics).toBe(mt);
    });

    test('should default to real singletons when no deps are injected', () => {
      const d = new CacheDashboard();
      expect(d.cache).toBeDefined();
      expect(d.metrics).toBeDefined();
      expect(d.validator).toBeDefined();
    });
  });

  describe('getCacheInfo', () => {
    test('should return zeros on an empty cache', async () => {
      const info = await dashboard.getCacheInfo();
      expect(info.totalEntries).toBe(0);
      expect(info.totalHits).toBe(0);
      expect(info.totalMisses).toBe(0);
      expect(info.hitRate).toBe('N/A');
      expect(info.avgTokensSaved).toBe(0);
    });

    test('should compute real hit rate and token savings from cache_events', async () => {
      await mt.recordHit({ cache_key: 'k1', token_count: 100 });
      await mt.recordHit({ cache_key: 'k2', token_count: 200 });
      await mt.recordMiss({ cache_key: 'k3' });

      const info = await dashboard.getCacheInfo();
      expect(info.totalHits).toBe(2);
      expect(info.totalMisses).toBe(1);
      expect(info.hitRate).toBe('66.7');
      expect(info.avgTokensSaved).toBe(150);
      expect(info.totalTokensSaved).toBe(300);
    });

    test('should reflect totalEntries from CacheManager.stats()', async () => {
      cm.store({
        key: 'k1', agent_type: 'agent-tdd', task_slug: 's', output_digest: 'd',
        output_blob: '{}', token_count: 50, ttl: 72 * 60 * 60 * 1000
      });
      const info = await dashboard.getCacheInfo();
      expect(info.totalEntries).toBe(1);
    });

    test('should compute utilization against the real configured maxEntries', async () => {
      const result = cm.configure({ maxEntries: 100 });
      expect(result.success).toBe(true);
      cm.store({
        key: 'k1', agent_type: 'a', task_slug: 's', output_digest: 'd',
        output_blob: '{}', token_count: 10, ttl: 1000 * 60 * 60
      });
      const info = await dashboard.getCacheInfo();
      expect(info.maxEntries).toBe(100);
      expect(info.utilizationPercent).toBe(1);
    });

    test('should not throw when cache manager errors', async () => {
      const brokenCache = { stats: () => { throw new Error('DB error'); } };
      const d = new CacheDashboard({ cache: brokenCache, metrics: mt, validator: null });
      const info = await d.getCacheInfo();
      expect(info.hitRate).toBe('N/A');
      expect(info.totalEntries).toBe(0);
    });
  });

  describe('HTML Generation', () => {
    test('should generate valid HTML', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<html');
      expect(html).toContain('</html>');
    });

    test('should include dashboard title, stat cards, chart containers, and detail panels', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Cache Metrics Dashboard');
      expect(html).toContain('Cache Hit Rate');
      expect(html).toContain('Cached Entries');
      expect(html).toContain('Avg Tokens Saved');
      expect(html).toContain('Hit Rate Trend');
      expect(html).toContain('Tokens Saved Accumulation');
      expect(html).toContain('Request Volume');
      expect(html).toContain('Cache Status');
      expect(html).toContain('Embedding Scorer');
      expect(html).toContain('Recommendations');
      expect(html).toContain('chart.js');
    });

    test('should embed real cache stats in HTML', async () => {
      await mt.recordHit({ cache_key: 'k1', token_count: 100 });
      await mt.recordHit({ cache_key: 'k2', token_count: 200 });
      cm.store({
        key: 'k1', agent_type: 'a', task_slug: 's', output_digest: 'd',
        output_blob: '{}', token_count: 100, ttl: 1000 * 60 * 60
      });

      const html = await dashboard.generateHTML();
      expect(html).toContain('100.0'); // hit rate (2 hits, 0 misses)
      expect(html).toContain('150'); // avg tokens saved per hit
    });

    test('should show latency as "Not tracked" since it is not instrumented', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Not tracked');
      expect(html).toContain('0ms');
    });

    test('should show "No issues detected" when there are no recommendations', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('No issues detected');
    });

    test('should surface a real recommendation when hit rate is low', async () => {
      for (let i = 0; i < 10; i++) await mt.recordMiss({ cache_key: `k${i}` });
      const html = await dashboard.generateHTML();
      expect(html).toContain('relevance-scoring');
    });

    test('should embed hourly chart series computed from cache_events', async () => {
      await mt.recordHit({ cache_key: 'k1', token_count: 42 });
      const html = await dashboard.generateHTML();
      // Cumulative tokens-saved series must contain the real total somewhere.
      expect(html).toMatch(/42/);
    });

    test('should mark embedding scorer as not ready when no validator is injected', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Embedding Scorer ✗');
    });

    test('should mark embedding scorer as ready when validator reports ready', async () => {
      const validator = { getEmbeddingStats: () => ({ ready: true, cacheHits: 5, hitRate: '80.0%' }) };
      const d = new CacheDashboard({ cache: cm, metrics: mt, validator });
      const html = await d.generateHTML();
      expect(html).toContain('Embedding Scorer ✓');
    });

    test('should be responsive on mobile', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('@media (max-width: 768px)');
    });

    test('should include timestamp', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Last updated:');
    });
  });

  describe('Error Handling', () => {
    test('should not throw when cache manager errors', async () => {
      const brokenCache = { stats: () => { throw new Error('DB error'); } };
      const d = new CacheDashboard({ cache: brokenCache, metrics: mt, validator: null });
      const html = await d.generateHTML();
      expect(html).toContain('Cache Metrics Dashboard');
      expect(html).toContain('Degraded');
    });

    test('should not throw when metrics tracker errors', async () => {
      const brokenMetrics = { getHitRate: () => { throw new Error('DB error'); } };
      const d = new CacheDashboard({ cache: cm, metrics: brokenMetrics, validator: null });
      const html = await d.generateHTML();
      expect(html).toContain('Cache Metrics Dashboard');
    });

    test('should not throw when validator errors', async () => {
      const brokenValidator = { getEmbeddingStats: () => { throw new Error('boom'); } };
      const d = new CacheDashboard({ cache: cm, metrics: mt, validator: brokenValidator });
      const html = await d.generateHTML();
      expect(html).toContain('Embedding Scorer');
    });
  });

  describe('HTML Structure', () => {
    test('should have proper semantic HTML structure and styling', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('<meta charset="UTF-8">');
      expect(html).toContain('<style>');
      expect(html).toContain('</style>');
      expect(html).toContain('<script>');
      expect(html).toContain('class="container"');
      expect(html).toContain('class="stats-grid"');
      expect(html).toContain('class="charts-grid"');
      expect(html).toContain('class="details-grid"');
    });
  });

  describe('execute() (CLI wiring)', () => {
    let tmpFile;

    beforeEach(() => {
      tmpFile = path.join(os.tmpdir(), `cache-dashboard-test-${Date.now()}.html`);
    });

    afterEach(() => {
      if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
    });

    test('writes the generated dashboard to --output and reports success', async () => {
      const result = await execute({ output: tmpFile });
      expect(result.status).toBe('success');
      expect(fs.existsSync(tmpFile)).toBe(true);
      const written = fs.readFileSync(tmpFile, 'utf8');
      expect(written).toContain('<!DOCTYPE html>');
    });

    test('reports an error if the file cannot be written', async () => {
      const result = await execute({ output: '/nonexistent-dir/dashboard.html' });
      expect(result.status).toBe('error');
    });
  });
});
