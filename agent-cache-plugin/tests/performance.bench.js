/**
 * Performance Benchmarks for Agent-Cache Plugin
 *
 * Measures: retrieval time, search speed, hit rates, eviction performance
 */

const cacheManagement = require('../skills/cache-management');
const metricsTracker = require('../skills/metrics-tracker');

class CacheBenchmark {
  constructor() {
    this.results = {
      operations: [],
      metrics: {}
    };
  }

  /**
   * Run all benchmarks
   */
  async runAll() {
    console.log('Starting Agent-Cache Performance Benchmarks...\n');

    await this.benchmarkStoreOperations();
    await this.benchmarkRetrievalOperations();
    await this.benchmarkSearchOperations();
    await this.benchmarkEvictionPerformance();
    await this.benchmarkUnderLoad();
    await this.benchmarkHitRates();

    this.printReport();
    return this.results;
  }

  /**
   * Benchmark store operations
   */
  async benchmarkStoreOperations() {
    const cache = cacheManagement.createManager();
    console.log('📝 Benchmarking Store Operations...');

    const sizes = [100, 1000, 5000];

    for (const size of sizes) {
      const times = [];

      for (let i = 0; i < size; i++) {
        const start = performance.now();
        await cache.store({
          prompt: `Prompt ${i}`,
          output: 'X'.repeat(100),
          metadata: {
            agentType: 'test-agent',
            tags: ['benchmark']
          }
        });
        times.push(performance.now() - start);
      }

      const stats = this._calculateStats(times);
      console.log(`  ✓ ${size} stores: avg ${stats.mean.toFixed(2)}ms, p95 ${stats.p95.toFixed(2)}ms`);

      this.results.operations.push({
        operation: 'store',
        count: size,
        mean: stats.mean,
        p95: stats.p95,
        p99: stats.p99
      });
    }
    console.log('');
  }

  /**
   * Benchmark retrieval operations
   */
  async benchmarkRetrievalOperations() {
    const cache = cacheManagement.createManager();
    console.log('🔍 Benchmarking Retrieval Operations...');

    // Store entries first
    const entryIds = [];
    for (let i = 0; i < 1000; i++) {
      const result = await cache.store({
        prompt: `Prompt ${i}`,
        output: `Output ${i}`,
        metadata: {
          agentType: 'test-agent',
          tokenCount: Math.random() * 500
        }
      });
      entryIds.push(result.entryId);
    }

    // Benchmark retrieval
    const times = [];
    for (const id of entryIds) {
      const start = performance.now();
      await cache.retrieve(id);
      times.push(performance.now() - start);
    }

    const stats = this._calculateStats(times);
    console.log(`  ✓ 1000 retrievals: avg ${stats.mean.toFixed(2)}ms, p95 ${stats.p95.toFixed(2)}ms, p99 ${stats.p99.toFixed(2)}ms`);

    this.results.operations.push({
      operation: 'retrieve',
      count: 1000,
      mean: stats.mean,
      p95: stats.p95,
      p99: stats.p99
    });
    console.log('');
  }

  /**
   * Benchmark search operations
   */
  async benchmarkSearchOperations() {
    const cache = cacheManagement.createManager();
    console.log('🔎 Benchmarking Search Operations...');

    // Setup with various tag combinations
    for (let i = 0; i < 2000; i++) {
      const taskTypes = ['research', 'implementation', 'design', 'testing'];
      const taskType = taskTypes[i % taskTypes.length];

      await cache.store({
        prompt: `Prompt for ${taskType}`,
        output: `Output ${i}`,
        metadata: {
          agentType: 'agent-tdd',
          taskType: taskType,
          tags: [taskType, 'benchmark']
        }
      });
    }

    // Benchmark different search scenarios
    const scenarios = [
      { pattern: '*', tags: [], limit: 100, name: 'Broad search (limit 100)' },
      { pattern: '*', tags: ['research'], limit: 100, name: 'Tag filter' },
      { pattern: 'Prompt', tags: [], limit: 50, name: 'Pattern match' },
      { pattern: '*', tags: ['research', 'benchmark'], limit: 100, name: 'Multi-tag filter' }
    ];

    for (const scenario of scenarios) {
      const times = [];
      for (let i = 0; i < 10; i++) {
        const start = performance.now();
        await cache.search(scenario);
        times.push(performance.now() - start);
      }

      const stats = this._calculateStats(times);
      console.log(`  ✓ ${scenario.name}: avg ${stats.mean.toFixed(2)}ms`);

      this.results.operations.push({
        operation: 'search',
        scenario: scenario.name,
        mean: stats.mean,
        p95: stats.p95
      });
    }
    console.log('');
  }

  /**
   * Benchmark eviction performance
   */
  async benchmarkEvictionPerformance() {
    console.log('🗑️  Benchmarking Eviction Performance...');

    const policies = ['LRU', 'LFU', 'FIFO'];

    for (const policy of policies) {
      const cache = cacheManagement.createManager({
        maxSize: 5 * 1024 * 1024, // 5 MB
        maxEntries: 1000,
        evictionPolicy: policy
      });

      const start = performance.now();
      let storeCount = 0;

      // Fill until eviction triggers
      while (storeCount < 5000) {
        const result = await cache.store({
          prompt: `Prompt ${storeCount}`,
          output: 'X'.repeat(1000),
          metadata: {
            agentType: 'test-agent',
            tags: ['load-test']
          }
        });
        if (result.success) storeCount++;
      }

      const elapsed = performance.now() - start;
      const stats = cache.getStats();

      console.log(`  ✓ ${policy}: ${storeCount} stores in ${elapsed.toFixed(0)}ms, evicted ${stats.totalEvictions} entries`);

      this.results.operations.push({
        operation: 'eviction',
        policy: policy,
        timeMs: elapsed,
        evictions: stats.totalEvictions
      });
    }
    console.log('');
  }

  /**
   * Benchmark under load
   */
  async benchmarkUnderLoad() {
    const cache = cacheManagement.createManager();
    const metrics = metricsTracker.createTracker();

    console.log('⚡ Benchmarking Under Load (100 concurrent ops)...');

    // Simulate concurrent load
    const operations = [];

    for (let i = 0; i < 100; i++) {
      operations.push(
        cache.store({
          prompt: `Load test prompt ${i}`,
          output: `Output ${i}`,
          metadata: {
            agentType: 'test-agent',
            tokenCount: Math.random() * 1000
          }
        })
      );
    }

    const start = performance.now();
    const results = await Promise.all(operations);
    const elapsed = performance.now() - start;

    const successful = results.filter(r => r.success).length;

    console.log(`  ✓ 100 concurrent stores: ${elapsed.toFixed(0)}ms (${(100/elapsed*1000).toFixed(0)} ops/sec), success rate ${(successful/100*100).toFixed(1)}%\n`);

    this.results.operations.push({
      operation: 'concurrent_store',
      count: 100,
      timeMs: elapsed,
      opsPerSec: (100/elapsed*1000)
    });
  }

  /**
   * Benchmark hit rates under various scenarios
   */
  async benchmarkHitRates() {
    const cache = cacheManagement.createManager();
    const metrics = metricsTracker.createTracker();

    console.log('📈 Benchmarking Hit Rates...');

    // Scenario 1: Repeated queries (high hit rate expected)
    const prompts = [];
    for (let i = 0; i < 10; i++) {
      prompts.push(`Repeated prompt ${i}`);
    }

    // Store base entries
    for (const prompt of prompts) {
      await cache.store({
        prompt: prompt,
        output: 'Cached result',
        metadata: {
          agentType: 'test-agent',
          tokenCount: 200
        }
      });
    }

    // Query with repetition
    let hits = 0;
    for (let round = 0; round < 5; round++) {
      for (const prompt of prompts) {
        const results = await cache.search({
          pattern: '*',
          limit: 100
        });
        const match = results.find(r => r.prompt === prompt);
        if (match) hits++;
      }
    }

    const expectedHits = prompts.length * 5;
    const hitRate = (hits / expectedHits * 100).toFixed(1);

    console.log(`  ✓ Repeated query hit rate: ${hitRate}%`);
    console.log(`  ✓ Avg retrieval from cache stats: ${cache.getStats().hitRate.toFixed(3)}`);

    this.results.metrics = {
      hitRate: hitRate,
      cacheSize: cache.getStats().cacheSize,
      totalEntries: cache.getStats().totalEntries
    };
    console.log('');
  }

  /**
   * Calculate statistics from timing array
   */
  _calculateStats(times) {
    const sorted = times.sort((a, b) => a - b);
    const mean = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const median = sorted[Math.floor(sorted.length / 2)];
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    const p99 = sorted[Math.floor(sorted.length * 0.99)];

    return { mean, median, p95, p99 };
  }

  /**
   * Print benchmark report
   */
  printReport() {
    console.log('\n' + '='.repeat(60));
    console.log('PERFORMANCE BENCHMARK REPORT');
    console.log('='.repeat(60) + '\n');

    console.log('OPERATIONS SUMMARY');
    console.log('─'.repeat(60));

    const grouped = {};
    this.results.operations.forEach(op => {
      if (!grouped[op.operation]) grouped[op.operation] = [];
      grouped[op.operation].push(op);
    });

    Object.entries(grouped).forEach(([opName, ops]) => {
      console.log(`\n${opName.toUpperCase()}:`);
      ops.forEach(op => {
        let summary = `  • `;
        if (op.count) summary += `${op.count} ops`;
        if (op.mean) summary += ` - avg ${op.mean.toFixed(2)}ms`;
        if (op.p95) summary += ` p95 ${op.p95.toFixed(2)}ms`;
        if (op.opsPerSec) summary += ` (${op.opsPerSec.toFixed(0)} ops/sec)`;
        if (op.policy) summary += ` [${op.policy}]`;
        if (op.evictions) summary += ` evicted ${op.evictions}`;
        console.log(summary);
      });
    });

    console.log('\n' + '─'.repeat(60));
    console.log('CACHE METRICS');
    console.log('─'.repeat(60));
    console.log(`Hit Rate: ${this.results.metrics.hitRate}%`);
    console.log(`Total Entries: ${this.results.metrics.totalEntries}`);
    console.log(`Cache Size: ${(this.results.metrics.cacheSize / 1024).toFixed(1)} KB`);

    console.log('\n' + '='.repeat(60) + '\n');
  }
}

// Export for use
module.exports = { CacheBenchmark };

// Run if executed directly
if (require.main === module) {
  const benchmark = new CacheBenchmark();
  benchmark.runAll().catch(console.error);
}
