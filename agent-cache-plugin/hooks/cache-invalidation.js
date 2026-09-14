/**
 * Hook: cache-invalidation
 *
 * CLI entry point: reads stdin JSON, outputs stdout JSON, uses exit codes.
 * Handles cache invalidation, staleness checks, and eviction policies.
 * Runs periodically and on-demand to maintain cache health.
 *
 * Input (stdin JSON): { sessionId: string, reason?: string, timestamp?: number }
 * Output (stdout JSON): { invalidated: boolean, entriesRemoved: number, metricsArchived?: boolean }
 * Exit codes: 0 = success, 1 = error
 */

const cacheSkill = require('../skills/cache-management');
const metricsSkill = require('../skills/metrics-tracker');
const { readStdinJSON } = require('./_stdin-reader');

/**
 * Main hook logic
 */
async function main() {
  try {
    // Read and parse stdin
    const input = await readStdinJSON();

    // Validate required fields
    if (!input.sessionId || typeof input.sessionId !== 'string' || input.sessionId.trim() === '') {
      process.stdout.write(JSON.stringify({
        error: 'Missing or invalid required field: sessionId',
        invalidated: false,
        entriesRemoved: 0
      }) + '\n');
      process.exit(1);
    }

    // Get cache and metrics managers
    const cache = cacheSkill.getSingleton();
    const metrics = metricsSkill.getSingleton();

    const results = {
      invalidated: false,
      entriesRemoved: 0,
      metricsArchived: false
    };

    // Step 1: Check for stale entries (TTL-based invalidation)
    const staleResult = await invalidateStaleEntries(cache);
    results.entriesRemoved += staleResult.count;

    // Step 2: Check for low-value entries (hit-rate based invalidation)
    const lowValueResult = await invalidateLowValueEntries(cache, metrics);
    results.entriesRemoved += lowValueResult.count;

    // Step 3: Enforce size limits (LRU eviction if needed)
    const sizeResult = await enforceSizeLimits(cache);
    results.entriesRemoved += sizeResult.count;

    // Step 4: Record invalidation event
    if (results.entriesRemoved > 0) {
      results.invalidated = true;
      await metrics.recordInvalidation({
        trigger: input.reason || 'on-demand',
        entriesRemoved: results.entriesRemoved,
        entriesUpdated: 0,
        totalRemaining: 0
      });
      results.metricsArchived = true;
    }

    process.stdout.write(JSON.stringify(results) + '\n');
    process.exit(0);

  } catch (error) {
    // Invalid JSON or other execution error
    process.stdout.write(JSON.stringify({
      error: error.message,
      invalidated: false,
      entriesRemoved: 0
    }) + '\n');
    process.exit(1);
  }
}

/**
 * Invalidate entries that have exceeded their TTL
 */
async function invalidateStaleEntries(cache) {
  const now = Date.now();
  const results = {
    count: 0,
    details: []
  };

  try {
    // Get all entries
    const allEntries = await cache.search({
      pattern: '*',
      limit: 10000
    });

    const staleEntries = allEntries.filter(entry => {
      const entryAge = now - entry.metadata.timestamp;
      const ttl = entry.metadata.ttl || (24 * 60 * 60 * 1000); // Default 24h
      return entryAge > ttl;
    });

    // Invalidate stale entries
    for (const entry of staleEntries) {
      const invalidateResult = await cache.invalidate(entry.id);
      results.count += invalidateResult.count;
      results.details.push(`Removed stale entry: ${entry.id}`);
    }

  } catch (error) {
    results.details.push(`Error checking staleness: ${error.message}`);
  }

  return results;
}

/**
 * Invalidate low-value entries (rarely used)
 */
async function invalidateLowValueEntries(cache, metrics) {
  const results = {
    count: 0,
    details: []
  };

  try {
    // Get metrics to identify low-hit entries
    const perf = await metrics.getPerformanceMetrics();

    // Entries with zero hits in the last 7 days are candidates
    const hitThreshold = 0;
    const timeWindow = 7 * 24 * 60 * 60 * 1000; // 7 days

    // In real implementation, would iterate and remove based on hit count
    // Simplified here - would need to track per-entry hit counts in metrics

    return results;

  } catch (error) {
    results.details.push(`Error evaluating entry value: ${error.message}`);
  }

  return results;
}

/**
 * Enforce cache size limits using LRU eviction
 */
async function enforceSizeLimits(cache) {
  const results = {
    count: 0,
    details: []
  };

  try {
    const stats = await cache.stats();

    // Check if over size limit (e.g., 100MB default)
    const MAX_CACHE_SIZE = 100 * 1024 * 1024; // 100MB
    const MAX_ENTRIES = 10000;

    if (stats.cacheSize > MAX_CACHE_SIZE || stats.totalEntries > MAX_ENTRIES) {
      // Evict least recently used entries
      const evictionResult = await cache.enforce({
        maxSize: MAX_CACHE_SIZE,
        maxEntries: MAX_ENTRIES,
        policy: 'LRU'
      });

      results.count = evictionResult.evictedCount;
      results.details.push(
        `Evicted ${evictionResult.evictedCount} entries due to size limits`,
        `Cache size: ${Math.round(stats.cacheSize / 1024 / 1024)}MB / ${Math.round(MAX_CACHE_SIZE / 1024 / 1024)}MB`
      );
    }

  } catch (error) {
    results.details.push(`Error enforcing size limits: ${error.message}`);
  }

  return results;
}

// Run the hook
main();
