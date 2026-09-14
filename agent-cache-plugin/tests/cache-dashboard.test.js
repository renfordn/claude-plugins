/**
 * Test Suite: Cache Dashboard
 *
 * Tests for CacheDashboard with mocked cache manager and validator
 */

const CacheDashboard = require('../commands/cache-dashboard');

describe('CacheDashboard', () => {
  let dashboard;
  let mockCacheManager;
  let mockValidator;
  let mockEmbeddingScorer;

  beforeEach(() => {
    mockCacheManager = {
      stats: jest.fn().mockResolvedValue({
        totalEntries: 1250,
        totalHits: 4500,
        totalMisses: 1500,
        avgTokensSaved: 245,
        hitRate: 75
      })
    };

    mockValidator = {
      getEmbeddingStats: jest.fn().mockReturnValue({
        cacheHits: 450,
        cacheMisses: 50,
        apiCalls: 45,
        fallbacks: 5,
        hitRate: '90.0%',
        cacheSize: 495,
        ready: true
      })
    };

    mockEmbeddingScorer = {
      getStats: jest.fn().mockReturnValue({
        cacheHits: 450,
        cacheMisses: 50,
        apiCalls: 45,
        fallbacks: 5,
        hitRate: '90.0%',
        cacheSize: 495,
        ready: true
      })
    };

    dashboard = new CacheDashboard(mockCacheManager, mockValidator, mockEmbeddingScorer);
  });

  describe('Initialization', () => {
    test('should initialize with dependencies', () => {
      expect(dashboard.cacheManager).toBe(mockCacheManager);
      expect(dashboard.validator).toBe(mockValidator);
      expect(dashboard.embeddingScorer).toBe(mockEmbeddingScorer);
    });

    test('should initialize empty metrics', () => {
      expect(dashboard.metrics).toEqual({
        hits: [],
        misses: [],
        latencies: [],
        tokensSaved: [],
        evictions: [],
        timestamps: []
      });
    });
  });

  describe('getCacheInfo', () => {
    test('should fetch cache information', async () => {
      const info = await dashboard.getCacheInfo();

      expect(info.totalEntries).toBe(1250);
      expect(info.totalHits).toBe(4500);
      expect(info.totalMisses).toBe(1500);
      expect(info.hitRate).toBe('75.0');
      expect(info.avgTokensSaved).toBe(245);
    });

    test('should calculate correct hit rate', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({
        totalHits: 800,
        totalMisses: 200,
        totalEntries: 500,
        avgTokensSaved: 250
      });

      const info = await dashboard.getCacheInfo();
      expect(info.hitRate).toBe('80.0');
    });

    test('should return N/A when no stats available', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({
        totalHits: 0,
        totalMisses: 0
      });

      const info = await dashboard.getCacheInfo();
      expect(info.hitRate).toBe('N/A');
    });

    test('should handle missing stats gracefully', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({});

      const info = await dashboard.getCacheInfo();
      expect(info.totalEntries).toBe(0);
      expect(info.totalHits).toBe(0);
      expect(info.totalMisses).toBe(0);
      expect(info.avgTokensSaved).toBe(0);
    });

    test('should handle cache manager error', async () => {
      mockCacheManager.stats.mockRejectedValueOnce(new Error('DB error'));

      const info = await dashboard.getCacheInfo();
      expect(info.hitRate).toBe('N/A');
      expect(info.totalEntries).toBe(0);
      expect(info.avgTokensSaved).toBe(0);
    });

    test('should provide default latency values', async () => {
      const info = await dashboard.getCacheInfo();
      expect(info.avgLatency).toBe('2.5ms');
      expect(info.p95Latency).toBe('25ms');
      expect(info.p99Latency).toBe('45ms');
    });
  });

  describe('HTML Generation', () => {
    test('should generate valid HTML', async () => {
      const html = await dashboard.generateHTML();

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<html');
      expect(html).toContain('</html>');
    });

    test('should include dashboard title', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Cache Metrics Dashboard');
    });

    test('should include stat cards', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Cache Hit Rate');
      expect(html).toContain('Cached Entries');
      expect(html).toContain('Avg Tokens Saved');
    });

    test('should include chart containers', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Hit Rate Trend');
      expect(html).toContain('Tokens Saved Accumulation');
      expect(html).toContain('Request Volume');
      expect(html).toContain('Latency Distribution');
    });

    test('should include detail panels', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Cache Status');
      expect(html).toContain('Embedding Scorer');
      expect(html).toContain('Recommendations');
    });

    test('should include Chart.js library', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('chart.js');
    });

    test('should embed cache stats in HTML', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('75.0%');
      expect(html).toContain('1,250');
      expect(html).toContain('245');
    });

    test('should embed embedding scorer stats', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('90.0%');
      expect(html).toContain('450');
    });

    test('should mark embedding scorer as ready', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Embedding Scorer ✓');
    });

    test('should mark embedding scorer as not ready when disabled', async () => {
      mockValidator.getEmbeddingStats.mockReturnValueOnce({
        ready: false,
        cacheHits: 0
      });

      const html = await dashboard.generateHTML();
      expect(html).toContain('Embedding Scorer ✗');
    });

    test('should be responsive on mobile', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('@media (max-width: 768px)');
    });

    test('should include timestamp', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('Last updated:');
      expect(html).toContain('Dashboard v1.0');
    });
  });

  describe('Chart Data Generation', () => {
    test('should generate hit rate data', () => {
      const data = dashboard._generateChartData();
      expect(data).toHaveProperty('hitRate');
      expect(Array.isArray(data.hitRate)).toBe(true);
      expect(data.hitRate.length).toBe(24);
    });

    test('should generate tokens saved data', () => {
      const data = dashboard._generateChartData();
      expect(data).toHaveProperty('tokensSaved');
      expect(Array.isArray(data.tokensSaved)).toBe(true);
      expect(data.tokensSaved.length).toBe(24);
    });

    test('should generate volume data', () => {
      const data = dashboard._generateChartData();
      expect(data).toHaveProperty('volume');
      expect(Array.isArray(data.volume)).toBe(true);
      expect(data.volume.length).toBe(24);
    });

    test('should generate reasonable hit rate values', () => {
      const data = dashboard._generateChartData();
      data.hitRate.forEach(rate => {
        expect(rate).toBeGreaterThanOrEqual(60);
        expect(rate).toBeLessThanOrEqual(90);
      });
    });

    test('should generate reasonable token values', () => {
      const data = dashboard._generateChartData();
      data.tokensSaved.forEach(tokens => {
        expect(tokens).toBeGreaterThanOrEqual(100);
        expect(tokens).toBeLessThanOrEqual(300);
      });
    });

    test('should generate reasonable volume values', () => {
      const data = dashboard._generateChartData();
      data.volume.forEach(vol => {
        expect(vol).toBeGreaterThanOrEqual(200);
        expect(vol).toBeLessThanOrEqual(700);
      });
    });
  });

  describe('Stats Collection', () => {
    test('should initialize metrics tracking', () => {
      expect(dashboard.metrics.hits).toEqual([]);
      expect(dashboard.metrics.misses).toEqual([]);
      expect(dashboard.metrics.latencies).toEqual([]);
      expect(dashboard.metrics.tokensSaved).toEqual([]);
      expect(dashboard.metrics.timestamps).toEqual([]);
    });

    test('should have metrics structure for all fields', () => {
      const requiredFields = ['hits', 'misses', 'latencies', 'tokensSaved', 'evictions', 'timestamps'];
      requiredFields.forEach(field => {
        expect(dashboard.metrics).toHaveProperty(field);
        expect(Array.isArray(dashboard.metrics[field])).toBe(true);
      });
    });
  });

  describe('Integration', () => {
    test('should call cacheManager.stats()', async () => {
      await dashboard.generateHTML();
      expect(mockCacheManager.stats).toHaveBeenCalled();
    });

    test('should call validator.getEmbeddingStats()', async () => {
      await dashboard.generateHTML();
      expect(mockValidator.getEmbeddingStats).toHaveBeenCalled();
    });

    test('should call _buildCacheInfo()', async () => {
      const spy = jest.spyOn(dashboard, '_buildCacheInfo');
      await dashboard.generateHTML();
      expect(spy).toHaveBeenCalled();
    });

    test('should handle validator returning null stats', async () => {
      mockValidator.getEmbeddingStats.mockReturnValueOnce(null);

      const html = await dashboard.generateHTML();
      expect(html).toContain('Embedding Scorer');
    });

    test('should use validator stats in detail panel', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('450'); // Cache hits from validator
      expect(html).toContain('90.0%'); // Hit rate from validator
    });
  });

  describe('Error Handling', () => {
    test('should handle missing cacheManager gracefully', async () => {
      const d = new CacheDashboard(null, mockValidator, mockEmbeddingScorer);
      // Should not throw when trying to access methods
      expect(d.cacheManager).toBeNull();
    });

    test('should handle missing validator gracefully', async () => {
      const d = new CacheDashboard(mockCacheManager, null, mockEmbeddingScorer);
      // Should initialize successfully
      expect(d.validator).toBeNull();
    });

    test('should use empty stats when validator unavailable', async () => {
      const d = new CacheDashboard(mockCacheManager, null, mockEmbeddingScorer);
      const html = await d.generateHTML();
      expect(html).toContain('Embedding Scorer');
    });

    test('should not throw on cache manager error', async () => {
      mockCacheManager.stats.mockRejectedValueOnce(new Error('Connection lost'));

      const html = await dashboard.generateHTML();
      expect(html).toContain('Cache Metrics Dashboard');
    });
  });

  describe('HTML Structure', () => {
    test('should have proper semantic HTML structure', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('<meta charset="UTF-8">');
      expect(html).toContain('<meta name="viewport"');
      expect(html).toContain('<title>');
    });

    test('should include CSS styling', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('<style>');
      expect(html).toContain('</style>');
    });

    test('should include JavaScript functionality', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('<script>');
      expect(html).toContain('</script>');
    });

    test('should have container divs', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('class="container"');
      expect(html).toContain('class="header"');
      expect(html).toContain('class="stats-grid"');
      expect(html).toContain('class="charts-grid"');
      expect(html).toContain('class="details-grid"');
    });

    test('should use consistent color scheme', async () => {
      const html = await dashboard.generateHTML();
      expect(html).toContain('#667eea'); // Primary
      expect(html).toContain('#764ba2'); // Secondary
      expect(html).toContain('#10b981'); // Success
    });
  });

  describe('Performance', () => {
    test('should generate HTML within reasonable time', async () => {
      const start = Date.now();
      await dashboard.generateHTML();
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(1000);
    });

    test('should not create excessive objects', async () => {
      const before = Object.keys(global).length;
      await dashboard.generateHTML();
      const after = Object.keys(global).length;
      expect(after - before).toBeLessThan(10);
    });
  });

  describe('Data Formatting', () => {
    test('should format hit rate as percentage', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({
        totalHits: 750,
        totalMisses: 250
      });

      const info = await dashboard.getCacheInfo();
      expect(info.hitRate).toMatch(/^\d+\.\d$/);
    });

    test('should format large numbers with commas', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({
        totalHits: 10000,
        totalMisses: 2000,
        totalEntries: 5000
      });

      const html = await dashboard.generateHTML();
      expect(html).toContain('10,000');
      expect(html).toContain('5,000');
    });

    test('should round token values to nearest integer', async () => {
      mockCacheManager.stats.mockResolvedValueOnce({
        totalEntries: 100,
        totalHits: 75,
        totalMisses: 25,
        avgTokensSaved: 245.6789
      });

      const html = await dashboard.generateHTML();
      expect(html).toContain('246');
    });
  });
});
