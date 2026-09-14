---
description: Performance monitoring and optimization tracking with hit rate and token savings analysis
keywords: [metrics, monitoring, performance, tracking, analytics]
version: 1.0.0
---

# Skill: Metrics Tracker

## Overview

Metrics Tracker records cache performance events (hits and misses) and provides analytics on cache effectiveness, token savings, and optimization opportunities. It enables data-driven tuning of cache policies and helps measure the ROI of caching.

## What It Does

- **Records** cache hits and misses with timestamps and metadata
- **Calculates** hit rate, token savings, and cost reduction
- **Analyzes** performance by task type and agent
- **Measures** retrieval latency (average, median, percentiles)
- **Tracks** relevance scores and cache utilization
- **Identifies** optimization opportunities via pattern analysis
- **Exports** reports in JSON, CSV, or HTML format

## Core Operations

### Record Cache Hit
Logs a successful cache hit event with tokens saved and relevance score.

```javascript
await metrics.recordHit({
  cachedEntryId: 'entry-123',
  taskType: 'implementation',
  tokensSaved: 2500,
  relevanceScore: 92,
  agentType: 'agent-tdd'
});
```

### Record Cache Miss
Logs a cache miss event when no suitable cached entry found.

```javascript
await metrics.recordMiss({
  query: 'User prompt or search pattern',
  taskType: 'implementation',
  agentType: 'agent-tdd'
});
```

### Get Hit Rate
Returns hit/miss statistics for a time window (default: last 24 hours).

```javascript
const stats = await metrics.getHitRate({
  start: Date.now() - (24 * 60 * 60 * 1000),
  end: Date.now()
});
console.log(`Hit rate: ${(stats.hitRate * 100).toFixed(1)}% (${stats.totalHits}/${stats.totalQueries})`);
```

### Get Token Savings
Reports total and average token savings from cache hits.

```javascript
const savings = await metrics.getTokenSavings();
console.log(`Total saved: ${savings.totalTokensSaved} tokens`);
console.log(`Estimated cost reduction: $${savings.estimatedCost.toFixed(2)}`);
console.log(`Average per hit: ${savings.avgPerHit} tokens`);
```

### Get Performance Metrics
Returns comprehensive analytics: retrieval latency percentiles, performance breakdown by task type and agent.

```javascript
const perf = await metrics.getPerformanceMetrics();
console.log(`Retrieval time (p95): ${perf.cacheRetrievalTime.p95}ms`);
console.log(`Tasks with highest utilization:`, perf.taskBreakdown);
console.log(`Agent cache effectiveness:`, perf.agentBreakdown);
```

### Get Recommendations
Analyzes patterns and suggests optimizations (impact: high/medium/low).

```javascript
const recs = await metrics.getRecommendations();
recs.suggestions.forEach(s => {
  console.log(`[${s.impact}] ${s.area}: ${s.action}`);
});
// Example: [high] threshold tuning: Increase relevance threshold to 80 (currently 70)
```

### Export Report
Generates a metrics report in JSON, CSV, or HTML format.

```javascript
const report = await metrics.exportReport('html');
console.log(`Report saved to: ${report.reportPath}`);
```

## Metrics Recorded

Each event captures:

- **Type**: "hit" or "miss"
- **Timestamp**: When the event occurred
- **Task type**: Category of work (e.g., "implementation", "testing")
- **Agent type**: Which agent performed the work
- **Tokens saved** (hits only): Tokens avoided by using cache
- **Retrieval time** (hits only): Milliseconds to fetch cached entry
- **Relevance score** (hits only): 0–100 confidence in the match

## Key Metrics Explained

### Hit Rate
Percentage of queries that found usable cache entries. Higher is better (>50% is excellent).

### Token Savings
Total tokens avoided across all cache hits. At ~0.03¢ per 1k tokens, multiply by 0.03/1000 for estimated cost savings.

### Retrieval Time Percentiles
- **p95**: 95th percentile (typical "bad" case)
- **p99**: 99th percentile (worst common case)
- **median**: 50th percentile (typical case)

### Task Breakdown
Hit/miss rates and token savings per task type. Identifies which tasks benefit most from caching.

### Agent Utilization
Which agents use the cache most effectively; identifies agents that may benefit from higher relevance thresholds.

## Usage Patterns

### Pattern 1: Monitor During Session
```javascript
// Every few minutes, check health
const hitRate = await metrics.getHitRate();
if (hitRate.hitRate < 0.3) {
  console.warn('Low hit rate; consider relaxing relevance threshold');
}
```

### Pattern 2: Generate End-of-Session Report
```javascript
const savings = await metrics.getTokenSavings();
const perf = await metrics.getPerformanceMetrics();
console.log(`Session summary: ${savings.totalTokensSaved} tokens saved`);
await metrics.exportReport('html');  // Share with team
```

### Pattern 3: Identify High-Value Optimization
```javascript
const recs = await metrics.getRecommendations();
const highImpact = recs.suggestions.filter(s => s.impact === 'high');
// Act on highest-impact suggestions first
```

## Performance Considerations

- **Recording**: O(1) for each event; negligible overhead
- **Statistics**: O(n) aggregation where n = total events in window
- **Recommendations**: O(n) analysis; runs every 10 seconds
- **Export**: O(n) for large reports; consider time windows for huge datasets

For sessions with >10k events, export reports only for recent time windows (e.g., last 7 days).

## Best Practices

1. **Record consistently**: Log every cache hit and miss for accurate metrics
2. **Use time windows**: Analyze recent data (last 24h–7d) rather than all-time to spot trends
3. **Set thresholds**: Alert if hit rate drops below 30% (may indicate misconfiguration)
4. **Track cost**: Multiply token savings by price per token to justify caching investment
5. **Monitor by task type**: Different tasks have different cache effectiveness; tune per task
6. **Review recommendations**: Run weekly to identify low-hanging optimization fruit
7. **Export reports**: Share weekly metrics with team; use to measure ROI and guide future improvements

## Interpretation Guide

| Hit Rate | Interpretation | Action |
|----------|-----------------|--------|
| <20% | Cache not helping | Lower relevance threshold or improve tagging |
| 20–50% | Moderate benefit | Current setup working; monitor regularly |
| 50–80% | Strong benefit | Excellent; maintain current thresholds |
| >80% | Excellent ROI | May be too permissive; watch for false positives |

| Avg Savings per Hit | Interpretation |
|---------------------|-----------------|
| <100 tokens | Low value hits | Caching saves little; may not be worth latency |
| 100–500 tokens | Moderate value | Worthwhile; typical for simple queries |
| >500 tokens | High value | Excellent ROI; prioritize these task types |

## Integration

- **Orchestration**: Uses metrics to adjust cache strategy
- **Dashboard**: Real-time widget showing hit rate, token savings
- **Audits**: Historical reports for compliance and cost tracking
- **Cost tracking**: Token savings feed into monthly billing estimates
