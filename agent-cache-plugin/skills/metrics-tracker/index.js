/**
 * Metrics Tracker Skill
 *
 * Tracks cache performance metrics, token savings, and analytics.
 * Provides hit rate calculations, cost analysis, and optimization recommendations.
 */

class MetricsTracker {
  constructor(options = {}) {
    this.events = []; // Event log
    this.windowDays = options.windowDays || 7;
  }

  /**
   * Record a cache hit
   */
  async recordHit(event) {
    try {
      const record = {
        id: this._generateId(),
        type: 'hit',
        timestamp: event.timestamp || Date.now(),
        cachedEntryId: event.cachedEntryId,
        taskType: event.taskType || 'general',
        agentType: event.agentType,
        tokensSaved: event.tokensSaved || 0,
        relevanceScore: event.relevanceScore || 0,
        retrievalTimeMs: event.retrievalTimeMs || 0
      };

      this.events.push(record);
      return { success: true, eventId: record.id };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Record a cache miss
   */
  async recordMiss(event) {
    try {
      const record = {
        id: this._generateId(),
        type: 'miss',
        timestamp: event.timestamp || Date.now(),
        taskType: event.taskType || 'general',
        agentType: event.agentType,
        query: event.query || ''
      };

      this.events.push(record);
      return { success: true, eventId: record.id };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get cache hit rate
   */
  async getHitRate(timeWindow) {
    const events = this._filterByTimeWindow(this.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit').length;
    const misses = events.filter(e => e.type === 'miss').length;
    const total = hits + misses;

    return {
      hitRate: total > 0 ? hits / total : 0,
      totalHits: hits,
      totalMisses: misses,
      totalQueries: total,
      timeWindow: this._getTimeWindowLabel(timeWindow)
    };
  }

  /**
   * Get token savings metrics
   */
  async getTokenSavings(timeWindow) {
    const events = this._filterByTimeWindow(this.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit');

    const totalTokensSaved = hits.reduce((sum, e) => sum + (e.tokensSaved || 0), 0);
    const avgPerHit = hits.length > 0 ? totalTokensSaved / hits.length : 0;
    const maxSingleSave = hits.length > 0
      ? Math.max(...hits.map(e => e.tokensSaved || 0))
      : 0;

    // Rough cost estimate ($0.003 per 1K tokens for input, $0.006 per 1K output)
    const estimatedCostReduction = totalTokensSaved * 0.000004; // Average $0.004 per token

    return {
      totalTokensSaved,
      avgPerHit: Math.round(avgPerHit),
      maxSingleSave,
      hitCount: hits.length,
      estimatedCostReduction: `$${estimatedCostReduction.toFixed(4)}`,
      timeWindow: this._getTimeWindowLabel(timeWindow)
    };
  }

  /**
   * Get comprehensive performance metrics
   */
  async getPerformanceMetrics(timeWindow) {
    const events = this._filterByTimeWindow(this.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit');

    // Retrieval time percentiles
    const retrievalTimes = hits
      .filter(e => e.retrievalTimeMs)
      .map(e => e.retrievalTimeMs)
      .sort((a, b) => a - b);

    const cacheRetrievalTime = {
      avg: retrievalTimes.length > 0
        ? Math.round(retrievalTimes.reduce((a, b) => a + b, 0) / retrievalTimes.length)
        : 0,
      median: this._percentile(retrievalTimes, 50),
      p95: this._percentile(retrievalTimes, 95),
      p99: this._percentile(retrievalTimes, 99)
    };

    // Task type breakdown
    const taskBreakdown = this._groupByTaskType(events);

    // Agent type breakdown
    const agentBreakdown = this._groupByAgentType(events);

    // Relevance score stats
    const relevanceScores = hits
      .filter(e => e.relevanceScore)
      .map(e => e.relevanceScore);

    return {
      period: this._getTimeWindowLabel(timeWindow),
      totalEvents: events.length,
      cacheRetrievalTime,
      taskBreakdown,
      agentBreakdown,
      relevanceScores: {
        avg: relevanceScores.length > 0
          ? Math.round(relevanceScores.reduce((a, b) => a + b, 0) / relevanceScores.length)
          : 0,
        min: relevanceScores.length > 0 ? Math.min(...relevanceScores) : 0,
        max: relevanceScores.length > 0 ? Math.max(...relevanceScores) : 0
      }
    };
  }

  /**
   * Get optimization recommendations based on metrics
   */
  async getRecommendations() {
    const suggestions = [];
    const allEvents = this.events;

    if (allEvents.length === 0) {
      return { suggestions: [] };
    }

    const hitRate = allEvents.filter(e => e.type === 'hit').length / allEvents.length;

    // Low hit rate
    if (hitRate < 0.1) {
      suggestions.push({
        area: 'relevance-scoring',
        finding: 'Hit rate below 10%',
        impact: 'high',
        action: 'Consider lowering relevance threshold from 75% to 65%, or implement embedding-based scoring'
      });
    }

    // High hit rate but low token savings
    const totalTokensSaved = allEvents
      .filter(e => e.type === 'hit')
      .reduce((sum, e) => sum + (e.tokensSaved || 0), 0);

    if (hitRate > 0.25 && totalTokensSaved < 5000) {
      suggestions.push({
        area: 'cache-value',
        finding: 'Good hit rate but low token savings per hit',
        impact: 'medium',
        action: 'Focus cache on complex tasks (research, design) with longer outputs'
      });
    }

    // Very high cache usage of specific agents
    const agentUsage = this._groupByAgentType(allEvents);
    const topAgent = Object.entries(agentUsage)
      .sort((a, b) => b[1].queries - a[1].queries)[0];

    if (topAgent && topAgent[1].queries > allEvents.length * 0.5) {
      suggestions.push({
        area: 'agent-balance',
        finding: `${topAgent[0]} dominates cache usage (${Math.round((topAgent[1].queries / allEvents.length) * 100)}%)`,
        impact: 'low',
        action: `Monitor for over-fitting; consider task-specific tuning for ${topAgent[0]}`
      });
    }

    // Suggest TTL adjustments
    const recentEvents = allEvents.filter(e =>
      Date.now() - e.timestamp < 7 * 24 * 60 * 60 * 1000
    );

    if (recentEvents.length > 0) {
      suggestions.push({
        area: 'ttl-optimization',
        finding: `Cache has ${recentEvents.length} events in last 7 days`,
        impact: 'medium',
        action: 'Review entry age distribution and adjust TTL by complexity for optimal balance'
      });
    }

    return { suggestions };
  }

  /**
   * Export metrics report
   */
  async exportReport(format = 'json') {
    try {
      const metrics = await this.getPerformanceMetrics();
      const hitRate = await this.getHitRate();
      const savings = await this.getTokenSavings();
      const recommendations = await this.getRecommendations();

      const report = {
        generatedAt: new Date().toISOString(),
        summary: {
          totalEvents: this.events.length,
          hitRate: Math.round(hitRate.hitRate * 100),
          totalTokensSaved: savings.totalTokensSaved,
          estimatedCostSavings: savings.estimatedCostReduction
        },
        metrics,
        recommendations
      };

      if (format === 'json') {
        return {
          success: true,
          report: report,
          format: 'json'
        };
      } else if (format === 'csv') {
        return {
          success: true,
          report: this._toCsv(report),
          format: 'csv'
        };
      } else if (format === 'html') {
        return {
          success: true,
          report: this._toHtml(report),
          format: 'html'
        };
      }

      return { success: false, error: 'Unsupported format' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Record invalidation/cleanup event
   */
  async recordInvalidation(event) {
    try {
      const record = {
        id: this._generateId(),
        type: 'invalidation',
        timestamp: event.timestamp || Date.now(),
        trigger: event.trigger || 'unknown',
        entriesRemoved: event.entriesRemoved || 0,
        entriesUpdated: event.entriesUpdated || 0,
        totalRemaining: event.totalRemaining || 0
      };

      this.events.push(record);
      return { success: true, eventId: record.id };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Clear metrics history
   */
  async clear() {
    const count = this.events.length;
    this.events = [];
    return { count, success: true };
  }

  // Private methods

  _generateId() {
    return `metric-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  _filterByTimeWindow(events, timeWindow) {
    const window = timeWindow || {};
    const start = window.start || Date.now() - (24 * 60 * 60 * 1000); // Default: last 24h
    const end = window.end || Date.now();

    return events.filter(e => e.timestamp >= start && e.timestamp <= end);
  }

  _getTimeWindowLabel(timeWindow) {
    if (!timeWindow) return 'Last 24 hours';
    const duration = (timeWindow.end || Date.now()) - (timeWindow.start || Date.now());
    const days = Math.floor(duration / (24 * 60 * 60 * 1000));
    return days > 1 ? `Last ${days} days` : 'Last 24 hours';
  }

  _percentile(arr, p) {
    if (arr.length === 0) return 0;
    const index = Math.ceil((arr.length * p) / 100) - 1;
    return arr[Math.max(0, index)];
  }

  _groupByTaskType(events) {
    const breakdown = {};

    events.forEach(event => {
      const taskType = event.taskType || 'general';
      if (!breakdown[taskType]) {
        breakdown[taskType] = {
          hits: 0,
          misses: 0,
          queries: 0,
          tokensSaved: 0
        };
      }

      breakdown[taskType].queries++;
      if (event.type === 'hit') {
        breakdown[taskType].hits++;
        breakdown[taskType].tokensSaved += event.tokensSaved || 0;
      } else {
        breakdown[taskType].misses++;
      }
    });

    // Add hitRate to each
    Object.keys(breakdown).forEach(taskType => {
      const data = breakdown[taskType];
      data.hitRate = data.queries > 0 ? data.hits / data.queries : 0;
    });

    return breakdown;
  }

  _groupByAgentType(events) {
    const breakdown = {};

    events.forEach(event => {
      const agentType = event.agentType || 'unknown';
      if (!breakdown[agentType]) {
        breakdown[agentType] = {
          hits: 0,
          misses: 0,
          queries: 0,
          tokensSaved: 0
        };
      }

      breakdown[agentType].queries++;
      if (event.type === 'hit') {
        breakdown[agentType].hits++;
        breakdown[agentType].tokensSaved += event.tokensSaved || 0;
      } else {
        breakdown[agentType].misses++;
      }
    });

    // Add hitRate to each
    Object.keys(breakdown).forEach(agentType => {
      const data = breakdown[agentType];
      data.hitRate = data.queries > 0 ? data.hits / data.queries : 0;
    });

    return breakdown;
  }

  _toCsv(report) {
    const lines = [
      'Metric,Value',
      `Generated At,${report.generatedAt}`,
      `Total Events,${report.summary.totalEvents}`,
      `Hit Rate %,${report.summary.hitRate}`,
      `Tokens Saved,${report.summary.totalTokensSaved}`,
      `Cost Savings,${report.summary.estimatedCostSavings}`
    ];

    return lines.join('\n');
  }

  _toHtml(report) {
    return `
<!DOCTYPE html>
<html>
<head>
  <title>Cache Metrics Report</title>
  <style>
    body { font-family: sans-serif; margin: 20px; }
    h1 { color: #333; }
    table { border-collapse: collapse; width: 100%; margin: 20px 0; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f5f5f5; }
    .metric { font-weight: bold; }
  </style>
</head>
<body>
  <h1>Cache Metrics Report</h1>
  <p>Generated: ${report.generatedAt}</p>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Total Events</td><td>${report.summary.totalEvents}</td></tr>
    <tr><td>Hit Rate</td><td>${report.summary.hitRate}%</td></tr>
    <tr><td>Tokens Saved</td><td>${report.summary.totalTokensSaved}</td></tr>
    <tr><td>Cost Savings</td><td>${report.summary.estimatedCostSavings}</td></tr>
  </table>
</body>
</html>
    `;
  }
}

// Singleton instance
let singletonInstance = null;

// Export as skill
module.exports = {
  name: 'metrics-tracker',
  version: '1.0.0',
  description: 'Performance metrics tracking and analytics skill',

  createTracker: (options) => {
    // Return singleton if no options, otherwise return new instance
    if (!options && singletonInstance) {
      return singletonInstance;
    }
    const tracker = new MetricsTracker(options);
    if (!options) {
      singletonInstance = tracker;
    }
    return tracker;
  },

  getSingleton: () => {
    if (!singletonInstance) {
      singletonInstance = new MetricsTracker();
    }
    return singletonInstance;
  },

  resetSingleton: () => {
    singletonInstance = new MetricsTracker();
    return singletonInstance;
  },

  // Skill methods
  async recordHit(event) {
    const tracker = module.exports.getSingleton();
    return tracker.recordHit(event);
  },

  async recordMiss(event) {
    const tracker = module.exports.getSingleton();
    return tracker.recordMiss(event);
  },

  async getHitRate(timeWindow) {
    const tracker = module.exports.getSingleton();
    return tracker.getHitRate(timeWindow);
  },

  async getTokenSavings(timeWindow) {
    const tracker = module.exports.getSingleton();
    return tracker.getTokenSavings(timeWindow);
  },

  async getPerformanceMetrics(timeWindow) {
    const tracker = module.exports.getSingleton();
    return tracker.getPerformanceMetrics(timeWindow);
  },

  async getRecommendations() {
    const tracker = module.exports.getSingleton();
    return tracker.getRecommendations();
  },

  async exportReport(format) {
    const tracker = module.exports.getSingleton();
    return tracker.exportReport(format);
  },

  // Export class for testing
  MetricsTracker
};
