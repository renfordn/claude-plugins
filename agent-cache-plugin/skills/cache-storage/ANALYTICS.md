# Advanced Analytics & Reporting

## Overview

Comprehensive analytics engine that provides deep insights into cache performance, ROI, and optimization opportunities. Transforms raw metrics into actionable intelligence with anomaly detection, trend analysis, and performance benchmarking.

**Key Features**:
- 📊 Multi-dimensional hit rate analysis (by agent, task, time)
- 💰 Token savings ROI calculation with configurable cost models
- 🚨 Anomaly detection for unusual cache patterns
- 📈 Trend analysis with directional forecasting
- 🏆 Top performer identification and benchmarking
- 💡 AI-powered optimization recommendations
- 📄 Multi-format export (JSON, CSV, HTML, Markdown)

## Installation

AdvancedAnalytics works with existing MetricsTracker:

```bash
npm install @claude/agent-cache-plugin
```

## Quick Start

```javascript
const MetricsTracker = require('./skills/metrics-tracker');
const AdvancedAnalytics = require('./skills/cache-storage/AdvancedAnalytics');

// Get metrics tracker singleton
const tracker = MetricsTracker.getSingleton();

// Create analytics engine
const analytics = new AdvancedAnalytics(tracker, {
  costModel: {
    inputCostPer1K: 0.003,
    outputCostPer1K: 0.006,
    averageCostPerToken: 0.000004
  },
  anomalyThreshold: 2.0,  // Standard deviations
  trendWindowDays: 7
});

// Get comprehensive dashboard
const dashboard = await analytics.getDashboard();

console.log({
  hitRate: dashboard.summary.hitRate,
  costSaved: dashboard.summary.totalCostSaved,
  topAgent: dashboard.topPerformers.topAgents[0],
  anomalies: dashboard.anomalies,
  recommendations: dashboard.recommendations
});
```

## Features

### Dashboard

Complete overview of cache performance:

```javascript
const dashboard = await analytics.getDashboard(timeWindow);

// Returns:
{
  summary: { totalQueries, hitRate, tokensSaved, costSaved, ... },
  performance: { retrievalTime, relevance, consistency },
  roi: { netROI, roiPercentage, byAgent, byTask },
  anomalies: [ ... ],
  trends: { hitRateTrend, tokenSavingsTrend, dailyMetrics },
  topPerformers: { topAgents, topTasks, highestValueTask },
  recommendations: [ ... ]
}
```

### Hit Rate Analysis

Multi-dimensional breakdown of cache effectiveness:

```javascript
const analysis = await analytics.getHitRateAnalysis(timeWindow);

// Includes:
analysis.overall      // Overall hit rate statistics
analysis.byAgent      // Hit rate per agent
analysis.byTask       // Hit rate per task type
analysis.byTimeOfDay  // Hit rate by hour (0-23)
analysis.byDayOfWeek  // Hit rate by day (Sunday-Saturday)
```

Example output:
```javascript
{
  overall: {
    hitRate: 0.45,
    totalHits: 450,
    totalMisses: 550,
    totalQueries: 1000
  },
  byAgent: {
    "research-agent": {
      hitRate: 0.65,
      hits: 130,
      misses: 70,
      totalQueries: 200
    },
    "analysis-agent": {
      hitRate: 0.35,
      hits: 70,
      misses: 130,
      totalQueries: 200
    }
  },
  byTimeOfDay: {
    "9": 0.52,   // 9am has 52% hit rate
    "10": 0.48,
    ...
  }
}
```

### ROI Analysis

Calculate cache value and return on investment:

```javascript
const roi = await analytics.getROIAnalysis(timeWindow);

// Returns:
{
  totalTokensSaved: 125000,
  totalCostSaved: 0.50,          // USD
  storageOverhead: 0.50,          // Monthly cost estimate
  maintenanceOverhead: 0.20,
  netROI: -0.20,                 // ROI after costs
  roiPercentage: -40,            // ROI %
  costPerHit: 0.001,             // Cost per cache hit
  byAgent: { "agent-a": 0.25, "agent-b": 0.15 },
  byTask: { "research": 0.30, "analysis": 0.10 }
}
```

### Performance Analysis

Detailed performance metrics including percentiles:

```javascript
const perf = await analytics.getPerformanceAnalysis(timeWindow);

// Returns:
{
  retrievalTime: {
    min: 5,
    max: 150,
    mean: 45,
    median: 40,
    p95: 120,      // 95th percentile
    p99: 145
  },
  relevance: {
    min: 0.65,
    max: 0.99,
    mean: 0.85,
    median: 0.87
  },
  consistency: 1.8   // Higher = more consistent
}
```

### Anomaly Detection

Automatically identify unusual patterns:

```javascript
const dashboard = await analytics.getDashboard();

dashboard.anomalies.forEach(anomaly => {
  console.log({
    type: anomaly.type,              // 'hit-rate-anomaly' or 'token-savings-outlier'
    severity: anomaly.severity,      // 'low' or 'medium'
    value: anomaly.value,
    expectedRange: anomaly.expectedRange
  });
});
```

Anomaly detection uses statistical methods:
- **Hit Rate Anomalies**: Detects days with unusual hit rate drops/spikes (>2 standard deviations)
- **Token Savings Outliers**: Identifies queries with abnormal token savings

### Trend Analysis

Understand performance direction:

```javascript
const dashboard = await analytics.getDashboard();

const trends = dashboard.trends;

// Returns:
{
  hitRateTrend: {
    direction: 'up',         // 'up', 'down', or 'stable'
    percentChange: 12
  },
  tokenSavingsTrend: {
    direction: 'stable',
    percentChange: 2
  },
  volumeTrend: {
    direction: 'up',
    percentChange: 8
  },
  dailyMetrics: [
    { timestamp, hitRate, queryCount, tokensSaved },
    ...
  ]
}
```

Trend direction calculated using last 3 days vs previous 3 days comparison.

### Top Performers

Identify high-value agents and tasks:

```javascript
const dashboard = await analytics.getDashboard();

dashboard.topPerformers.topAgents.forEach(agent => {
  console.log({
    name: agent.name,
    queryCount: agent.queryCount,
    hitRate: agent.hitRate,
    totalTokensSaved: agent.totalTokensSaved,
    avgTokensPerHit: agent.avgTokensPerHit
  });
});

// Get specific high-value performers
const topAgent = dashboard.topPerformers.mostConsistentAgent;
const topTask = dashboard.topPerformers.highestValueTask;
```

### Smart Recommendations

AI-powered suggestions for optimization:

```javascript
const dashboard = await analytics.getDashboard();

dashboard.recommendations.forEach(rec => {
  console.log({
    priority: rec.priority,      // 'high', 'medium', 'low'
    category: rec.category,      // 'hit-rate', 'agent-optimization', etc
    title: rec.title,
    finding: rec.finding,
    recommendation: rec.recommendation,
    expectedImpact: rec.expectedImpact
  });
});
```

Recommendations generated based on:
1. **Hit Rate Optimization** — Suggests improvements if <15% or plateauing >60%
2. **Agent-Specific Tuning** — Prioritizes highest-value agents
3. **Time-Based Strategy** — Detects peak usage hours with varying hit rates
4. **TTL Optimization** — Suggests TTL adjustments based on entry age distribution

## Export Formats

### JSON Export

Complete structured data for programmatic use:

```javascript
const result = await analytics.exportAnalyticsReport('json');

// result.report contains:
{
  generatedAt: "2024-08-26T...",
  timeWindow: "Last 7 days",
  dashboard: { ... },
  hitRateAnalysis: { ... }
}
```

### CSV Export

Tabular format for spreadsheet tools:

```javascript
const result = await analytics.exportAnalyticsReport('csv');

// result.report contains:
// Cache Analytics Report
// Generated: 2024-08-26T...
// Period: Last 7 days
//
// SUMMARY
// Total Queries,Total Hits,Hit Rate,Tokens Saved,Cost Saved
// 1000,450,45.0%,125000,$0.50
```

### HTML Export

Rich formatted report for viewing in browser:

```javascript
const result = await analytics.exportAnalyticsReport('html');

// Generates styled HTML with:
// - Summary metrics cards
// - Performance statistics
// - Key findings
// - Timestamp and period info
```

### Markdown Export

Export for documentation and sharing:

```javascript
const result = await analytics.exportAnalyticsReport('markdown');

// Generates markdown with:
// - Headings for each section
// - Formatted metrics tables
// - Inline statistics
// - Readable for GitHub, wikis, etc
```

## Configuration

### Custom Cost Model

Adjust pricing for your LLM provider:

```javascript
const analytics = new AdvancedAnalytics(tracker, {
  costModel: {
    inputCostPer1K: 0.003,      // Your input cost per 1K tokens
    outputCostPer1K: 0.006,     // Your output cost per 1K tokens
    averageCostPerToken: 0.000004  // Blended average
  }
});
```

### Anomaly Detection Sensitivity

Configure sensitivity for anomaly detection:

```javascript
const analytics = new AdvancedAnalytics(tracker, {
  anomalyThreshold: 2.0  // Standard deviations (lower = more sensitive)
  // 1.0 = more sensitive (catch more anomalies)
  // 2.0 = moderate (default)
  // 3.0 = less sensitive (only extreme anomalies)
});
```

### Trend Analysis Window

Set how many days to analyze for trends:

```javascript
const analytics = new AdvancedAnalytics(tracker, {
  trendWindowDays: 7  // Analyze last 7 days for trends
});
```

## Time Windows

All analysis methods accept optional `timeWindow` parameter:

```javascript
// Default: last 1000 events
const summary = await analytics.getSummary();

// Last 24 hours
const last24h = await analytics.getSummary({
  start: Date.now() - 24*60*60*1000,
  end: Date.now()
});

// Last 7 days
const last7d = await analytics.getSummary({
  start: Date.now() - 7*24*60*60*1000,
  end: Date.now()
});

// Specific date range
const dateRange = await analytics.getSummary({
  start: new Date('2024-08-01').getTime(),
  end: new Date('2024-08-31').getTime()
});
```

## API Reference

### getDashboard(timeWindow)
Complete analytics dashboard with all sections.
- **Returns**: Dashboard object with summary, performance, ROI, anomalies, trends, recommendations

### getSummary(timeWindow)
Executive summary of cache performance.
- **Returns**: Summary metrics including hit rate, tokens saved, cost savings

### getHitRateAnalysis(timeWindow)
Multi-dimensional hit rate breakdown.
- **Returns**: Hit rates by overall, agent, task, time of day, day of week

### getROIAnalysis(timeWindow)
Token savings and ROI calculation.
- **Returns**: ROI metrics including net ROI, cost per hit, breakdown by agent/task

### getPerformanceAnalysis(timeWindow)
Detailed performance statistics with percentiles.
- **Returns**: Retrieval time stats, relevance metrics, consistency score

### exportAnalyticsReport(format, timeWindow)
Export analytics in multiple formats.
- **Parameters**: format ('json', 'csv', 'html', 'markdown'), timeWindow
- **Returns**: { success, report, format }

## Performance Considerations

- **Analysis Speed**: Large datasets (10K+ events) process in <100ms
- **Memory Usage**: ~1MB per 10K events analyzed
- **Time Window Impact**: Smaller windows (1 day) are faster than large windows (30+ days)

## Best Practices

1. **Review dashboards regularly**
   ```javascript
   // Daily check-in
   const dashboard = await analytics.getDashboard({
     start: Date.now() - 24*60*60*1000
   });
   ```

2. **Act on high-priority recommendations**
   ```javascript
   const recs = dashboard.recommendations.filter(r => r.priority === 'high');
   // Implement top recommendations within 1-2 weeks
   ```

3. **Monitor anomalies**
   ```javascript
   if (dashboard.anomalies.length > 5) {
     // Investigate unusual patterns
     console.warn('Multiple anomalies detected');
   }
   ```

4. **Track ROI trends**
   ```javascript
   // Monthly ROI review
   const monthlyROI = await analytics.getROIAnalysis({
     start: Date.now() - 30*24*60*60*1000
   });
   console.log(`Monthly ROI: ${monthlyROI.roiPercentage}%`);
   ```

5. **Optimize high-value agents/tasks**
   ```javascript
   dashboard.topPerformers.topAgents.forEach(agent => {
     // Allocate more resources/tuning to top performers
   });
   ```

## Troubleshooting

### "No anomalies detected but patterns look unusual"
- Increase anomaly sensitivity: set `anomalyThreshold: 1.5` (lower = more sensitive)
- Review trends manually: `dashboard.trends.dailyMetrics`

### "ROI is negative despite high hit rate"
- Check storage costs: may exceed token savings for small datasets
- Review `byAgent` and `byTask` to find high-value areas to focus on
- Ensure cost model matches your actual LLM pricing

### "Recommendations are generic"
- Ensure sufficient data: >100 events recommended for meaningful analysis
- Check by-dimension breakdowns for nuanced patterns
- Review time-based analysis for usage patterns

## See Also

- [FALLBACK.md](./FALLBACK.md) - Fallback storage backend
- [REDIS.md](./REDIS.md) - Redis backend details
- [API.md](../API.md) - Full cache API reference
- metrics-tracker skill - Basic metrics collection
