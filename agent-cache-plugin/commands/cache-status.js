/**
 * Command: /cache-status
 *
 * Display current cache statistics and health metrics.
 * Usage: /cache-status [--detailed] [--export json|csv|html]
 */

const cacheManagement = require('../skills/cache-management');
const metricsTracker = require('../skills/metrics-tracker');

class CacheStatusCommand {
  constructor() {
    this.cache = cacheManagement.getSingleton();
    this.metrics = metricsTracker.getSingleton();
  }

  /**
   * Execute the cache-status command
   */
  async execute(args = {}) {
    try {
      const detailed = args.detailed || args.d || false;
      const exportFormat = args.export || null;
      const includeRecommendations = args.recommendations !== false;

      // Gather metrics
      const stats = this.cache.getStats();
      const hitRate = await this.metrics.getHitRate();
      const savings = await this.metrics.getTokenSavings();
      const perfMetrics = await this.metrics.getPerformanceMetrics();
      const recommendations = includeRecommendations
        ? await this.metrics.getRecommendations()
        : { suggestions: [] };

      // Build report
      const report = this._buildReport(
        stats,
        hitRate,
        savings,
        perfMetrics,
        recommendations,
        detailed
      );

      // Export if requested
      if (exportFormat) {
        return this._exportReport(report, exportFormat);
      }

      return report;
    } catch (error) {
      return this._errorResponse(error);
    }
  }

  /**
   * Build text report
   */
  _buildReport(stats, hitRate, savings, perfMetrics, recommendations, detailed) {
    const now = new Date().toISOString();
    let report = `Cache Status Report
Generated: ${now}

═══════════════════════════════════════════════════════════

OVERALL STATS
─────────────
Total Entries:     ${stats.totalEntries.toLocaleString()}
Cache Size:        ${this._formatBytes(stats.cacheSize)} / ${this._formatBytes(stats.maxSize)} (${stats.utilizationPercent}%)
Hit Rate:          ${(hitRate.hitRate * 100).toFixed(1)}% (${hitRate.totalHits.toLocaleString()} hits / ${hitRate.totalQueries.toLocaleString()} queries)
Cache Efficiency:  ${this._calculateEfficiency(savings.totalTokensSaved, stats.cacheSize)} tokens/byte

TOKEN SAVINGS
─────────────
Total Saved:       ${savings.totalTokensSaved.toLocaleString()} tokens
Per Hit Average:   ${savings.avgPerHit} tokens
Max Single Save:   ${savings.maxSingleSave.toLocaleString()} tokens
Cost Reduction:    ${savings.estimatedCostReduction}

PERFORMANCE
───────────
Retrieval Time:
  • Avg:           ${perfMetrics.cacheRetrievalTime.avg}ms
  • Median:        ${perfMetrics.cacheRetrievalTime.median}ms
  • P95:           ${perfMetrics.cacheRetrievalTime.p95}ms
  • P99:           ${perfMetrics.cacheRetrievalTime.p99}ms

Relevance Scores:
  • Avg:           ${perfMetrics.relevanceScores.avg}%
  • Min:           ${perfMetrics.relevanceScores.min}%
  • Max:           ${perfMetrics.relevanceScores.max}%`;

    if (detailed) {
      report += this._buildDetailedSection(stats, perfMetrics);
    }

    if (recommendations.suggestions && recommendations.suggestions.length > 0) {
      report += this._buildRecommendationsSection(recommendations.suggestions);
    }

    report += '\n═══════════════════════════════════════════════════════════\n';

    return {
      status: 'success',
      format: 'text',
      report: report,
      metrics: {
        entries: stats.totalEntries,
        hitRate: hitRate.hitRate,
        tokensSaved: savings.totalTokensSaved,
        cacheSize: stats.cacheSize
      }
    };
  }

  /**
   * Build detailed breakdown section
   */
  _buildDetailedSection(stats, perfMetrics) {
    let section = '\n\nDETAILED BREAKDOWN\n';
    section += '──────────────────\n\n';

    // Top agents
    if (stats.topAgents && stats.topAgents.length > 0) {
      section += 'Top Agents:\n';
      stats.topAgents.forEach((agent, idx) => {
        section += `  ${idx + 1}. ${agent.agent} - ${agent.count} entries\n`;
      });
      section += '\n';
    }

    // Task type breakdown
    if (perfMetrics.taskBreakdown) {
      section += 'Task Type Performance:\n';
      Object.entries(perfMetrics.taskBreakdown).forEach(([taskType, data]) => {
        const hitRate = ((data.hits / (data.hits + data.misses)) * 100).toFixed(1);
        section += `  • ${taskType}: ${hitRate}% hit rate (${data.hits} hits, ${data.misses} misses)\n`;
      });
      section += '\n';
    }

    // Cache age info
    if (stats.oldestEntry && stats.newestEntry) {
      const oldestAge = this._formatAge(Date.now() - stats.oldestEntry);
      const newestAge = this._formatAge(Date.now() - stats.newestEntry);
      section += `Cache Age:\n  • Oldest entry: ${oldestAge}\n  • Newest entry: ${newestAge}\n`;
    }

    return section;
  }

  /**
   * Build recommendations section
   */
  _buildRecommendationsSection(suggestions) {
    let section = '\n\nRECOMMENDATIONS\n';
    section += '───────────────\n';

    suggestions.forEach((suggestion, idx) => {
      const impact = this._formatImpact(suggestion.impact);
      section += `\n${idx + 1}. [${impact}] ${suggestion.area}\n`;
      section += `   Finding: ${suggestion.finding}\n`;
      section += `   Action: ${suggestion.action}\n`;
    });

    return section;
  }

  /**
   * Export report in various formats
   */
  _exportReport(report, format) {
    if (format === 'json') {
      return {
        status: 'success',
        format: 'json',
        data: report.metrics,
        report: report.report
      };
    } else if (format === 'csv') {
      const csv = this._toCsv(report.metrics);
      return {
        status: 'success',
        format: 'csv',
        data: csv,
        contentType: 'text/csv'
      };
    } else if (format === 'html') {
      const html = this._toHtml(report);
      return {
        status: 'success',
        format: 'html',
        data: html,
        contentType: 'text/html'
      };
    }

    return this._errorResponse(new Error(`Unknown format: ${format}`));
  }

  /**
   * Convert to CSV
   */
  _toCsv(metrics) {
    const lines = [
      'Metric,Value',
      `Total Entries,${metrics.entries}`,
      `Hit Rate,${(metrics.hitRate * 100).toFixed(1)}%`,
      `Tokens Saved,${metrics.tokensSaved}`,
      `Cache Size Bytes,${metrics.cacheSize}`
    ];
    return lines.join('\n');
  }

  /**
   * Convert to HTML
   */
  _toHtml(report) {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Cache Status Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
    .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
    .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    h1 { color: #1a73e8; margin-bottom: 10px; }
    .timestamp { color: #999; font-size: 12px; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
    .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .metric-label { color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #1a73e8; }
    .metric-unit { font-size: 12px; color: #999; margin-left: 4px; }
    table { width: 100%; border-collapse: collapse; background: white; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    th { background: #f9f9f9; padding: 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e8e8e8; }
    td { padding: 12px; border-bottom: 1px solid #e8e8e8; }
    tr:hover { background: #f9f9f9; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Cache Status Report</h1>
      <div class="timestamp">${new Date().toISOString()}</div>
    </div>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total Entries</div>
        <div class="metric-value">${report.metrics.entries.toLocaleString()}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Hit Rate</div>
        <div class="metric-value">${(report.metrics.hitRate * 100).toFixed(1)}<span class="metric-unit">%</span></div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Tokens Saved</div>
        <div class="metric-value">${report.metrics.tokensSaved.toLocaleString()}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Cache Size</div>
        <div class="metric-value">${(report.metrics.cacheSize / 1024 / 1024).toFixed(1)}<span class="metric-unit">MB</span></div>
      </div>
    </div>

    <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h2 style="margin-bottom: 15px;">Full Report</h2>
      <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; overflow-x: auto; font-size: 12px;">${report.report}</pre>
    </div>
  </div>
</body>
</html>`;
  }

  /**
   * Error response
   */
  _errorResponse(error) {
    return {
      status: 'error',
      error: error.message,
      report: `Error generating cache status: ${error.message}`
    };
  }

  // Utility methods

  _formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  }

  _formatAge(ms) {
    if (ms < 60 * 1000) return 'just now';
    if (ms < 60 * 60 * 1000) return Math.floor(ms / (60 * 1000)) + ' min ago';
    if (ms < 24 * 60 * 60 * 1000) return Math.floor(ms / (60 * 60 * 1000)) + ' hours ago';
    return Math.floor(ms / (24 * 60 * 60 * 1000)) + ' days ago';
  }

  _formatImpact(impact) {
    const icons = { high: '🔴', medium: '🟡', low: '🟢' };
    return icons[impact] || '•';
  }

  _calculateEfficiency(tokens, bytes) {
    if (bytes === 0) return '0';
    return (tokens / bytes).toFixed(3);
  }
}

module.exports = {
  name: 'cache-status',
  description: 'Display cache statistics and health metrics',
  usage: '/cache-status [--detailed] [--export json|csv|html]',

  execute: async (args) => {
    const cmd = new CacheStatusCommand();
    return cmd.execute(args);
  },

  CacheStatusCommand
};
