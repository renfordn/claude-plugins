/**
 * Cache Dashboard Command
 *
 * Generates an interactive HTML dashboard showing cache metrics — hit rate,
 * token savings, request volume, and recommendations — computed from the
 * `cache_events` table via CacheManager/MetricsTracker, the same sources
 * `/cache-status` reads. Retrieval latency is not instrumented anywhere in
 * this plugin yet, so latency figures are shown as "Not tracked" rather
 * than invented.
 */

const fs = require('fs');
const sqliteCache = require('../skills/sqlite-cache');
const metricsTracker = require('../skills/metrics-tracker');
const cacheValidation = require('../skills/cache-validation');

class CacheDashboard {
  /**
   * @param {object} [deps] - Optional dependency injection for testing.
   * @param {object} [deps.cache]     - CacheManager instance.
   * @param {object} [deps.metrics]   - MetricsTracker instance.
   * @param {object} [deps.validator] - CacheValidator instance (embedding stats).
   */
  constructor(deps = {}) {
    this.cache = deps.cache || sqliteCache.getSingleton();
    this.metrics = deps.metrics || metricsTracker.getSingleton();
    this.validator = deps.validator || cacheValidation.getSingleton();
  }

  /**
   * Generate HTML dashboard
   */
  async generateHTML() {
    let rawStats = {};
    let config = {};
    let statusOk = true;

    try {
      if (this.cache) {
        rawStats = this.cache.stats();
        if (typeof this.cache.getConfig === 'function') config = this.cache.getConfig();
      }
    } catch (err) {
      statusOk = false;
      console.warn('[CacheDashboard] Failed to fetch cache stats:', err.message);
    }

    let hitRate = { hitRate: 0, totalHits: 0, totalMisses: 0, totalQueries: 0 };
    let savings = { totalTokensSaved: 0, avgPerHit: 0 };
    let perf = { cacheRetrievalTime: { avg: 0, median: 0, p95: 0, p99: 0 } };
    let recommendations = { suggestions: [] };
    let hourly = [];

    try {
      if (this.metrics) {
        hitRate = await this.metrics.getHitRate();
        savings = await this.metrics.getTokenSavings();
        perf = await this.metrics.getPerformanceMetrics();
        recommendations = await this.metrics.getRecommendations();
        hourly = await this.metrics.getHourlyBreakdown(24);
      }
    } catch (err) {
      statusOk = false;
      console.warn('[CacheDashboard] Failed to fetch metrics:', err.message);
    }

    let validatorStats = {};
    try {
      if (this.validator) validatorStats = this.validator.getEmbeddingStats();
    } catch (err) {
      console.warn('[CacheDashboard] Failed to fetch embedding stats:', err.message);
    }

    const cacheInfo = this._buildCacheInfo(rawStats, hitRate, savings, config);

    return this._buildHTMLPage(cacheInfo, perf, recommendations, validatorStats || {}, hourly, statusOk);
  }

  /**
   * Build cache info from real stats/hitRate/savings.
   */
  _buildCacheInfo(rawStats, hitRate, savings, config) {
    const totalEntries = (rawStats && rawStats.totalEntries) || 0;
    const totalHits = (hitRate && hitRate.totalHits) || 0;
    const totalMisses = (hitRate && hitRate.totalMisses) || 0;
    const totalQueries = (hitRate && hitRate.totalQueries) || 0;
    const maxEntries = (config && config.maxEntries) || 0;

    return {
      totalEntries,
      totalHits,
      totalMisses,
      totalQueries,
      hitRate: totalQueries > 0 ? (hitRate.hitRate * 100).toFixed(1) : 'N/A',
      avgTokensSaved: (savings && savings.avgPerHit) || 0,
      totalTokensSaved: (savings && savings.totalTokensSaved) || 0,
      maxEntries,
      utilizationPercent: maxEntries > 0 ? Math.min(100, Math.round((totalEntries / maxEntries) * 100)) : 0
    };
  }

  /**
   * Get cache information (legacy, for backward compatibility)
   */
  async getCacheInfo() {
    try {
      const rawStats = this.cache.stats();
      const config = typeof this.cache.getConfig === 'function' ? this.cache.getConfig() : {};
      const hitRate = await this.metrics.getHitRate();
      const savings = await this.metrics.getTokenSavings();
      return this._buildCacheInfo(rawStats, hitRate, savings, config);
    } catch (err) {
      return this._buildCacheInfo({}, { totalHits: 0, totalMisses: 0, totalQueries: 0 }, {}, {});
    }
  }

  _latencyBadge(ms) {
    if (!ms || ms <= 0) return { cls: 'badge-info', text: 'Not tracked' };
    if (ms < 5) return { cls: 'badge-success', text: 'Excellent' };
    if (ms < 25) return { cls: 'badge-success', text: 'Good' };
    if (ms < 50) return { cls: 'badge-warning', text: 'Acceptable' };
    return { cls: 'badge-warning', text: 'Slow' };
  }

  /**
   * Turn hourly cache_events buckets into Chart.js-ready series.
   */
  _buildChartSeries(hourly) {
    const labels = hourly.map((h) => {
      const d = new Date(h.hourStart);
      return `${String(d.getHours()).padStart(2, '0')}:00`;
    });
    const hitRateSeries = hourly.map((h) => {
      const total = h.hits + h.misses;
      return total > 0 ? Number(((h.hits / total) * 100).toFixed(1)) : null;
    });
    let cumulative = 0;
    const tokensCumulative = hourly.map((h) => (cumulative += h.tokensSaved));
    return {
      labels,
      hitRateSeries,
      tokensCumulative,
      hitsSeries: hourly.map((h) => h.hits),
      missesSeries: hourly.map((h) => h.misses)
    };
  }

  /**
   * Build HTML page with dashboard
   */
  _buildHTMLPage(cacheInfo, perf, recommendations, validatorStats, hourly, statusOk) {
    const embeddingStatus = validatorStats || {};
    const chart = this._buildChartSeries(hourly);
    const latency = perf && perf.cacheRetrievalTime ? perf.cacheRetrievalTime : { avg: 0, p95: 0, p99: 0 };
    const p50Badge = this._latencyBadge(latency.avg);
    const p95Badge = this._latencyBadge(latency.p95);
    const p99Badge = this._latencyBadge(latency.p99);
    const statusBadge = statusOk
      ? { cls: 'badge-success', text: 'Healthy' }
      : { cls: 'badge-warning', text: 'Degraded' };

    // Format numbers for display
    const formatNumber = (num) => {
      return Math.round(num).toLocaleString('en-US');
    };

    const recommendationItems = recommendations.suggestions && recommendations.suggestions.length > 0
      ? recommendations.suggestions.map((s) => `
                <div class="detail-item">
                    <span class="detail-label">${s.area}</span>
                    <span class="badge ${s.impact === 'high' ? 'badge-warning' : 'badge-info'}">${s.impact}</span>
                </div>`).join('')
      : `
                <div class="detail-item">
                    <span class="detail-label">Status</span>
                    <span class="badge badge-success">No issues detected</span>
                </div>`;

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cache Metrics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 32px;
            margin-bottom: 8px;
        }

        .header p {
            font-size: 14px;
            opacity: 0.9;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
        }

        .stat-label {
            font-size: 12px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 6px;
        }

        .stat-unit {
            font-size: 12px;
            color: #999;
        }

        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .chart-title {
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
        }

        .chart {
            position: relative;
            height: 300px;
        }

        .details-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .details-panel {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .panel-title {
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 12px;
        }

        .detail-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f5f5f5;
        }

        .detail-item:last-child {
            border-bottom: none;
        }

        .detail-label {
            font-size: 13px;
            color: #666;
            font-weight: 500;
        }

        .detail-value {
            font-size: 14px;
            color: #333;
            font-weight: 600;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-success {
            background: #d1fae5;
            color: #065f46;
        }

        .badge-warning {
            background: #fef3c7;
            color: #92400e;
        }

        .badge-info {
            background: #dbeafe;
            color: #1e40af;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 6px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }

        .timestamp {
            font-size: 12px;
            color: #999;
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #f0f0f0;
        }

        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .charts-grid {
                grid-template-columns: 1fr;
            }

            .details-grid {
                grid-template-columns: 1fr;
            }

            .header h1 {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Cache Metrics Dashboard</h1>
            <p>Cache health, computed from cache_events</p>
        </div>

        <!-- Key Metrics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Cache Hit Rate</div>
                <div class="stat-value">${cacheInfo.hitRate}${cacheInfo.hitRate === 'N/A' ? '' : '%'}</div>
                <div class="stat-unit">${formatNumber(cacheInfo.totalQueries)} queries recorded</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Cached Entries</div>
                <div class="stat-value">${formatNumber(cacheInfo.totalEntries)}</div>
                <div class="stat-unit">${cacheInfo.maxEntries ? `of ${formatNumber(cacheInfo.maxEntries)} max` : 'no configured max'}</div>
                <div class="progress-bar"><div class="progress-fill" style="width: ${cacheInfo.utilizationPercent}%"></div></div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Avg Tokens Saved</div>
                <div class="stat-value">${formatNumber(cacheInfo.avgTokensSaved)}</div>
                <div class="stat-unit">Per cache hit — ${formatNumber(cacheInfo.totalTokensSaved)} total</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Latency (avg)</div>
                <div class="stat-value">${latency.avg}ms</div>
                <div class="stat-unit">Retrieval time</div>
                <span class="badge ${p50Badge.cls}">${p50Badge.text}</span>
            </div>

            <div class="stat-card">
                <div class="stat-label">Latency (p95)</div>
                <div class="stat-value">${latency.p95}ms</div>
                <div class="stat-unit">95th percentile</div>
                <span class="badge ${p95Badge.cls}">${p95Badge.text}</span>
            </div>

            <div class="stat-card">
                <div class="stat-label">Latency (p99)</div>
                <div class="stat-value">${latency.p99}ms</div>
                <div class="stat-unit">99th percentile</div>
                <span class="badge ${p99Badge.cls}">${p99Badge.text}</span>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">Hit Rate Trend (24h)</div>
                <div class="chart">
                    <canvas id="hitRateChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <div class="chart-title">Tokens Saved Accumulation (24h)</div>
                <div class="chart">
                    <canvas id="tokensSavedChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <div class="chart-title">Request Volume (by hour)</div>
                <div class="chart">
                    <canvas id="volumeChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Details -->
        <div class="details-grid">
            <div class="details-panel">
                <div class="panel-title">Cache Status</div>
                <div class="detail-item">
                    <span class="detail-label">Total Cache Hits</span>
                    <span class="detail-value">${formatNumber(cacheInfo.totalHits)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Total Cache Misses</span>
                    <span class="detail-value">${formatNumber(cacheInfo.totalMisses)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Active Entries</span>
                    <span class="detail-value">${formatNumber(cacheInfo.totalEntries)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Cache Status</span>
                    <span class="badge ${statusBadge.cls}">${statusBadge.text}</span>
                </div>
            </div>

            <div class="details-panel">
                <div class="panel-title">Embedding Scorer ${embeddingStatus.ready ? '✓' : '✗'}</div>
                <div class="detail-item">
                    <span class="detail-label">Cache Hits</span>
                    <span class="detail-value">${formatNumber(embeddingStatus.cacheHits || 0)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Cache Misses</span>
                    <span class="detail-value">${formatNumber(embeddingStatus.cacheMisses || 0)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">API Calls</span>
                    <span class="detail-value">${formatNumber(embeddingStatus.apiCalls || 0)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Hit Rate</span>
                    <span class="detail-value">${embeddingStatus.hitRate || 'N/A'}</span>
                </div>
            </div>

            <div class="details-panel">
                <div class="panel-title">Recommendations</div>${recommendationItems}
            </div>
        </div>

        <div class="timestamp">
            Last updated: <span id="timestamp">${new Date().toLocaleString()}</span> |
            Dashboard v2.0 | Agent Cache Plugin
        </div>
    </div>

    <script>
        // Chart color scheme
        const colors = {
            primary: '#667eea',
            secondary: '#764ba2',
            success: '#10b981',
            warning: '#f59e0b',
            danger: '#ef4444'
        };

        const labels = ${JSON.stringify(chart.labels)};

        // Hit Rate Trend Chart
        const hitRateCtx = document.getElementById('hitRateChart').getContext('2d');
        new Chart(hitRateCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Hit Rate (%)',
                    data: ${JSON.stringify(chart.hitRateSeries)},
                    spanGaps: true,
                    borderColor: colors.primary,
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: colors.primary,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { color: '#f0f0f0' }
                    },
                    x: {
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { display: false }
                    }
                }
            }
        });

        // Tokens Saved Chart
        const tokensSavedCtx = document.getElementById('tokensSavedChart').getContext('2d');
        new Chart(tokensSavedCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Cumulative Tokens Saved',
                    data: ${JSON.stringify(chart.tokensCumulative)},
                    backgroundColor: colors.primary,
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { color: '#f0f0f0' }
                    },
                    x: {
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { display: false }
                    }
                }
            }
        });

        // Request Volume Chart
        const volumeCtx = document.getElementById('volumeChart').getContext('2d');
        new Chart(volumeCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Hits',
                        data: ${JSON.stringify(chart.hitsSeries)},
                        backgroundColor: colors.success,
                        borderRadius: 4
                    },
                    {
                        label: 'Misses',
                        data: ${JSON.stringify(chart.missesSeries)},
                        backgroundColor: colors.warning,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#666', font: { size: 11 }, padding: 15 }
                    }
                },
                scales: {
                    y: {
                        stacked: true,
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { color: '#f0f0f0' }
                    },
                    x: {
                        stacked: true,
                        ticks: { color: '#666', font: { size: 11 } },
                        grid: { display: false }
                    }
                }
            }
        });

        // Update timestamp
        setInterval(() => {
            document.getElementById('timestamp').textContent = new Date().toLocaleString();
        }, 60000);
    </script>
</body>
</html>`;
  }
}

/**
 * Generate the dashboard and write it to disk.
 * @param {object} [args]
 * @param {string} [args.output] - Destination file (default: cache-dashboard.html).
 */
async function execute(args = {}) {
  const outputFile = args.output || args.o || 'cache-dashboard.html';
  try {
    const dashboard = new CacheDashboard();
    const html = await dashboard.generateHTML();
    fs.writeFileSync(outputFile, html);
    return { status: 'success', report: `Dashboard written to ${outputFile}`, format: 'html', data: html };
  } catch (err) {
    return { status: 'error', error: err.message, report: `Failed to generate dashboard: ${err.message}` };
  }
}

// CLI usage
if (require.main === module) {
  const argv = process.argv.slice(2);
  const outputIdx = Math.max(argv.indexOf('--output'), argv.indexOf('-o'));
  const outputFile = outputIdx >= 0 ? argv[outputIdx + 1] : undefined;

  execute({ output: outputFile }).then((result) => {
    console.log(result.report);
    if (result.status === 'error') process.exit(1);
  });
}

module.exports = {
  name: 'cache-dashboard',
  description: 'Generate an HTML dashboard of cache hit rate, token savings, and request volume',
  usage: 'cache-command.js dashboard [--output FILE]',

  execute,

  CacheDashboard
};
