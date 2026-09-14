/**
 * Command: /cache-config
 *
 * Configure cache settings and parameters.
 * Usage: /cache-config [--get | --set <key> <value>] [--reset] [--list]
 */

const cacheManagement = require('../skills/cache-management');
const cacheOrchestrator = require('../agents/agent-cache-orchestrator');

class CacheConfigCommand {
  constructor() {
    this.cache = cacheManagement.getSingleton();
    this.orchestrator = cacheOrchestrator.create({
      cache: this.cache,
      metrics: require('../skills/metrics-tracker').getSingleton()
    });
  }

  /**
   * Execute the cache-config command
   */
  async execute(args = {}) {
    try {
      if (args.list || Object.keys(args).length === 0) {
        return this._listConfig();
      }

      if (args.get) {
        return this._getConfig(args.get);
      }

      if (args.set && args.value !== undefined) {
        return this._setConfig(args.key, args.value);
      }

      if (args.reset) {
        return this._resetConfig();
      }

      if (args.validate) {
        return this._validateConfig();
      }

      return {
        status: 'error',
        message: 'Invalid command. Use --list, --get <key>, --set <key> <value>, --reset, or --validate'
      };
    } catch (error) {
      return this._errorResponse(error);
    }
  }

  /**
   * List all current configuration
   */
  async _listConfig() {
    const stats = this.cache.getStats();

    const config = {
      cache: {
        maxSize: this.cache.maxSize,
        maxEntries: this.cache.maxEntries,
        defaultTTL: this.cache.defaultTTL,
        evictionPolicy: this.cache.evictionPolicy
      },
      orchestrator: {
        relevanceThreshold: this.orchestrator.relevanceThreshold,
        stalenessThreshold: this.orchestrator.stalenessThreshold
      },
      current: {
        totalEntries: stats.totalEntries,
        cacheSize: stats.cacheSize,
        utilizationPercent: stats.utilizationPercent,
        hitRate: (stats.hitRate * 100).toFixed(1) + '%'
      }
    };

    const report = this._formatConfigReport(config);

    return {
      status: 'success',
      config: config,
      report: report
    };
  }

  /**
   * Get specific configuration value
   */
  async _getConfig(key) {
    const validKeys = [
      'maxSize', 'maxEntries', 'defaultTTL', 'evictionPolicy',
      'relevanceThreshold', 'stalenessThreshold'
    ];

    if (!validKeys.includes(key)) {
      return {
        status: 'error',
        message: `Unknown config key: ${key}`,
        validKeys: validKeys
      };
    }

    let value;
    if (key === 'relevanceThreshold' || key === 'stalenessThreshold') {
      value = this.orchestrator[key];
    } else {
      value = this.cache[key];
    }

    return {
      status: 'success',
      key: key,
      value: value,
      formatted: this._formatValue(key, value)
    };
  }

  /**
   * Set configuration value
   */
  async _setConfig(key, value) {
    const validKeys = [
      'maxSize', 'maxEntries', 'defaultTTL', 'evictionPolicy',
      'relevanceThreshold', 'stalenessThreshold'
    ];

    if (!validKeys.includes(key)) {
      return {
        status: 'error',
        message: `Unknown config key: ${key}`,
        validKeys: validKeys
      };
    }

    // Validate value type and range
    const validation = this._validateValue(key, value);
    if (!validation.valid) {
      return {
        status: 'error',
        key: key,
        message: validation.error,
        hint: validation.hint
      };
    }

    // Apply configuration
    try {
      if (key === 'evictionPolicy') {
        const result = await this.cache.configure({
          [key]: validation.parsedValue
        });
        if (!result.success) {
          return { status: 'error', message: result.error };
        }
      } else if (key === 'relevanceThreshold' || key === 'stalenessThreshold') {
        await this.orchestrator.configure({
          [key]: validation.parsedValue
        });
      } else {
        const result = await this.cache.configure({
          [key]: validation.parsedValue
        });
        if (!result.success) {
          return { status: 'error', message: result.error };
        }
      }

      return {
        status: 'success',
        key: key,
        oldValue: key === 'evictionPolicy' ? this.cache.evictionPolicy : (
          key === 'relevanceThreshold' ? this.orchestrator.relevanceThreshold :
          this.cache[key]
        ),
        newValue: validation.parsedValue,
        message: `${key} updated successfully`
      };
    } catch (error) {
      return this._errorResponse(error);
    }
  }

  /**
   * Reset to default configuration
   */
  async _resetConfig() {
    const defaults = {
      maxSize: 100 * 1024 * 1024, // 100 MB
      maxEntries: 10000,
      defaultTTL: 3 * 24 * 60 * 60 * 1000, // 3 days
      evictionPolicy: 'LRU',
      relevanceThreshold: 75,
      stalenessThreshold: 24 * 60 * 60 * 1000 // 24 hours
    };

    try {
      await this.cache.configure({
        maxSize: defaults.maxSize,
        maxEntries: defaults.maxEntries,
        defaultTTL: defaults.defaultTTL,
        evictionPolicy: defaults.evictionPolicy
      });

      await this.orchestrator.configure({
        relevanceThreshold: defaults.relevanceThreshold,
        stalenessThreshold: defaults.stalenessThreshold
      });

      return {
        status: 'success',
        message: 'Configuration reset to defaults',
        defaults: defaults
      };
    } catch (error) {
      return this._errorResponse(error);
    }
  }

  /**
   * Validate current configuration
   */
  async _validateConfig() {
    const issues = [];
    const warnings = [];

    // Check utilization
    const stats = this.cache.getStats();
    if (stats.utilizationPercent > 90) {
      warnings.push('Cache utilization high (>90%). Consider increasing maxSize or reducing TTL.');
    }

    // Check if entries at max
    if (stats.totalEntries >= this.cache.maxEntries * 0.95) {
      warnings.push('Cache approaching entry limit. Consider increasing maxEntries.');
    }

    // Check eviction policy effectiveness
    if (stats.hitRate < 0.1 && this.orchestrator.relevanceThreshold >= 75) {
      warnings.push('Hit rate low. Consider lowering relevanceThreshold from 75% to 65%.');
    }

    // Validate threshold values
    if (this.orchestrator.relevanceThreshold < 50 || this.orchestrator.relevanceThreshold > 95) {
      issues.push('relevanceThreshold should be between 50 and 95');
    }

    if (this.cache.defaultTTL < 60 * 1000) {
      issues.push('defaultTTL should be at least 1 minute');
    }

    const report = {
      valid: issues.length === 0,
      issues: issues,
      warnings: warnings,
      timestamp: new Date().toISOString()
    };

    return {
      status: 'success',
      validation: report,
      report: this._formatValidationReport(report)
    };
  }

  // Private methods

  _formatConfigReport(config) {
    return `Cache Configuration Report
═══════════════════════════════════════════

CACHE SETTINGS
──────────────
Max Size:              ${this._formatBytes(config.cache.maxSize)}
Max Entries:           ${config.cache.maxEntries.toLocaleString()}
Default TTL:           ${this._formatDuration(config.cache.defaultTTL)}
Eviction Policy:       ${config.cache.evictionPolicy}

ORCHESTRATOR SETTINGS
─────────────────────
Relevance Threshold:   ${config.orchestrator.relevanceThreshold}%
Staleness Threshold:   ${this._formatDuration(config.orchestrator.stalenessThreshold)}

CURRENT STATUS
──────────────
Total Entries:         ${config.current.totalEntries.toLocaleString()}
Cache Size:            ${this._formatBytes(config.current.cacheSize)} / ${this._formatBytes(config.cache.maxSize)}
Utilization:           ${config.current.utilizationPercent}%
Hit Rate:              ${config.current.hitRate}

═══════════════════════════════════════════`;
  }

  _formatValidationReport(validation) {
    let report = 'Configuration Validation Report\n';
    report += '═══════════════════════════════════════════\n\n';
    report += `Status: ${validation.valid ? '✓ VALID' : '✗ INVALID'}\n\n`;

    if (validation.issues.length > 0) {
      report += 'ISSUES\n──────\n';
      validation.issues.forEach((issue, idx) => {
        report += `${idx + 1}. ${issue}\n`;
      });
      report += '\n';
    }

    if (validation.warnings.length > 0) {
      report += 'WARNINGS\n────────\n';
      validation.warnings.forEach((warning, idx) => {
        report += `${idx + 1}. ${warning}\n`;
      });
      report += '\n';
    }

    if (validation.issues.length === 0 && validation.warnings.length === 0) {
      report += 'No issues or warnings found.\n';
    }

    report += '═══════════════════════════════════════════';
    return report;
  }

  _validateValue(key, value) {
    try {
      switch (key) {
        case 'maxSize':
          const sizeBytes = this._parseBytes(value);
          if (sizeBytes < 1024 * 1024) { // Min 1 MB
            return { valid: false, error: 'maxSize must be at least 1 MB', hint: 'Use units: 100MB, 1GB, etc.' };
          }
          return { valid: true, parsedValue: sizeBytes };

        case 'maxEntries':
          const entries = parseInt(value);
          if (isNaN(entries) || entries < 100) {
            return { valid: false, error: 'maxEntries must be at least 100', hint: 'Example: 10000' };
          }
          return { valid: true, parsedValue: entries };

        case 'defaultTTL':
          const ttl = this._parseDuration(value);
          if (ttl < 60 * 1000) { // Min 1 minute
            return { valid: false, error: 'defaultTTL must be at least 1 minute', hint: 'Use: 1h, 7d, 1d, etc.' };
          }
          return { valid: true, parsedValue: ttl };

        case 'evictionPolicy':
          const policy = String(value).toUpperCase();
          if (!['LRU', 'LFU', 'FIFO'].includes(policy)) {
            return { valid: false, error: 'evictionPolicy must be LRU, LFU, or FIFO', hint: 'Example: LRU' };
          }
          return { valid: true, parsedValue: policy };

        case 'relevanceThreshold':
          const threshold = parseInt(value);
          if (isNaN(threshold) || threshold < 50 || threshold > 95) {
            return { valid: false, error: 'relevanceThreshold must be between 50 and 95', hint: 'Example: 75' };
          }
          return { valid: true, parsedValue: threshold };

        case 'stalenessThreshold':
          const stale = this._parseDuration(value);
          if (stale < 60 * 1000) { // Min 1 minute
            return { valid: false, error: 'stalenessThreshold must be at least 1 minute', hint: 'Use: 1h, 7d, etc.' };
          }
          return { valid: true, parsedValue: stale };

        default:
          return { valid: false, error: `Unknown key: ${key}` };
      }
    } catch (error) {
      return { valid: false, error: error.message };
    }
  }

  _parseBytes(value) {
    const units = { B: 1, KB: 1024, MB: 1024 ** 2, GB: 1024 ** 3, TB: 1024 ** 4 };
    const match = String(value).match(/^([\d.]+)\s*(B|KB|MB|GB|TB)?$/i);
    if (!match) throw new Error('Invalid size format');
    return Math.round(parseFloat(match[1]) * (units[match[2]?.toUpperCase()] || 1));
  }

  _parseDuration(value) {
    const units = { s: 1000, m: 60 * 1000, h: 60 * 60 * 1000, d: 24 * 60 * 60 * 1000 };
    const match = String(value).match(/^([\d.]+)\s*(s|m|h|d)?$/i);
    if (!match) throw new Error('Invalid duration format');
    return Math.round(parseFloat(match[1]) * (units[match[2]?.toLowerCase()] || 1));
  }

  _formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  }

  _formatDuration(ms) {
    if (ms < 60 * 1000) return Math.floor(ms / 1000) + 's';
    if (ms < 60 * 60 * 1000) return Math.floor(ms / (60 * 1000)) + 'm';
    if (ms < 24 * 60 * 60 * 1000) return Math.floor(ms / (60 * 60 * 1000)) + 'h';
    return Math.floor(ms / (24 * 60 * 60 * 1000)) + 'd';
  }

  _formatValue(key, value) {
    if (key === 'maxSize') {
      return this._formatBytes(value);
    } else if (key === 'defaultTTL' || key === 'stalenessThreshold') {
      return this._formatDuration(value);
    } else if (key === 'relevanceThreshold') {
      return value + '%';
    }
    return value;
  }

  _errorResponse(error) {
    return {
      status: 'error',
      error: error.message
    };
  }
}

module.exports = {
  name: 'cache-config',
  description: 'Configure cache settings and parameters',
  usage: '/cache-config [--list | --get <key> | --set <key> <value> | --reset | --validate]',

  execute: async (args) => {
    const cmd = new CacheConfigCommand();
    return cmd.execute(args);
  },

  CacheConfigCommand
};
