/**
 * Advanced Analytics for Cache Performance
 *
 * Comprehensive analytics engine providing:
 * - Hit rate analysis by agent, task, and time periods
 * - Token savings ROI calculation with configurable cost models
 * - Anomaly detection for unusual cache patterns
 * - Trend analysis and forecasting
 * - Comparative performance metrics
 * - Multi-format export reports (JSON, CSV, HTML, markdown)
 */

class AdvancedAnalytics {
  constructor(metricsTracker, options = {}) {
    this.tracker = metricsTracker;
    this.costModel = options.costModel || {
      inputCostPer1K: 0.003,
      outputCostPer1K: 0.006,
      averageCostPerToken: 0.000004
    };
    this.anomalyThreshold = options.anomalyThreshold || 2.0; // Standard deviations
    this.trendWindowDays = options.trendWindowDays || 7;
  }

  /**
   * Get comprehensive analytics dashboard data
   */
  async getDashboard(timeWindow) {
    const events = this._filterByTimeWindow(this.tracker.events, timeWindow);

    return {
      summary: await this.getSummary(timeWindow),
      performance: await this.getPerformanceAnalysis(timeWindow),
      roi: await this.getROIAnalysis(timeWindow),
      anomalies: this._detectAnomalies(events),
      trends: this._analyzeTrends(events),
      topPerformers: this._getTopPerformers(events),
      recommendations: await this._generateAdvancedRecommendations(events)
    };
  }

  /**
   * Get executive summary
   */
  async getSummary(timeWindow) {
    const events = this._filterByTimeWindow(this.tracker.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit');
    const misses = events.filter(e => e.type === 'miss');

    const totalTokensSaved = hits.reduce((sum, e) => sum + (e.tokensSaved || 0), 0);
    const costSaved = totalTokensSaved * this.costModel.averageCostPerToken;

    return {
      timeWindow: this._getTimeWindowLabel(timeWindow),
      totalQueries: events.length,
      totalHits: hits.length,
      totalMisses: misses.length,
      hitRate: events.length > 0 ? (hits.length / events.length) : 0,
      totalTokensSaved,
      totalCostSaved: parseFloat(costSaved.toFixed(4)),
      avgRetrievalTimeMs: this._calculateAvgRetrievalTime(hits)
    };
  }

  /**
   * Hit rate analysis by multiple dimensions
   */
  async getHitRateAnalysis(timeWindow) {
    const events = this._filterByTimeWindow(this.tracker.events, timeWindow);

    return {
      overall: this._getHitRateStats(events),
      byAgent: this._getHitRateByDimension(events, 'agentType'),
      byTask: this._getHitRateByDimension(events, 'taskType'),
      byTimeOfDay: this._getHitRateByTimeOfDay(events),
      byDayOfWeek: this._getHitRateByDayOfWeek(events)
    };
  }

  /**
   * Token savings and ROI analysis
   */
  async getROIAnalysis(timeWindow) {
    const events = this._filterByTimeWindow(this.tracker.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit');

    const totalTokensSaved = hits.reduce((sum, e) => sum + (e.tokensSaved || 0), 0);
    const totalCostSaved = totalTokensSaved * this.costModel.averageCostPerToken;

    // Estimate storage and overhead costs
    const storageCostPerMonth = 0.50; // Rough estimate for cache storage
    const maintenanceCostPerMonth = 0.20;
    const totalOverhead = (storageCostPerMonth + maintenanceCostPerMonth) / 30 * (timeWindow?.days || 1);

    const netROI = totalCostSaved - totalOverhead;
    const roiPercentage = totalOverhead > 0 ? (netROI / totalOverhead) * 100 : 0;

    return {
      totalTokensSaved,
      totalCostSaved: parseFloat(totalCostSaved.toFixed(4)),
      storageOverhead: parseFloat(storageCostPerMonth.toFixed(4)),
      maintenanceOverhead: parseFloat(maintenanceCostPerMonth.toFixed(4)),
      netROI: parseFloat(netROI.toFixed(4)),
      roiPercentage: Math.round(roiPercentage),
      costPerHit: hits.length > 0 ? parseFloat((totalCostSaved / hits.length).toFixed(4)) : 0,
      byAgent: this._getROIByAgent(hits),
      byTask: this._getROIByTask(hits)
    };
  }

  /**
   * Performance analysis including percentiles
   */
  async getPerformanceAnalysis(timeWindow) {
    const events = this._filterByTimeWindow(this.tracker.events, timeWindow);
    const hits = events.filter(e => e.type === 'hit');

    const retrievalTimes = hits
      .filter(e => e.retrievalTimeMs)
      .map(e => e.retrievalTimeMs)
      .sort((a, b) => a - b);

    const relevanceScores = hits
      .filter(e => e.relevanceScore)
      .map(e => e.relevanceScore);

    return {
      retrievalTime: {
        min: retrievalTimes.length > 0 ? Math.min(...retrievalTimes) : 0,
        max: retrievalTimes.length > 0 ? Math.max(...retrievalTimes) : 0,
        mean: this._calculateMean(retrievalTimes),
        median: this._calculatePercentile(retrievalTimes, 50),
        p95: this._calculatePercentile(retrievalTimes, 95),
        p99: this._calculatePercentile(retrievalTimes, 99)
      },
      relevance: {
        min: relevanceScores.length > 0 ? Math.min(...relevanceScores) : 0,
        max: relevanceScores.length > 0 ? Math.max(...relevanceScores) : 0,
        mean: this._calculateMean(relevanceScores),
        median: this._calculatePercentile(relevanceScores, 50)
      },
      consistency: this._calculateConsistency(retrievalTimes)
    };
  }

  /**
   * Detect anomalies in cache patterns
   */
  _detectAnomalies(events) {
    const anomalies = [];

    if (events.length === 0) return anomalies;

    // Detect unusual hit rate drops
    const dailyHitRates = this._calculateDailyHitRates(events);
    const meanHitRate = dailyHitRates.reduce((a, b) => a + b, 0) / dailyHitRates.length;
    const stdDev = this._calculateStdDev(dailyHitRates, meanHitRate);

    dailyHitRates.forEach((rate, idx) => {
      if (Math.abs(rate - meanHitRate) > stdDev * this.anomalyThreshold) {
        anomalies.push({
          type: 'hit-rate-anomaly',
          severity: 'medium',
          dayIndex: idx,
          value: rate,
          expectedRange: `${Math.max(0, meanHitRate - stdDev * this.anomalyThreshold).toFixed(2)}-${(meanHitRate + stdDev * this.anomalyThreshold).toFixed(2)}`
        });
      }
    });

    // Detect token savings outliers
    const hits = events.filter(e => e.type === 'hit');
    const tokenSavings = hits.map(e => e.tokensSaved || 0);
    if (tokenSavings.length > 0) {
      const meanSavings = tokenSavings.reduce((a, b) => a + b, 0) / tokenSavings.length;
      const savingsStdDev = this._calculateStdDev(tokenSavings, meanSavings);

      tokenSavings.forEach((saving, idx) => {
        if (Math.abs(saving - meanSavings) > savingsStdDev * this.anomalyThreshold) {
          anomalies.push({
            type: 'token-savings-outlier',
            severity: 'low',
            entryIndex: idx,
            value: saving,
            expectedRange: `${Math.max(0, meanSavings - savingsStdDev * this.anomalyThreshold).toFixed(0)}-${(meanSavings + savingsStdDev * this.anomalyThreshold).toFixed(0)}`
          });
        }
      });
    }

    return anomalies;
  }

  /**
   * Analyze trends over time
   */
  _analyzeTrends(events) {
    const dailyMetrics = this._calculateDailyMetrics(events);

    return {
      hitRateTrend: this._calculateTrendDirection(dailyMetrics.map(m => m.hitRate)),
      tokenSavingsTrend: this._calculateTrendDirection(dailyMetrics.map(m => m.tokensSaved)),
      volumeTrend: this._calculateTrendDirection(dailyMetrics.map(m => m.queryCount)),
      dailyMetrics: dailyMetrics.slice(-this.trendWindowDays)
    };
  }

  /**
   * Get top performing agents/tasks
   */
  _getTopPerformers(events) {
    const byAgent = this._groupByDimension(events, 'agentType');
    const byTask = this._groupByDimension(events, 'taskType');

    const agentRankings = Object.entries(byAgent)
      .map(([name, data]) => ({
        name,
        queryCount: data.totalQueries,
        hitRate: data.hits / data.totalQueries,
        totalTokensSaved: data.tokensSaved,
        avgTokensPerHit: data.hits > 0 ? data.tokensSaved / data.hits : 0
      }))
      .sort((a, b) => b.totalTokensSaved - a.totalTokensSaved);

    const taskRankings = Object.entries(byTask)
      .map(([name, data]) => ({
        name,
        queryCount: data.totalQueries,
        hitRate: data.hits / data.totalQueries,
        totalTokensSaved: data.tokensSaved,
        avgTokensPerHit: data.hits > 0 ? data.tokensSaved / data.hits : 0
      }))
      .sort((a, b) => b.totalTokensSaved - a.totalTokensSaved);

    return {
      topAgents: agentRankings.slice(0, 5),
      topTasks: taskRankings.slice(0, 5),
      mostConsistentAgent: agentRankings[0],
      highestValueTask: taskRankings[0]
    };
  }

  /**
   * Export analytics report
   */
  async exportAnalyticsReport(format = 'json', timeWindow) {
    const dashboard = await this.getDashboard(timeWindow);
    const hitRateAnalysis = await this.getHitRateAnalysis(timeWindow);

    const report = {
      generatedAt: new Date().toISOString(),
      timeWindow: this._getTimeWindowLabel(timeWindow),
      dashboard,
      hitRateAnalysis
    };

    switch (format) {
      case 'json':
        return { success: true, report, format: 'json' };
      case 'csv':
        return { success: true, report: this._reportToCsv(report), format: 'csv' };
      case 'html':
        return { success: true, report: this._reportToHtml(report), format: 'html' };
      case 'markdown':
        return { success: true, report: this._reportToMarkdown(report), format: 'markdown' };
      default:
        return { success: false, error: 'Unsupported format' };
    }
  }

  // Private methods

  _filterByTimeWindow(events, timeWindow) {
    if (!timeWindow) {
      return events.slice(-1000); // Default: last 1000 events
    }

    const start = timeWindow.start || Date.now() - (24 * 60 * 60 * 1000);
    const end = timeWindow.end || Date.now();

    return events.filter(e => e.timestamp >= start && e.timestamp <= end);
  }

  _getTimeWindowLabel(timeWindow) {
    if (!timeWindow) return 'Last 1000 events';
    const duration = (timeWindow.end || Date.now()) - (timeWindow.start || Date.now());
    const days = Math.floor(duration / (24 * 60 * 60 * 1000));
    return days > 1 ? `Last ${days} days` : 'Last 24 hours';
  }

  _getHitRateStats(events) {
    const hits = events.filter(e => e.type === 'hit').length;
    const total = events.length;
    return {
      hitRate: total > 0 ? hits / total : 0,
      totalHits: hits,
      totalMisses: total - hits,
      totalQueries: total
    };
  }

  _getHitRateByDimension(events, dimension) {
    const grouped = this._groupByDimension(events, dimension);
    return Object.entries(grouped).reduce((acc, [name, data]) => {
      acc[name] = {
        hitRate: data.totalQueries > 0 ? data.hits / data.totalQueries : 0,
        hits: data.hits,
        misses: data.totalQueries - data.hits,
        totalQueries: data.totalQueries
      };
      return acc;
    }, {});
  }

  _getHitRateByTimeOfDay(events) {
    const byHour = {};
    for (let h = 0; h < 24; h++) {
      byHour[h] = { hits: 0, total: 0 };
    }

    events.forEach(e => {
      const hour = new Date(e.timestamp).getHours();
      byHour[hour].total++;
      if (e.type === 'hit') byHour[hour].hits++;
    });

    return Object.entries(byHour).reduce((acc, [hour, data]) => {
      acc[hour] = data.total > 0 ? data.hits / data.total : 0;
      return acc;
    }, {});
  }

  _getHitRateByDayOfWeek(events) {
    const byDay = {};
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

    days.forEach((day, idx) => {
      byDay[day] = { hits: 0, total: 0 };
    });

    events.forEach(e => {
      const day = days[new Date(e.timestamp).getDay()];
      byDay[day].total++;
      if (e.type === 'hit') byDay[day].hits++;
    });

    return Object.entries(byDay).reduce((acc, [day, data]) => {
      acc[day] = data.total > 0 ? data.hits / data.total : 0;
      return acc;
    }, {});
  }

  _getROIByAgent(hits) {
    const byAgent = {};
    hits.forEach(e => {
      const agent = e.agentType || 'unknown';
      if (!byAgent[agent]) byAgent[agent] = 0;
      byAgent[agent] += e.tokensSaved || 0;
    });

    return Object.entries(byAgent).reduce((acc, [agent, tokens]) => {
      acc[agent] = parseFloat((tokens * this.costModel.averageCostPerToken).toFixed(4));
      return acc;
    }, {});
  }

  _getROIByTask(hits) {
    const byTask = {};
    hits.forEach(e => {
      const task = e.taskType || 'general';
      if (!byTask[task]) byTask[task] = 0;
      byTask[task] += e.tokensSaved || 0;
    });

    return Object.entries(byTask).reduce((acc, [task, tokens]) => {
      acc[task] = parseFloat((tokens * this.costModel.averageCostPerToken).toFixed(4));
      return acc;
    }, {});
  }

  _calculateAvgRetrievalTime(hits) {
    const times = hits.filter(e => e.retrievalTimeMs).map(e => e.retrievalTimeMs);
    return times.length > 0 ? Math.round(times.reduce((a, b) => a + b, 0) / times.length) : 0;
  }

  _calculateMean(arr) {
    return arr.length > 0 ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0;
  }

  _calculatePercentile(arr, p) {
    if (arr.length === 0) return 0;
    const index = Math.ceil((arr.length * p) / 100) - 1;
    return arr[Math.max(0, index)];
  }

  _calculateStdDev(arr, mean) {
    if (arr.length === 0) return 0;
    const variance = arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length;
    return Math.sqrt(variance);
  }

  _calculateConsistency(arr) {
    if (arr.length === 0) return 1; // Perfect consistency for empty
    const mean = this._calculateMean(arr);
    const stdDev = this._calculateStdDev(arr, mean);
    return stdDev > 0 ? mean / stdDev : 1; // Higher is more consistent
  }

  _calculateDailyHitRates(events) {
    const byDay = {};
    events.forEach(e => {
      const day = Math.floor(e.timestamp / (24 * 60 * 60 * 1000));
      if (!byDay[day]) byDay[day] = { hits: 0, total: 0 };
      byDay[day].total++;
      if (e.type === 'hit') byDay[day].hits++;
    });

    return Object.values(byDay).map(d => d.total > 0 ? d.hits / d.total : 0);
  }

  _calculateDailyMetrics(events) {
    const byDay = {};
    events.forEach(e => {
      const day = Math.floor(e.timestamp / (24 * 60 * 60 * 1000));
      if (!byDay[day]) {
        byDay[day] = { hits: 0, total: 0, tokensSaved: 0, timestamp: day * 24 * 60 * 60 * 1000 };
      }
      byDay[day].total++;
      if (e.type === 'hit') {
        byDay[day].hits++;
        byDay[day].tokensSaved += e.tokensSaved || 0;
      }
    });

    return Object.values(byDay)
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(d => ({
        timestamp: d.timestamp,
        hitRate: d.total > 0 ? d.hits / d.total : 0,
        queryCount: d.total,
        tokensSaved: d.tokensSaved
      }));
  }

  _calculateTrendDirection(values) {
    if (values.length < 2) return 'insufficient-data';

    const recent = values.slice(-3);
    const older = values.slice(-6, -3);

    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const olderAvg = older.length > 0 ? older.reduce((a, b) => a + b, 0) / older.length : recentAvg;

    const change = ((recentAvg - olderAvg) / (olderAvg || 1)) * 100;

    if (change > 5) return { direction: 'up', percentChange: Math.round(change) };
    if (change < -5) return { direction: 'down', percentChange: Math.round(change) };
    return { direction: 'stable', percentChange: 0 };
  }

  _groupByDimension(events, dimension) {
    const grouped = {};
    events.forEach(e => {
      const key = e[dimension] || 'unknown';
      if (!grouped[key]) {
        grouped[key] = { hits: 0, totalQueries: 0, tokensSaved: 0 };
      }
      grouped[key].totalQueries++;
      if (e.type === 'hit') {
        grouped[key].hits++;
        grouped[key].tokensSaved += e.tokensSaved || 0;
      }
    });
    return grouped;
  }

  async _generateAdvancedRecommendations(events) {
    const recommendations = [];
    if (events.length === 0) return recommendations;

    const hitRate = events.filter(e => e.type === 'hit').length / events.length;
    const topPerformers = this._getTopPerformers(events);

    // Recommendation 1: Hit rate optimization
    if (hitRate < 0.15) {
      recommendations.push({
        priority: 'high',
        category: 'hit-rate',
        title: 'Improve Cache Hit Rate',
        finding: `Current hit rate is ${(hitRate * 100).toFixed(1)}%, below optimal 25%+`,
        recommendation: 'Expand cache coverage to high-value tasks or reduce relevance threshold',
        expectedImpact: 'Could improve ROI by 200-300%'
      });
    } else if (hitRate > 0.6) {
      recommendations.push({
        priority: 'medium',
        category: 'hit-rate',
        title: 'Hit Rate Plateau Detected',
        finding: `Hit rate is ${(hitRate * 100).toFixed(1)}%, consider optimization limits`,
        recommendation: 'Focus on cache quality over quantity; investigate miss patterns',
        expectedImpact: 'Refine caching strategy for higher ROI per entry'
      });
    }

    // Recommendation 2: Agent-specific optimization
    if (topPerformers.topAgents.length > 0) {
      const topAgent = topPerformers.topAgents[0];
      recommendations.push({
        priority: 'medium',
        category: 'agent-optimization',
        title: `Optimize ${topAgent.name} Agent`,
        finding: `${topAgent.name} is your highest-value agent (${(topAgent.totalTokensSaved || 0).toLocaleString()} tokens saved)`,
        recommendation: 'Prioritize caching for this agent; consider task-specific tuning',
        expectedImpact: `Potential ${((topAgent.hitRate * 100) + 5).toFixed(0)}% hit rate gain`
      });
    }

    // Recommendation 3: Time-based optimization
    const timeAnalysis = await this.getHitRateAnalysis({ start: Date.now() - 7 * 24 * 60 * 60 * 1000 });
    const timeOfDayHitRates = Object.values(timeAnalysis.byTimeOfDay);
    const maxTimeHitRate = Math.max(...timeOfDayHitRates);
    const minTimeHitRate = Math.min(...timeOfDayHitRates);

    if (maxTimeHitRate - minTimeHitRate > 0.2) {
      recommendations.push({
        priority: 'low',
        category: 'time-optimization',
        title: 'Time-Based Cache Strategy',
        finding: `Hit rate varies ${((maxTimeHitRate - minTimeHitRate) * 100).toFixed(0)}% across time periods`,
        recommendation: 'Adjust TTL and prefetching based on peak usage hours',
        expectedImpact: 'Better hit rate consistency across time'
      });
    }

    return recommendations.sort((a, b) => {
      const priorityOrder = { high: 0, medium: 1, low: 2 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
  }

  _reportToCsv(report) {
    const lines = [
      'Cache Analytics Report',
      `Generated: ${report.generatedAt}`,
      `Period: ${report.timeWindow}`,
      '',
      'SUMMARY',
      'Total Queries,Total Hits,Hit Rate,Tokens Saved,Cost Saved',
      `${report.dashboard.summary.totalQueries},${report.dashboard.summary.totalHits},${(report.dashboard.summary.hitRate * 100).toFixed(1)}%,${report.dashboard.summary.totalTokensSaved},$${report.dashboard.summary.totalCostSaved}`
    ];
    return lines.join('\n');
  }

  _reportToMarkdown(report) {
    return `# Cache Analytics Report

Generated: ${report.generatedAt}
Period: ${report.timeWindow}

## Summary
- **Total Queries**: ${report.dashboard.summary.totalQueries}
- **Hit Rate**: ${(report.dashboard.summary.hitRate * 100).toFixed(1)}%
- **Tokens Saved**: ${report.dashboard.summary.totalTokensSaved.toLocaleString()}
- **Cost Saved**: $${report.dashboard.summary.totalCostSaved}
- **Avg Retrieval Time**: ${report.dashboard.summary.avgRetrievalTimeMs}ms

## Performance
- Retrieval Time (avg): ${report.dashboard.performance.retrievalTime.mean}ms
- Retrieval Time (p95): ${report.dashboard.performance.retrievalTime.p95}ms
- Relevance Score (avg): ${report.dashboard.performance.relevance.mean}
`;
  }

  _reportToHtml(report) {
    return `<!DOCTYPE html>
<html>
<head>
  <title>Advanced Cache Analytics Report</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
    .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    h1 { color: #333; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
    h2 { color: #0066cc; margin-top: 30px; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
    .metric { background: #f9f9f9; padding: 15px; border-left: 4px solid #0066cc; border-radius: 4px; }
    .metric-label { color: #666; font-size: 12px; text-transform: uppercase; }
    .metric-value { font-size: 24px; font-weight: bold; color: #333; margin-top: 5px; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #f0f0f0; font-weight: 600; }
    .timestamp { color: #999; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Advanced Cache Analytics Report</h1>
    <p class="timestamp">Generated: ${report.generatedAt}</p>
    <p class="timestamp">Period: ${report.timeWindow}</p>

    <h2>Summary Metrics</h2>
    <div class="summary">
      <div class="metric">
        <div class="metric-label">Total Queries</div>
        <div class="metric-value">${report.dashboard.summary.totalQueries}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Hit Rate</div>
        <div class="metric-value">${(report.dashboard.summary.hitRate * 100).toFixed(1)}%</div>
      </div>
      <div class="metric">
        <div class="metric-label">Tokens Saved</div>
        <div class="metric-value">${report.dashboard.summary.totalTokensSaved.toLocaleString()}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Cost Saved</div>
        <div class="metric-value">$${report.dashboard.summary.totalCostSaved}</div>
      </div>
    </div>
  </div>
</body>
</html>`;
  }
}

module.exports = AdvancedAnalytics;
