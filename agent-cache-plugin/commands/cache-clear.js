/**
 * Command: /cache-clear
 *
 * Clear cache entries selectively or globally.
 * Usage: /cache-clear [--all|--id <id>|--pattern <pattern>|--agent <agent>|--age <days>|--tag <tag>]
 */

const cacheManagement = require('../skills/sqlite-cache');

class CacheClearCommand {
  constructor() {
    this.cache = cacheManagement.getSingleton();
  }

  /**
   * Execute the cache-clear command
   */
  async execute(args = {}) {
    try {
      // Validate that at least one filter is specified
      if (!args.all && !args.id && !args.pattern && !args.agent && !args.age && !args.tag) {
        return this._requiresConfirmation(
          'No filter specified. Use --all to clear entire cache.',
          args
        );
      }

      // Get current cache state before clearing
      const beforeStats = this.cache.getStats();

      let result;

      if (args.all) {
        result = await this.cache.clear();
        return this._successResponse(
          'ALL_CLEAR',
          result.count,
          beforeStats,
          args
        );
      }

      // Apply specific filters
      let entriesToClear = [];

      if (args.id) {
        const invalidated = await this.cache.invalidate(args.id);
        entriesToClear.push(args.id);
        return this._successResponse(
          'ID_CLEAR',
          invalidated.count,
          beforeStats,
          args
        );
      }

      if (args.pattern) {
        const invalidated = await this.cache.invalidate(args.pattern);
        return this._successResponse(
          'PATTERN_CLEAR',
          invalidated.count,
          beforeStats,
          args
        );
      }

      if (args.agent) {
        // Clear all entries from specific agent
        const entries = await this.cache.search({ tags: [args.agent], limit: 100000 });
        let removed = 0;
        for (const entry of entries) {
          const result = await this.cache.invalidate(entry.id);
          removed += result.count;
        }
        return this._successResponse(
          'AGENT_CLEAR',
          removed,
          beforeStats,
          args
        );
      }

      if (args.age) {
        // Clear entries older than X days
        const ageMs = parseInt(args.age) * 24 * 60 * 60 * 1000;
        const invalidated = await this._clearByAge(ageMs);
        return this._successResponse(
          'AGE_CLEAR',
          invalidated.count,
          beforeStats,
          args
        );
      }

      if (args.tag) {
        // Clear entries with specific tag
        const invalidated = await this._clearByTag(args.tag);
        return this._successResponse(
          'TAG_CLEAR',
          invalidated.count,
          beforeStats,
          args
        );
      }

      return this._errorResponse(new Error('No clear operation performed'));
    } catch (error) {
      return this._errorResponse(error);
    }
  }

  /**
   * Clear entries older than specified age
   */
  async _clearByAge(ageMs) {
    const now = Date.now();
    const entries = await this.cache.search({ pattern: '*', limit: 100000 });

    const toRemove = entries.filter(entry => {
      const entryAge = now - entry.metadata.timestamp;
      return entryAge > ageMs;
    });

    let removed = 0;
    for (const entry of toRemove) {
      const result = await this.cache.invalidate(entry.id);
      removed += result.count;
    }

    return { count: removed };
  }

  /**
   * Clear entries with specific tag
   */
  async _clearByTag(tag) {
    const entries = await this.cache.search({ tags: [tag], limit: 100000 });

    let removed = 0;
    for (const entry of entries) {
      const result = await this.cache.invalidate(entry.id);
      removed += result.count;
    }

    return { count: removed };
  }

  /**
   * Requires user confirmation for the operation
   */
  _requiresConfirmation(message, args) {
    return {
      status: 'requires_confirmation',
      message: message,
      suggestion: 'Specify one of: --all, --id <id>, --pattern <pattern>, --agent <agent>, --age <days>, --tag <tag>',
      examples: [
        '/cache-clear --all',
        '/cache-clear --agent agent-tdd:agent-TDD',
        '/cache-clear --age 7',
        '/cache-clear --pattern "cache-*"',
        '/cache-clear --tag "research"'
      ]
    };
  }

  /**
   * Success response
   */
  _successResponse(clearType, count, beforeStats, args) {
    const afterStats = this.cache.getStats();
    const sizeFreed = beforeStats.cacheSize - afterStats.cacheSize;

    let detail = '';
    switch (clearType) {
      case 'ALL_CLEAR':
        detail = 'Cleared entire cache';
        break;
      case 'ID_CLEAR':
        detail = `Cleared entry: ${args.id}`;
        break;
      case 'PATTERN_CLEAR':
        detail = `Cleared entries matching pattern: ${args.pattern}`;
        break;
      case 'AGENT_CLEAR':
        detail = `Cleared entries from agent: ${args.agent}`;
        break;
      case 'AGE_CLEAR':
        detail = `Cleared entries older than ${args.age} days`;
        break;
      case 'TAG_CLEAR':
        detail = `Cleared entries with tag: ${args.tag}`;
        break;
    }

    const report = `Cache Clear Report
═══════════════════════════════════════════

Operation: ${detail}

RESULTS
───────
Entries Removed:   ${count}
Space Freed:       ${this._formatBytes(sizeFreed)}

BEFORE
──────
Total Entries:     ${beforeStats.totalEntries}
Cache Size:        ${this._formatBytes(beforeStats.cacheSize)} (${beforeStats.utilizationPercent}%)

AFTER
─────
Total Entries:     ${afterStats.totalEntries}
Cache Size:        ${this._formatBytes(afterStats.cacheSize)} (${afterStats.utilizationPercent}%)

═══════════════════════════════════════════`;

    return {
      status: 'success',
      operation: clearType,
      summary: {
        entriesRemoved: count,
        spaceFreed: sizeFreed,
        beforeSize: beforeStats.cacheSize,
        afterSize: afterStats.cacheSize,
        percentReduction: beforeStats.cacheSize > 0
          ? Math.round(((sizeFreed) / beforeStats.cacheSize) * 100)
          : 0
      },
      report: report
    };
  }

  /**
   * Error response
   */
  _errorResponse(error) {
    return {
      status: 'error',
      error: error.message,
      report: `Error clearing cache: ${error.message}`
    };
  }

  /**
   * Format bytes to human readable
   */
  _formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  }
}

module.exports = {
  name: 'cache-clear',
  description: 'Clear cache entries selectively or globally',
  usage: '/cache-clear [--all|--id <id>|--pattern <pattern>|--agent <agent>|--age <days>|--tag <tag>]',

  execute: async (args) => {
    const cmd = new CacheClearCommand();
    return cmd.execute(args);
  },

  CacheClearCommand
};
