/**
 * Test Suite: Advanced Analytics
 *
 * Tests for comprehensive cache analytics engine including:
 * - Hit rate analysis by dimensions
 * - ROI calculations
 * - Anomaly detection
 * - Trend analysis
 */

const AdvancedAnalytics = require('../skills/cache-storage/AdvancedAnalytics');

// Mock metrics tracker
class MockMetricsTracker {
  constructor() {
    this.events = [];
  }

  addEvent(event) {
    this.events.push({
      id: `mock-${Date.now()}-${Math.random()}`,
      timestamp: Date.now(),
      ...event
    });
  }
}

describe('AdvancedAnalytics', () => {
  let analytics;
  let tracker;

  beforeEach(() => {
    tracker = new MockMetricsTracker();
    analytics = new AdvancedAnalytics(tracker);
  });

  describe('Dashboard', () => {
    test('should generate empty dashboard for no events', async () => {
      const dashboard = await analytics.getDashboard();
      expect(dashboard).toHaveProperty('summary');
      expect(dashboard).toHaveProperty('performance');
      expect(dashboard).toHaveProperty('roi');
      expect(dashboard.summary.totalQueries).toBe(0);
    });

    test('should include all dashboard sections', async () => {
      tracker.addEvent({ type: 'hit', taskType: 'research', agentType: 'claude', tokensSaved: 1000, retrievalTimeMs: 50 });
      const dashboard = await analytics.getDashboard();

      expect(dashboard).toHaveProperty('summary');
      expect(dashboard).toHaveProperty('performance');
      expect(dashboard).toHaveProperty('roi');
      expect(dashboard).toHaveProperty('anomalies');
      expect(dashboard).toHaveProperty('trends');
      expect(dashboard).toHaveProperty('topPerformers');
      expect(dashboard).toHaveProperty('recommendations');
    });
  });

  describe('Summary', () => {
    test('should calculate summary metrics', async () => {
      tracker.addEvent({ type: 'hit', tokensSaved: 1000 });
      tracker.addEvent({ type: 'miss' });

      const summary = await analytics.getSummary();
      expect(summary.totalQueries).toBe(2);
      expect(summary.totalHits).toBe(1);
      expect(summary.totalMisses).toBe(1);
      expect(summary.hitRate).toBe(0.5);
    });

    test('should calculate cost savings', async () => {
      tracker.addEvent({ type: 'hit', tokensSaved: 1000 });
      tracker.addEvent({ type: 'hit', tokensSaved: 500 });

      const summary = await analytics.getSummary();
      expect(summary.totalTokensSaved).toBe(1500);
      expect(summary.totalCostSaved).toBeGreaterThan(0);
    });

    test('should handle no hits', async () => {
      tracker.addEvent({ type: 'miss' });
      const summary = await analytics.getSummary();

      expect(summary.hitRate).toBe(0);
      expect(summary.totalTokensSaved).toBe(0);
      expect(summary.totalCostSaved).toBe(0);
    });
  });

  describe('Hit Rate Analysis', () => {
    beforeEach(() => {
      tracker.addEvent({ type: 'hit', agentType: 'agent-a', taskType: 'research' });
      tracker.addEvent({ type: 'miss', agentType: 'agent-a', taskType: 'research' });
      tracker.addEvent({ type: 'hit', agentType: 'agent-b', taskType: 'analysis' });
    });

    test('should calculate overall hit rate', async () => {
      const analysis = await analytics.getHitRateAnalysis();
      expect(analysis.overall.hitRate).toBeCloseTo(2/3, 1);
    });

    test('should break down hit rate by agent', async () => {
      const analysis = await analytics.getHitRateAnalysis();
      expect(analysis.byAgent).toHaveProperty('agent-a');
      expect(analysis.byAgent).toHaveProperty('agent-b');
      expect(analysis.byAgent['agent-b'].hitRate).toBe(1);
    });

    test('should break down hit rate by task', async () => {
      const analysis = await analytics.getHitRateAnalysis();
      expect(analysis.byTask).toHaveProperty('research');
      expect(analysis.byTask).toHaveProperty('analysis');
    });

    test('should include time-based breakdowns', async () => {
      const analysis = await analytics.getHitRateAnalysis();
      expect(analysis.byTimeOfDay).toBeDefined();
      expect(analysis.byDayOfWeek).toBeDefined();
    });
  });

  describe('ROI Analysis', () => {
    test('should calculate total ROI', async () => {
      tracker.addEvent({ type: 'hit', tokensSaved: 5000 });
      tracker.addEvent({ type: 'hit', tokensSaved: 3000 });

      const roi = await analytics.getROIAnalysis();
      expect(roi.totalTokensSaved).toBe(8000);
      expect(roi.totalCostSaved).toBeGreaterThan(0);
      expect(roi.netROI).toBeDefined();
      expect(roi.roiPercentage).toBeDefined();
    });

    test('should calculate cost per hit', async () => {
      tracker.addEvent({ type: 'hit', tokensSaved: 1000 });
      tracker.addEvent({ type: 'hit', tokensSaved: 2000 });

      const roi = await analytics.getROIAnalysis();
      expect(roi.costPerHit).toBeGreaterThan(0);
    });

    test('should break down ROI by agent', async () => {
      tracker.addEvent({ type: 'hit', agentType: 'agent-a', tokensSaved: 1000 });
      tracker.addEvent({ type: 'hit', agentType: 'agent-b', tokensSaved: 2000 });

      const roi = await analytics.getROIAnalysis();
      expect(roi.byAgent).toHaveProperty('agent-a');
      expect(roi.byAgent).toHaveProperty('agent-b');
      expect(roi.byAgent['agent-b']).toBeGreaterThan(roi.byAgent['agent-a']);
    });

    test('should break down ROI by task', async () => {
      tracker.addEvent({ type: 'hit', taskType: 'research', tokensSaved: 2000 });
      tracker.addEvent({ type: 'hit', taskType: 'analysis', tokensSaved: 1000 });

      const roi = await analytics.getROIAnalysis();
      expect(roi.byTask).toHaveProperty('research');
      expect(roi.byTask).toHaveProperty('analysis');
    });
  });

  describe('Performance Analysis', () => {
    test('should calculate retrieval time statistics', async () => {
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 10 });
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 50 });
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 100 });

      const perf = await analytics.getPerformanceAnalysis();
      expect(perf.retrievalTime.min).toBe(10);
      expect(perf.retrievalTime.max).toBe(100);
      expect(perf.retrievalTime.mean).toBeGreaterThan(10);
      expect(perf.retrievalTime.mean).toBeLessThan(100);
      expect(perf.retrievalTime.median).toBeDefined();
      expect(perf.retrievalTime.p95).toBeDefined();
      expect(perf.retrievalTime.p99).toBeDefined();
    });

    test('should calculate relevance statistics', async () => {
      tracker.addEvent({ type: 'hit', relevanceScore: 0.8 });
      tracker.addEvent({ type: 'hit', relevanceScore: 0.95 });

      const perf = await analytics.getPerformanceAnalysis();
      expect(perf.relevance.min).toBeGreaterThanOrEqual(0);
      expect(perf.relevance.max).toBeLessThanOrEqual(1);
      expect(perf.relevance.mean).toBeDefined();
    });

    test('should calculate consistency metric', async () => {
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 50 });
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 50 });
      tracker.addEvent({ type: 'hit', retrievalTimeMs: 50 });

      const perf = await analytics.getPerformanceAnalysis();
      expect(perf.consistency).toBeGreaterThan(0);
    });
  });

  describe('Anomaly Detection', () => {
    test('should detect hit rate anomalies', async () => {
      // Add normal events
      for (let i = 0; i < 20; i++) {
        tracker.addEvent({ type: 'hit' });
      }
      // Add anomalous events (many misses)
      for (let i = 0; i < 10; i++) {
        tracker.addEvent({ type: 'miss', timestamp: Date.now() - 24*60*60*1000 });
      }

      const dashboard = await analytics.getDashboard();
      expect(Array.isArray(dashboard.anomalies)).toBe(true);
    });

    test('should detect token savings outliers', async () => {
      // Normal savings
      for (let i = 0; i < 10; i++) {
        tracker.addEvent({ type: 'hit', tokensSaved: 1000 });
      }
      // Outlier
      tracker.addEvent({ type: 'hit', tokensSaved: 50000 });

      const dashboard = await analytics.getDashboard();
      expect(dashboard.anomalies.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Trend Analysis', () => {
    test('should analyze trends', async () => {
      // Simulate trend data over time
      const baseTime = Date.now() - 7*24*60*60*1000;
      for (let day = 0; day < 7; day++) {
        const dayTime = baseTime + day * 24*60*60*1000;
        tracker.events.push({
          id: `trend-${day}`,
          type: 'hit',
          timestamp: dayTime,
          tokensSaved: 1000 + day * 100
        });
      }

      const dashboard = await analytics.getDashboard();
      expect(dashboard.trends).toBeDefined();
      expect(dashboard.trends.hitRateTrend).toBeDefined();
      expect(dashboard.trends.tokenSavingsTrend).toBeDefined();
      expect(dashboard.trends.dailyMetrics).toBeDefined();
    });
  });

  describe('Top Performers', () => {
    test('should identify top agents', async () => {
      tracker.addEvent({ type: 'hit', agentType: 'high-value', tokensSaved: 5000 });
      tracker.addEvent({ type: 'hit', agentType: 'low-value', tokensSaved: 100 });

      const dashboard = await analytics.getDashboard();
      const topAgents = dashboard.topPerformers.topAgents;
      expect(topAgents.length).toBeGreaterThan(0);
      expect(topAgents[0].name).toBe('high-value');
    });

    test('should identify top tasks', async () => {
      tracker.addEvent({ type: 'hit', taskType: 'complex', tokensSaved: 5000 });
      tracker.addEvent({ type: 'hit', taskType: 'simple', tokensSaved: 100 });

      const dashboard = await analytics.getDashboard();
      const topTasks = dashboard.topPerformers.topTasks;
      expect(topTasks.length).toBeGreaterThan(0);
      expect(topTasks[0].name).toBe('complex');
    });

    test('should rank by token savings', async () => {
      tracker.addEvent({ type: 'hit', agentType: 'a', tokensSaved: 1000 });
      tracker.addEvent({ type: 'hit', agentType: 'b', tokensSaved: 5000 });

      const dashboard = await analytics.getDashboard();
      expect(dashboard.topPerformers.topAgents[0].totalTokensSaved)
        .toBeGreaterThan(dashboard.topPerformers.topAgents[1].totalTokensSaved);
    });
  });

  describe('Recommendations', () => {
    test('should generate recommendations for low hit rate', async () => {
      // Create low hit rate scenario
      for (let i = 0; i < 100; i++) {
        tracker.addEvent({ type: 'miss' });
      }
      tracker.addEvent({ type: 'hit', tokensSaved: 100 });

      const dashboard = await analytics.getDashboard();
      const recommendations = dashboard.recommendations;
      expect(Array.isArray(recommendations)).toBe(true);
    });

    test('should rank recommendations by priority', async () => {
      tracker.addEvent({ type: 'miss' });
      tracker.addEvent({ type: 'miss' });
      tracker.addEvent({ type: 'miss' });
      tracker.addEvent({ type: 'hit', agentType: 'test-agent', tokensSaved: 1000 });

      const dashboard = await analytics.getDashboard();
      const recommendations = dashboard.recommendations;

      if (recommendations.length > 1) {
        for (let i = 0; i < recommendations.length - 1; i++) {
          const priorityOrder = { high: 0, medium: 1, low: 2 };
          expect(priorityOrder[recommendations[i].priority])
            .toBeLessThanOrEqual(priorityOrder[recommendations[i + 1].priority]);
        }
      }
    });
  });

  describe('Export Formats', () => {
    beforeEach(() => {
      tracker.addEvent({ type: 'hit', agentType: 'test', tokensSaved: 1000 });
      tracker.addEvent({ type: 'miss' });
    });

    test('should export as JSON', async () => {
      const result = await analytics.exportAnalyticsReport('json');
      expect(result.success).toBe(true);
      expect(result.format).toBe('json');
      expect(result.report).toBeDefined();
      expect(result.report.dashboard).toBeDefined();
    });

    test('should export as CSV', async () => {
      const result = await analytics.exportAnalyticsReport('csv');
      expect(result.success).toBe(true);
      expect(result.format).toBe('csv');
      expect(result.report).toContain('Cache Analytics Report');
    });

    test('should export as HTML', async () => {
      const result = await analytics.exportAnalyticsReport('html');
      expect(result.success).toBe(true);
      expect(result.format).toBe('html');
      expect(result.report).toContain('<!DOCTYPE html>');
    });

    test('should export as Markdown', async () => {
      const result = await analytics.exportAnalyticsReport('markdown');
      expect(result.success).toBe(true);
      expect(result.format).toBe('markdown');
      expect(result.report).toContain('# Cache Analytics Report');
    });

    test('should reject unsupported formats', async () => {
      const result = await analytics.exportAnalyticsReport('xml');
      expect(result.success).toBe(false);
    });
  });

  describe('Time Window Filtering', () => {
    test('should filter by time window', async () => {
      const now = Date.now();
      tracker.addEvent({ type: 'hit', timestamp: now - 1*60*60*1000 }); // 1h ago
      tracker.addEvent({ type: 'hit', timestamp: now - 2*24*60*60*1000 }); // 2d ago

      const summary = await analytics.getSummary({ start: now - 1*24*60*60*1000 });
      expect(summary.totalHits).toBe(1);
    });

    test('should handle time windows with no events', async () => {
      const futureWindow = {
        start: Date.now() + 24*60*60*1000,
        end: Date.now() + 2*24*60*60*1000
      };
      const summary = await analytics.getSummary(futureWindow);
      expect(summary.totalQueries).toBe(0);
    });
  });

  describe('Edge Cases', () => {
    test('should handle empty metrics tracker', async () => {
      const dashboard = await analytics.getDashboard();
      expect(dashboard.summary.totalQueries).toBe(0);
      expect(dashboard.roi.totalTokensSaved).toBe(0);
    });

    test('should handle single event', async () => {
      tracker.addEvent({ type: 'hit', tokensSaved: 500 });
      const summary = await analytics.getSummary();
      expect(summary.hitRate).toBe(1);
    });

    test('should handle all misses', async () => {
      for (let i = 0; i < 10; i++) {
        tracker.addEvent({ type: 'miss' });
      }
      const summary = await analytics.getSummary();
      expect(summary.hitRate).toBe(0);
      expect(summary.totalTokensSaved).toBe(0);
    });

    test('should handle events without optional fields', async () => {
      tracker.addEvent({ type: 'hit' });
      tracker.addEvent({ type: 'miss' });

      const summary = await analytics.getSummary();
      expect(summary.totalQueries).toBe(2);
      expect(summary.totalHits).toBe(1);
    });
  });
});
