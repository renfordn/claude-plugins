# Cache Metrics Dashboard

## Overview

The Cache Metrics Dashboard provides real-time visualization of cache performance metrics and health indicators. It displays hit rates, token savings, latency distribution, and recommendations in an interactive web interface.

**Target Audience**: Operators, DevOps engineers, and developers monitoring cache performance  
**Update Frequency**: Auto-updates every 60 seconds  
**Data Source**: Live cache manager and embedding scorer statistics

## Key Metrics

### 1. Cache Hit Rate (%)
- **Definition**: Percentage of cache lookups that found a matching entry
- **Formula**: `totalHits / (totalHits + totalMisses) * 100`
- **Target**: 75-90% (post-optimization)
- **Initial Target**: 60-85% (phase v1.0)
- **Interpretation**:
  - `>85%`: Excellent, cache is very effective
  - `70-85%`: Good, cache is working well
  - `50-70%`: Acceptable, tuning may help
  - `<50%`: Poor, consider TTL or relevance adjustments

### 2. Cached Entries
- **Definition**: Number of active cache entries currently stored
- **Status Indicator**: Shows progress bar relative to cache capacity
- **Target**: 50-90% of max capacity (avoid <30% or >95%)
- **Actions if High** (>95%):
  - Increase max cache size
  - Reduce TTL values
  - Enable more aggressive eviction

### 3. Average Tokens Saved
- **Definition**: Average number of tokens saved per cache hit
- **Calculation**: `totalTokensSaved / totalHits`
- **Target**: 200-500 tokens per hit
- **Example**: If a query normally costs 300 tokens and cache saves 250, value is 250

### 4. Latency Metrics
- **p50 (Median)**: 50% of queries complete faster than this
  - Target: <5ms for memory, <50ms for SQLite
- **p95**: 95% of queries complete faster than this
  - Target: <25ms for memory, <100ms for SQLite
- **p99**: 99% of queries complete faster than this
  - Target: <50ms for memory, <200ms for SQLite

## Dashboard Sections

### Stat Cards (Top Row)
Six cards showing key metrics at a glance:

1. **Cache Hit Rate** - Primary indicator of cache effectiveness
2. **Cached Entries** - Current cache size with visual progress bar
3. **Avg Tokens Saved** - Economic impact per hit
4. **Latency (p50)** - Median retrieval time
5. **Latency (p95)** - 95th percentile
6. **Latency (p99)** - 99th percentile

### Charts (Middle Section)

#### Hit Rate Trend (24h)
- **Chart Type**: Line chart with point markers
- **X-Axis**: Time (last 24 hours)
- **Y-Axis**: Hit rate percentage (0-100%)
- **Interpretation**:
  - Upward trend indicates cache warming
  - Flat or declining trend may indicate cache stale entries
  - Daily patterns show peak usage times

#### Tokens Saved Accumulation
- **Chart Type**: Bar chart
- **X-Axis**: Time intervals (6h ago, 4h ago, 2h ago, Now)
- **Y-Axis**: Cumulative tokens saved
- **Interpretation**:
  - Steep growth indicates high cache effectiveness
  - Flat growth may mean low hit rate or small cached entries

#### Request Volume (by hour)
- **Chart Type**: Stacked bar chart
- **X-Axis**: Hour of day (00-24)
- **Y-Axis**: Request count
- **Datasets**:
  - Hits (green) - successful cache retrievals
  - Misses (amber) - cache misses (new API calls)
- **Interpretation**:
  - Shows traffic patterns and when cache is most effective
  - Wide gap between hits/misses = low hit rate

#### Latency Distribution
- **Chart Type**: Doughnut chart
- **Categories**:
  - `<5ms` (green) - Excellent
  - `5-25ms` (blue) - Good
  - `25-50ms` (amber) - Acceptable
  - `>50ms` (red) - Poor
- **Interpretation**:
  - Mostly green = cache is fast
  - Mostly red = consider backend optimization

### Detail Panels (Bottom Section)

#### Cache Status
Current operational metrics:
- **Total Cache Hits**: Cumulative hit count
- **Total Cache Misses**: Cumulative miss count
- **Active Entries**: Number of stored cache entries
- **Cache Status**: Health badge (Healthy/Degraded/Error)

#### Embedding Scorer Status
Semantic relevance scoring metrics (Phase v1.2):
- **Cache Hits**: Embedding cache hits (fast lookups)
- **Cache Misses**: Embedding cache misses (API calls)
- **API Calls**: Total OpenAI API calls made
- **Hit Rate**: Percentage of embedding cache hits
- **Status**: Ready ✓ or Disabled ✗

**Note**: Embedding scorer is optional. If disabled, falling back to keyword-only scoring.

#### Recommendations
Actionable insights and alerts:
- **Hit Rate Target**: On/Below/Above target range
- **Cache Eviction**: Eviction rate (<5% good, >10% concerning)
- **Memory Usage**: Cache size as % of max capacity
- **Action Required**: Immediate actions needed (if any)

### Common Recommendations

| Finding | Recommendation | Action |
|---------|---|---|
| Hit Rate <50% | Review TTL settings | Increase TTL or review cache keys |
| Hit Rate >90% | Consider larger cache | Increase cache size or entry lifetime |
| High Eviction (>10%) | Cache too small | Increase max cache size |
| Memory >95% | Reaching capacity | Monitor and increase if needed |
| Latency p99 >100ms | Backend slow | Check database/API performance |
| Low Token Savings | Small queries | Review query patterns |

## Using the Dashboard

### Generating the Dashboard

#### Via Code
```javascript
const CacheDashboard = require('./commands/cache-dashboard');
const dashboard = new CacheDashboard(cacheManager, validator, embeddingScorer);

// Generate HTML
const html = await dashboard.generateHTML();
console.log(html);

// Or save to file
const fs = require('fs');
fs.writeFileSync('dashboard.html', html);
```

#### Via CLI
```bash
node commands/cache-dashboard.js --output dashboard.html
# Opens in browser with --open flag
node commands/cache-dashboard.js --open
```

### Viewing the Dashboard

1. **Direct File**: Open `dashboard.html` in a web browser
2. **HTTP Server**: Serve with `python -m http.server` or similar
3. **Integration**: Embed in your monitoring platform (Grafana, etc.)

## Metrics Interpretation Guide

### Healthy Cache Indicators
- Hit Rate: 75-90%
- Cached Entries: 50-80% of capacity
- Latency p95: <25ms
- Eviction Rate: <5%
- No errors in embedding scorer

### Warning Signs
- Hit Rate declining over time
- Eviction rate increasing (>10%)
- Cache hitting capacity limits (>95%)
- High latency p99 (>100ms)
- Embedding API failures spiking

### Performance Tuning

#### If Hit Rate is Low (<50%)
1. Check TTL - may be expiring too quickly
2. Verify cache key generation - may be too unique
3. Review query patterns - may not benefit from caching
4. Increase cache size if memory allows

#### If Latency is High (p99 >100ms)
1. Check storage backend (SQLite slower than memory)
2. Verify database performance
3. Review embedding API latency (if enabled)
4. Check system resources (CPU, I/O)

#### If Cache is Filling Up (>90%)
1. Increase max cache size
2. Reduce TTL to evict stale entries
3. Review if all cached entries are useful
4. Consider more aggressive eviction policy

## Integration with Other Tools

### Export to JSON
```javascript
const stats = dashboard.cacheManager.stats();
const json = JSON.stringify(stats);
// Send to monitoring system
```

### Integration Points
- **Grafana**: Custom JSON data source
- **Datadog**: Custom metrics via API
- **CloudWatch**: Push metrics to AWS
- **Prometheus**: Expose metrics endpoint
- **Slack**: Periodic alerts via webhook

## Real-World Example

### Scenario: Production Cache Performance
```
Hit Rate: 82% (within target)
Cached Entries: 1,250 active entries
Avg Tokens Saved: 245 per hit
Latency p99: 28ms (acceptable)

Findings:
- Hit rate on track
- Eviction rate low (2%)
- Memory usage optimal (65%)
- Action: None required
```

### Scenario: Degraded Performance
```
Hit Rate: 45% (below target)
Cached Entries: 120 active entries
Avg Tokens Saved: 150 per hit
Latency p99: 85ms (high)

Findings:
- Hit rate below target
- Cache may be too small
- Backend queries taking longer
- Action: Increase cache size and TTL, investigate backend
```

## Monitoring Dashboard

### Daily Checklist
- [ ] Hit rate is within target (75-90%)
- [ ] No critical errors in logs
- [ ] Latency remains acceptable (<100ms p99)
- [ ] Cache not filling up (50-90%)

### Weekly Review
- [ ] Trend analysis - hit rate improving?
- [ ] Token savings - meeting targets?
- [ ] Any anomalies or spikes?
- [ ] Adjust TTL/size if needed

### Monthly Analysis
- [ ] Hit rate trends vs. last month
- [ ] ROI of caching (tokens saved × cost)
- [ ] Any configuration changes needed?
- [ ] Plan next optimization phase

## Troubleshooting

### Dashboard Shows No Data
**Cause**: Cache manager not initialized or returning empty stats  
**Solution**:
1. Verify cache manager is running
2. Check that stats() method is implemented
3. Ensure cache has been used (need hits/misses to show data)

### Embedding Scorer Shows ✗
**Cause**: OpenAI API key not configured  
**Solution**: Set `OPENAI_API_KEY` environment variable and restart

### Latency Appears High
**Cause**: Could be storage backend (SQLite slower than Memory)  
**Solution**:
1. Check which backend is active
2. Consider switching to MemoryBackend for performance
3. Check system resource availability

### Charts Not Rendering
**Cause**: Missing Chart.js library  
**Solution**: Ensure dashboard HTML includes CDN link for Chart.js

## Advanced Features

### Custom Metrics
Extend dashboard with application-specific metrics:
```javascript
class ExtendedDashboard extends CacheDashboard {
  async generateHTML() {
    const html = await super.generateHTML();
    // Add custom sections
    return html.replace('</body>', customMetrics + '</body>');
  }
}
```

### Real-time Updates
Implement WebSocket for live updates:
```javascript
// Server
ws.send(JSON.stringify(await dashboard.cacheManager.stats()));

// Client
ws.onmessage = (event) => {
  const stats = JSON.parse(event.data);
  updateCharts(stats);
};
```

### Alerts & Notifications
Configure alerts for specific conditions:
```javascript
const stats = await dashboard.cacheManager.stats();
if (stats.hitRate < 0.50) {
  // Send Slack/email alert
  notifyOps('Low cache hit rate: ' + stats.hitRate);
}
```

## API Reference

### CacheDashboard Constructor
```javascript
new CacheDashboard(cacheManager, validator, embeddingScorer)
```

### Methods
- `async generateHTML()` - Generate complete HTML dashboard
- `async getCacheInfo()` - Get formatted cache statistics
- `_buildCacheInfo(stats)` - Build cache info from raw stats
- `_generateChartData()` - Generate mock chart data for demo

### Properties
- `cacheManager` - Reference to cache manager
- `validator` - Reference to cache validator
- `embeddingScorer` - Reference to embedding scorer
- `metrics` - Accumulated metrics data

## Performance Considerations

### Dashboard Generation
- Generation time: <100ms typical
- HTML size: ~20KB compressed
- Chart.js library: ~35KB (CDN)
- Total page load: <500ms on typical connection

### Browser Rendering
- Desktop Chrome: <50ms
- Mobile Safari: <100ms
- IE11: <200ms (not recommended)

## Roadmap

### v1.1 (In Progress)
- ✅ Basic metrics dashboard
- ✅ 4 core charts
- ⏳ Export to PNG/PDF

### v1.2 (Planned)
- Real-time WebSocket updates
- Custom metric aggregations
- Alert configuration UI
- Integration with external monitoring

### v2.0 (Future)
- Machine learning based recommendations
- Predictive performance alerts
- Cost optimization suggestions
- Multi-tenant dashboards

## See Also
- [PERSISTENCE.md](./PERSISTENCE.md) - Storage backend options
- [EMBEDDING_SCORING.md](./EMBEDDING_SCORING.md) - Semantic relevance scoring
- [API.md](../API.md) - Full plugin API reference
