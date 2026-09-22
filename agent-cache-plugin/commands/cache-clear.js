/**
 * Command: /cache-clear
 *
 * Delete cache entries by filter, or everything with --all --yes.
 * Usage: /cache-clear [--all --yes] [--agent AGENT] [--task TASK] [--older-than DAYS]
 *                     [--before DATE] [--pattern SUBSTR] [--id KEY] [--tags A,B]
 *
 * Filters combine (AND). `--tags` selects by agent_type, the only tag-like column the
 * SQLite backend has. Bytes freed are not reported: the backend does not track entry size.
 */

const sqliteCache = require('../skills/sqlite-cache');

const DAY_MS = 24 * 60 * 60 * 1000;

class CacheClearCommand {
  /**
   * @param {object} [deps] - Optional dependency injection for testing.
   * @param {object} [deps.cache] - CacheManager instance.
   */
  constructor(deps = {}) {
    this.cache = deps.cache || sqliteCache.getSingleton();
  }

  async execute(args = {}) {
    try {
      const before = this.cache.stats();

      if (args.all) {
        if (!args.yes) {
          return {
            status: 'requires_confirmation',
            message: `This will delete ALL ${before.totalEntries} cache entries. Re-run with --yes to confirm.`,
            report: `⚠️  This will delete ALL ${before.totalEntries} cache entries.\nRe-run with --all --yes to confirm.`
          };
        }
        const { deletedCount } = this.cache.clear();
        return this._success('Cleared entire cache', deletedCount, before);
      }

      const filters = this._filtersFrom(args);
      if (filters.error) {
        return this._error(filters.error);
      }
      if (Object.keys(filters.opts).length === 0) {
        return {
          status: 'requires_confirmation',
          message: 'No filter specified. Use --all --yes to clear the entire cache.',
          suggestion: 'Specify one of: --all --yes, --agent AGENT, --task TASK, --older-than DAYS, --before DATE, --pattern SUBSTR, --id KEY, --tags A,B',
          report: [
            'No filter specified. Nothing deleted.',
            'Examples:',
            '  /cache-clear --all --yes',
            '  /cache-clear --agent agent-tdd:agent-TDD',
            '  /cache-clear --older-than 7',
            '  /cache-clear --task my-feature',
            '  /cache-clear --pattern abc123'
          ].join('\n')
        };
      }

      let count;
      if (filters.opts.id) {
        count = this.cache.invalidate(filters.opts.id).count;
      } else {
        count = this.cache.invalidateWhere(filters.opts).count;
      }
      return this._success(filters.description, count, before);
    } catch (error) {
      return this._error(error.message);
    }
  }

  /** Translate CLI args into invalidateWhere() options plus a human description. */
  _filtersFrom(args) {
    const opts = {};
    const desc = [];

    const id = args.id || args.key;
    if (id) {
      opts.id = String(id);
      desc.push(`key ${id}`);
    }
    if (args.pattern) {
      opts.pattern = String(args.pattern);
      desc.push(`key contains "${args.pattern}"`);
    }
    const tags = [];
    if (args.agent) tags.push(...String(args.agent).split(',').map(s => s.trim()).filter(Boolean));
    if (args.tags) tags.push(...String(args.tags).split(',').map(s => s.trim()).filter(Boolean));
    if (args.tag) tags.push(...String(args.tag).split(',').map(s => s.trim()).filter(Boolean));
    if (tags.length) {
      opts.tags = tags;
      desc.push(`agent in [${tags.join(', ')}]`);
    }
    if (args.task) {
      opts.taskSlug = String(args.task);
      desc.push(`task ${args.task}`);
    }
    const olderThan = args['older-than'] !== undefined ? args['older-than'] : args.age;
    if (olderThan !== undefined) {
      const days = Number(olderThan);
      if (!Number.isFinite(days) || days < 0) return { error: `--older-than must be a number of days, got "${olderThan}"` };
      opts.olderThan = days * DAY_MS;
      desc.push(`older than ${days} day${days === 1 ? '' : 's'}`);
    }
    if (args.before) {
      const ts = Date.parse(String(args.before));
      if (Number.isNaN(ts)) return { error: `--before must be an ISO 8601 date, got "${args.before}"` };
      opts.before = ts;
      desc.push(`created before ${new Date(ts).toISOString()}`);
    }

    return { opts, description: `Cleared entries: ${desc.join(' AND ')}` };
  }

  _success(detail, count, before) {
    const after = this.cache.stats();
    const report = `Cache Clear Report
═══════════════════════════════════════════

Operation: ${detail}

Entries Removed:   ${count}
Before:            ${before.totalEntries} entries
After:             ${after.totalEntries} entries

═══════════════════════════════════════════`;
    return {
      status: 'success',
      summary: { entriesRemoved: count, before: before.totalEntries, after: after.totalEntries },
      report
    };
  }

  _error(message) {
    return { status: 'error', error: message, report: `Error clearing cache: ${message}` };
  }
}

module.exports = {
  name: 'cache-clear',
  description: 'Delete cache entries by filter, or everything with --all --yes',
  usage: '/cache-clear [--all --yes | --agent AGENT | --task TASK | --older-than DAYS | --before DATE | --pattern SUBSTR | --id KEY | --tags A,B]',

  execute: async (args) => {
    const cmd = new CacheClearCommand();
    return cmd.execute(args);
  },

  CacheClearCommand
};
