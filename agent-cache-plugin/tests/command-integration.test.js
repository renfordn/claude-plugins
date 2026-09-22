/**
 * Test Suite: Command Integration
 *
 * Tests the CLI commands: cache-status, cache-clear, cache-config, end-to-end through
 * scripts/cache-command.js against a throwaway CLAUDE_PLUGIN_DATA dir. Asserts real DB
 * mutations (config persists across processes; clear actually deletes rows), not just exit codes.
 */

const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const cacheCommand = path.join(__dirname, '../scripts/cache-command.js');
const { CacheManager } = require('../skills/sqlite-cache');

let dataDir;

beforeEach(() => {
  dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cache-cmd-'));
});

afterEach(() => {
  fs.rmSync(dataDir, { recursive: true, force: true });
});

function runCommand(args) {
  const env = { ...process.env, CLAUDE_PLUGIN_DATA: dataDir };
  try {
    const result = execFileSync('node', [cacheCommand, ...args.split(' ').filter(Boolean)], {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
      env
    });
    return { output: result, error: '', exitCode: 0 };
  } catch (error) {
    return {
      output: error.stdout || '',
      error: error.stderr || '',
      exitCode: error.status || 1
    };
  }
}

/** Open the same DB the CLI used, to seed rows or assert on them. */
function withDb(fn) {
  const cm = new CacheManager(path.join(dataDir, 'cache.db'));
  try { return fn(cm); } finally { cm.close(); }
}

function seed(cm, key, overrides = {}) {
  cm.store({
    key,
    agent_type: 'agent-tdd',
    task_slug: 'feat-a',
    output_digest: 'd',
    output_blob: '{}',
    token_count: 10,
    ...overrides
  });
}

describe('CLI Commands', () => {
  describe('cache-status command', () => {
    test('status', () => expect(runCommand('status').exitCode).toBe(0));
    test('status --detailed', () => expect(runCommand('status --detailed').exitCode).toBe(0));
    test('status --export json', () => expect(runCommand('status --export json').exitCode).toBe(0));
    test('status --detailed --export json', () =>
      expect(runCommand('status --detailed --export json').exitCode).toBe(0));
  });

  describe('cache-clear command', () => {
    test('no filter deletes nothing and exits 0', () => {
      withDb(cm => seed(cm, 'k1'));
      const result = runCommand('clear');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('Nothing deleted');
      withDb(cm => expect(cm.stats().totalEntries).toBe(1));
    });

    test('--all without --yes asks for confirmation and deletes nothing', () => {
      withDb(cm => seed(cm, 'k1'));
      const result = runCommand('clear --all');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('--all --yes');
      withDb(cm => expect(cm.stats().totalEntries).toBe(1));
    });

    test('--all --yes deletes every row', () => {
      withDb(cm => { seed(cm, 'k1'); seed(cm, 'k2'); });
      const result = runCommand('clear --all --yes');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('Entries Removed:   2');
      withDb(cm => expect(cm.stats().totalEntries).toBe(0));
    });

    test('--agent deletes only that agent_type', () => {
      withDb(cm => {
        seed(cm, 'k1', { agent_type: 'agent-tdd' });
        seed(cm, 'k2', { agent_type: 'agent-isdd:planning-agent' });
      });
      const result = runCommand('clear --agent agent-tdd');
      expect(result.exitCode).toBe(0);
      withDb(cm => {
        expect(cm.retrieve('k1')).toBeNull();
        expect(cm.retrieve('k2')).not.toBeNull();
      });
    });

    test('--task deletes only that task_slug', () => {
      withDb(cm => {
        seed(cm, 'k1', { task_slug: 'feat-a' });
        seed(cm, 'k2', { task_slug: 'feat-b' });
      });
      expect(runCommand('clear --task feat-a').exitCode).toBe(0);
      withDb(cm => {
        expect(cm.retrieve('k1')).toBeNull();
        expect(cm.retrieve('k2')).not.toBeNull();
      });
    });

    test('--older-than keeps fresh rows', () => {
      withDb(cm => seed(cm, 'fresh'));
      expect(runCommand('clear --older-than 7').exitCode).toBe(0);
      withDb(cm => expect(cm.retrieve('fresh')).not.toBeNull());
    });

    test('--older-than 0 deletes rows created before now', () => {
      withDb(cm => seed(cm, 'k1'));
      // created_at < now - 0 → anything at least 1ms old
      const result = runCommand('clear --older-than 0');
      expect(result.exitCode).toBe(0);
      withDb(cm => expect(cm.retrieve('k1')).toBeNull());
    });

    test('--tags a,b maps to agent_type IN (a,b)', () => {
      withDb(cm => {
        seed(cm, 'k1', { agent_type: 'tag1' });
        seed(cm, 'k2', { agent_type: 'tag3' });
        seed(cm, 'k3', { agent_type: 'other' });
      });
      expect(runCommand('clear --tags tag1,tag2,tag3').exitCode).toBe(0);
      withDb(cm => {
        expect(cm.retrieve('k1')).toBeNull();
        expect(cm.retrieve('k2')).toBeNull();
        expect(cm.retrieve('k3')).not.toBeNull();
      });
    });

    test('--id deletes one exact key', () => {
      withDb(cm => { seed(cm, 'k1'); seed(cm, 'k10'); });
      expect(runCommand('clear --id k1').exitCode).toBe(0);
      withDb(cm => {
        expect(cm.retrieve('k1')).toBeNull();
        expect(cm.retrieve('k10')).not.toBeNull();
      });
    });

    test('--pattern deletes substring key matches', () => {
      withDb(cm => { seed(cm, 'abc-1'); seed(cm, 'abc-2'); seed(cm, 'xyz'); });
      expect(runCommand('clear --pattern abc').exitCode).toBe(0);
      withDb(cm => expect(cm.stats().totalEntries).toBe(1));
    });

    test('--before with a bad date exits 1', () => {
      const result = runCommand('clear --before not-a-date');
      expect(result.exitCode).toBe(1);
      expect(result.error).toContain('ISO 8601');
    });
  });

  describe('cache-config command', () => {
    test('--list shows defaults', () => {
      const result = runCommand('config --list');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('Relevance Threshold:   75%');
      expect(result.output).toContain('Default TTL:           3d');
    });

    test('--set persists across processes', () => {
      const set = runCommand('config --set relevanceThreshold 80');
      expect(set.exitCode).toBe(0);
      expect(set.output).toContain('relevanceThreshold = 80% (was 75%)');

      const get = runCommand('config --get relevanceThreshold');
      expect(get.exitCode).toBe(0);
      expect(get.output).toContain('relevanceThreshold = 80%');

      withDb(cm => expect(cm.getConfig().relevanceThreshold).toBe(80));
    });

    test('--set defaultTTL accepts duration units and applies to new stores', () => {
      expect(runCommand('config --set defaultTTL 7d').exitCode).toBe(0);
      withDb(cm => {
        expect(cm.defaultTTL).toBe(7 * 24 * 60 * 60 * 1000);
        seed(cm, 'k1');
        expect(cm.retrieve('k1').ttl).toBe(7 * 24 * 60 * 60 * 1000);
      });
    });

    test('--set maxEntries is enforced by LRU on the next store', () => {
      expect(runCommand('config --set maxEntries 100').exitCode).toBe(0);
      withDb(cm => {
        for (let i = 0; i < 101; i++) seed(cm, `k${i}`);
        expect(cm.stats().totalEntries).toBe(100);
      });
    });

    test('--reset KEY restores one default', () => {
      runCommand('config --set relevanceThreshold 80');
      const result = runCommand('config --reset relevanceThreshold');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('relevanceThreshold = 75% (default)');
      withDb(cm => expect(cm.getConfig().relevanceThreshold).toBe(75));
    });

    test('--reset restores all defaults', () => {
      runCommand('config --set relevanceThreshold 80');
      runCommand('config --set defaultTTL 7d');
      expect(runCommand('config --reset').exitCode).toBe(0);
      withDb(cm => expect(cm.getConfig()).toEqual({
        maxEntries: 10000,
        defaultTTL: 72 * 60 * 60 * 1000,
        relevanceThreshold: 75,
        stalenessThreshold: 24 * 60 * 60 * 1000
      }));
    });

    test('--validate', () => expect(runCommand('config --validate').exitCode).toBe(0));

    test('--list --validate emits both reports', () => {
      const result = runCommand('config --list --validate');
      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('Cache Configuration Report');
      expect(result.output).toContain('Configuration Validation Report');
    });

    test('--validate warns when stalenessThreshold exceeds defaultTTL', () => {
      runCommand('config --set defaultTTL 1h');
      const result = runCommand('config --validate');
      expect(result.output).toContain('stalenessThreshold exceeds defaultTTL');
    });

    test('out-of-range value exits 1 and writes nothing', () => {
      const result = runCommand('config --set relevanceThreshold 200');
      expect(result.exitCode).toBe(1);
      expect(result.error).toContain('at most 95');
      withDb(cm => expect(cm.getConfig().relevanceThreshold).toBe(75));
    });

    test('unknown key exits 1 with the valid keys', () => {
      const result = runCommand('config --set invalidKey invalidValue');
      expect(result.exitCode).toBe(1);
      expect(result.error).toContain('Unknown config key: invalidKey');
    });

    test('retired keys (maxSize, evictionPolicy) are rejected', () => {
      expect(runCommand('config --set maxSize 500MB').exitCode).toBe(1);
      expect(runCommand('config --set evictionPolicy LFU').exitCode).toBe(1);
    });

    test('orchestrator reads persisted thresholds', () => {
      runCommand('config --set relevanceThreshold 90');
      withDb(cm => {
        const { create } = require('../agents/agent-cache-orchestrator');
        const orch = create({ cache: cm, metrics: { recordHit: async () => {}, recordMiss: async () => {} } });
        expect(orch.relevanceThreshold).toBe(90);
      });
    });
  });

  describe('Error handling', () => {
    test('unknown command exits non-zero', () => {
      const result = runCommand('unknown-command');
      expect(result.exitCode).not.toBe(0);
      expect(result.error || result.output).toContain('Unknown command');
    });

    test('--help shows usage', () => expect(runCommand('--help').output).toContain('Usage:'));

    test('--version shows a version', () => {
      const result = runCommand('--version');
      expect(result.exitCode).toBe(0);
      expect(result.output).toMatch(/v\d+\.\d+\.\d+/);
    });
  });
});
