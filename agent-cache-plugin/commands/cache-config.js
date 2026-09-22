/**
 * Command: /cache-config
 *
 * View and change the four persisted cache settings (see sqlite-cache CONFIG_KEYS).
 * Usage: /cache-config [--list] [--get KEY] [--set KEY VALUE] [--reset [KEY]] [--validate]
 *
 * Settings live in the cache DB's `config` table, so a change made here is picked up by the
 * next hook or CLI process. There is no maxSize/evictionPolicy: the SQLite backend is
 * LRU-by-maxEntries only and does not track bytes.
 */

const sqliteCache = require('../skills/sqlite-cache');
const metricsTracker = require('../skills/metrics-tracker');

const { CONFIG_KEYS } = sqliteCache;
const VALID_KEYS = Object.keys(CONFIG_KEYS);

const DURATION_KEYS = new Set(['defaultTTL', 'stalenessThreshold']);
const PERCENT_KEYS = new Set(['relevanceThreshold']);

class CacheConfigCommand {
  /**
   * @param {object} [deps] - Optional dependency injection for testing.
   * @param {object} [deps.cache]   - CacheManager instance.
   * @param {object} [deps.metrics] - MetricsTracker instance.
   */
  constructor(deps = {}) {
    this.cache = deps.cache || sqliteCache.getSingleton();
    this.metrics = deps.metrics || metricsTracker.getSingleton();
  }

  /**
   * Execute the cache-config command. `--list --validate` may be combined; otherwise the
   * first matching action wins.
   */
  async execute(args = {}) {
    try {
      if (args.set !== undefined) {
        const [key, value] = this._setArgs(args);
        if (key === undefined || value === undefined) {
          return this._error('Usage: --set KEY VALUE', { validKeys: VALID_KEYS });
        }
        return this._setConfig(key, value);
      }

      if (args.reset !== undefined) {
        return this._resetConfig(args.reset === true ? null : String(args.reset));
      }

      if (args.get !== undefined) {
        return this._getConfig(String(args.get));
      }

      const wantList = args.list || (!args.validate && Object.keys(args).length === 0);
      const wantValidate = !!args.validate;
      if (!wantList && !wantValidate) {
        return this._error('Invalid command. Use --list, --get KEY, --set KEY VALUE, --reset [KEY], or --validate');
      }

      const parts = [];
      let out = { status: 'success' };
      if (wantList) {
        const listed = await this._listConfig();
        out = { ...out, ...listed };
        parts.push(listed.report);
      }
      if (wantValidate) {
        const validated = await this._validateConfig();
        out = { ...out, validation: validated.validation };
        parts.push(validated.report);
      }
      out.report = parts.join('\n\n');
      return out;
    } catch (error) {
      return this._error(error.message);
    }
  }

  /** `--set KEY VALUE` arrives as set:[KEY,VALUE]; also accept --set KEY --value VALUE. */
  _setArgs(args) {
    if (Array.isArray(args.set)) return [args.set[0], args.set.slice(1).join(' ')];
    if (typeof args.set === 'string') return [args.set, args.value !== undefined ? String(args.value) : undefined];
    return [args.key, args.value];
  }

  async _listConfig() {
    const config = this.cache.getConfig();
    const stats = this.cache.stats();
    const hitRate = await this.metrics.getHitRate();
    const current = {
      totalEntries: stats.totalEntries || 0,
      hitRate: hitRate && hitRate.hitRate != null ? hitRate.hitRate : 0
    };
    return {
      config,
      current,
      report: this._formatConfigReport(config, current)
    };
  }

  async _getConfig(key) {
    if (!VALID_KEYS.includes(key)) {
      return this._error(`Unknown config key: ${key}`, { validKeys: VALID_KEYS });
    }
    const value = this.cache.getConfig()[key];
    const formatted = this._formatValue(key, value);
    return { status: 'success', key, value, formatted, report: `${key} = ${formatted}` };
  }

  async _setConfig(key, value) {
    if (!VALID_KEYS.includes(key)) {
      return this._error(`Unknown config key: ${key}`, { validKeys: VALID_KEYS });
    }
    const validation = this._validateValue(key, value);
    if (!validation.valid) {
      return this._error(validation.error, { key, hint: validation.hint });
    }

    const oldValue = this.cache.getConfig()[key];
    const result = this.cache.configure({ [key]: validation.parsedValue });
    if (!result.success) {
      return this._error(result.error, { key });
    }
    const newValue = result.config[key];
    return {
      status: 'success',
      key,
      oldValue,
      newValue,
      report: `Updated: ${key} = ${this._formatValue(key, newValue)} (was ${this._formatValue(key, oldValue)})`
    };
  }

  async _resetConfig(key) {
    if (key !== null && !VALID_KEYS.includes(key)) {
      return this._error(`Unknown config key: ${key}`, { validKeys: VALID_KEYS });
    }
    const result = key === null
      ? this.cache.resetConfig()
      : this.cache.configure({ [key]: null });
    if (!result.success) {
      return this._error(result.error);
    }
    const keys = key === null ? VALID_KEYS : [key];
    const lines = keys.map(k => `Reset: ${k} = ${this._formatValue(k, result.config[k])} (default)`);
    return {
      status: 'success',
      reset: keys,
      config: result.config,
      report: lines.join('\n')
    };
  }

  async _validateConfig() {
    const config = this.cache.getConfig();
    const stats = this.cache.stats();
    const hitRate = await this.metrics.getHitRate();
    const issues = [];
    const warnings = [];

    for (const key of VALID_KEYS) {
      const spec = CONFIG_KEYS[key];
      const v = config[key];
      if (spec.min != null && v < spec.min) issues.push(`${key} (${v}) is below minimum ${spec.min}`);
      if (spec.max != null && v > spec.max) issues.push(`${key} (${v}) is above maximum ${spec.max}`);
    }

    const total = stats.totalEntries || 0;
    if (total >= config.maxEntries * 0.95) {
      warnings.push(`Cache at ${total}/${config.maxEntries} entries; LRU eviction is imminent. Consider raising maxEntries.`);
    }
    const rate = hitRate && hitRate.hitRate != null ? hitRate.hitRate : 0;
    const sampled = hitRate && (hitRate.hits || 0) + (hitRate.misses || 0) >= 20;
    if (sampled && rate < 0.1 && config.relevanceThreshold >= 75) {
      warnings.push(`Hit rate ${(rate * 100).toFixed(1)}% with relevanceThreshold ${config.relevanceThreshold}. Consider lowering to 65.`);
    }
    if (config.stalenessThreshold > config.defaultTTL) {
      warnings.push('stalenessThreshold exceeds defaultTTL; entries expire before they are ever considered stale.');
    }

    const validation = { valid: issues.length === 0, issues, warnings, timestamp: new Date().toISOString() };
    return { validation, report: this._formatValidationReport(validation) };
  }

  // Formatting / parsing

  _formatConfigReport(config, current) {
    return `Cache Configuration Report
═══════════════════════════════════════════

SETTINGS (persisted in cache.db)
────────────────────────────────
Max Entries:           ${config.maxEntries.toLocaleString()}
Default TTL:           ${this._formatDuration(config.defaultTTL)}
Relevance Threshold:   ${config.relevanceThreshold}%
Staleness Threshold:   ${this._formatDuration(config.stalenessThreshold)}
Eviction:              LRU by entry count (bytes are not tracked)

CURRENT STATUS
──────────────
Total Entries:         ${current.totalEntries.toLocaleString()} / ${config.maxEntries.toLocaleString()}
Hit Rate:              ${(current.hitRate * 100).toFixed(1)}%

═══════════════════════════════════════════`;
  }

  _formatValidationReport(validation) {
    let report = 'Configuration Validation Report\n';
    report += '═══════════════════════════════════════════\n\n';
    report += `Status: ${validation.valid ? '✓ VALID' : '✗ INVALID'}\n\n`;
    if (validation.issues.length > 0) {
      report += 'ISSUES\n──────\n';
      validation.issues.forEach((issue, idx) => { report += `${idx + 1}. ${issue}\n`; });
      report += '\n';
    }
    if (validation.warnings.length > 0) {
      report += 'WARNINGS\n────────\n';
      validation.warnings.forEach((w, idx) => { report += `${idx + 1}. ${w}\n`; });
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
      if (DURATION_KEYS.has(key)) {
        return { valid: true, parsedValue: this._parseDuration(value) };
      }
      const n = parseInt(value, 10);
      if (Number.isNaN(n)) {
        return { valid: false, error: `${key} must be an integer`, hint: PERCENT_KEYS.has(key) ? 'Example: 75' : 'Example: 10000' };
      }
      return { valid: true, parsedValue: n };
    } catch (error) {
      return { valid: false, error: error.message, hint: 'Use: 1h, 7d, 30m, 90s' };
    }
  }

  _parseDuration(value) {
    const units = { ms: 1, s: 1000, m: 60 * 1000, h: 60 * 60 * 1000, d: 24 * 60 * 60 * 1000 };
    const match = String(value).trim().match(/^([\d.]+)\s*(ms|s|m|h|d)?$/i);
    if (!match) throw new Error(`Invalid duration: ${value}`);
    const unit = match[2] ? match[2].toLowerCase() : 'ms';
    return Math.round(parseFloat(match[1]) * units[unit]);
  }

  _formatDuration(ms) {
    if (ms % (24 * 60 * 60 * 1000) === 0) return ms / (24 * 60 * 60 * 1000) + 'd';
    if (ms % (60 * 60 * 1000) === 0) return ms / (60 * 60 * 1000) + 'h';
    if (ms % (60 * 1000) === 0) return ms / (60 * 1000) + 'm';
    if (ms % 1000 === 0) return ms / 1000 + 's';
    return ms + 'ms';
  }

  _formatValue(key, value) {
    if (DURATION_KEYS.has(key)) return this._formatDuration(value);
    if (PERCENT_KEYS.has(key)) return value + '%';
    return String(value);
  }

  _error(message, extra = {}) {
    return { status: 'error', error: message, report: `Error: ${message}`, ...extra };
  }
}

module.exports = {
  name: 'cache-config',
  description: 'View and change persisted cache settings',
  usage: '/cache-config [--list | --get KEY | --set KEY VALUE | --reset [KEY] | --validate]',

  execute: async (args) => {
    const cmd = new CacheConfigCommand();
    return cmd.execute(args);
  },

  CacheConfigCommand
};
