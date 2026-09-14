/**
 * Hook: post-agent-completion
 *
 * CLI entry point: reads stdin JSON, outputs stdout JSON, uses exit codes.
 * Stores the agent output in cache for future reuse.
 *
 * Input (stdin JSON): { toolName: string, input: object, output: object, sessionId: string, metadata?: object }
 * Output (stdout JSON): { stored: boolean, tokensSaved?: number, cacheKey?: string }
 * Exit codes: 0 = success, 1 = error
 */

const cacheSkill = require('../skills/cache-management');
const metricsSkill = require('../skills/metrics-tracker');
const { readStdinJSON } = require('./_stdin-reader');
const { sanitizeParameters } = require('../utils/credential-sanitizer');

/**
 * Main hook logic
 */
async function main() {
  try {
    // Read and parse stdin
    const input = await readStdinJSON();

    // Validate required fields
    if (!input.toolName || typeof input.toolName !== 'string' || input.toolName.trim() === '') {
      writePostToolUse();
      process.exit(0);
    }

    if (!input.sessionId || typeof input.sessionId !== 'string' || input.sessionId.trim() === '') {
      writePostToolUse();
      process.exit(0);
    }

    if (!input.output || typeof input.output !== 'object') {
      writePostToolUse();
      process.exit(0);
    }

    if (!input.input || typeof input.input !== 'object') {
      writePostToolUse();
      process.exit(0);
    }

    // Get cache and metrics managers
    const cache = cacheSkill.getSingleton();
    const metrics = metricsSkill.getSingleton();

    // Determine if output is cacheable
    const metadata = input.metadata || {};
    const parameters = metadata.parameters || {};
    const isCacheable = determineCacheability(input.output, parameters);

    if (!isCacheable) {
      writePostToolUse();
      process.exit(0);
    }

    // Prepare cache entry
    const inputStr = JSON.stringify(input.input);
    const cacheEntry = {
      id: undefined, // Let cache manager generate
      prompt: inputStr,
      output: serializeOutput(input.output),
      metadata: {
        agentType: input.toolName,
        taskType: parameters.taskType || 'general',
        tags: buildTags(input.toolName, parameters),
        tokenCount: (metadata.inputTokens || 0) + (metadata.outputTokens || 0),
        inputTokens: metadata.inputTokens || 0,
        outputTokens: metadata.outputTokens || 0,
        executionTime: metadata.executionTimeMs || 0,
        timestamp: Date.now(),
        ttl: calculateTTL(parameters),
        parameters: sanitizeParameters(parameters)
      }
    };

    // Store in cache
    const storeResult = await cache.store(cacheEntry);

    if (storeResult.success) {
      const tokensSaved = cacheEntry.metadata.tokenCount;

      // Record cache storage event (stub - metrics doesn't have recordCacheStore in current implementation)
      await metrics.recordHit({
        cachedEntryId: storeResult.entryId,
        agentType: input.toolName,
        taskType: parameters.taskType || 'general',
        tokensSaved: tokensSaved,
        relevanceScore: 100
      });

      writePostToolUse(`cache: stored (tokensSaved=${tokensSaved}, cacheKey=${storeResult.entryId})`);
      process.exit(0);
    } else {
      writePostToolUse();
      process.exit(0);
    }

  } catch (error) {
    // Invalid JSON or other execution error
    writePostToolUse();
    process.exit(0);
  }
}

/**
 * Write a harness-recognized PostToolUse decision to stdout.
 * @param {string} [additionalContext] Optional free-text context (e.g. cache-store facts).
 */
function writePostToolUse(additionalContext) {
  const hookSpecificOutput = { hookEventName: 'PostToolUse' };
  if (additionalContext) {
    hookSpecificOutput.additionalContext = additionalContext;
  }
  process.stdout.write(JSON.stringify({ hookSpecificOutput }) + '\n');
}

/**
 * Determine if agent output should be cached
 */
function determineCacheability(output, parameters) {
  // Don't cache if explicitly marked as non-cacheable
  if (parameters && parameters.noCache === true) {
    return false;
  }

  // Don't cache if output contains time-sensitive markers
  try {
    const outputStr = JSON.stringify(output).toLowerCase();
    const timeSensitivePatterns = ['current time', 'now', 'today', 'live data', 'real-time'];
    if (timeSensitivePatterns.some(pattern => outputStr.includes(pattern))) {
      return false;
    }
  } catch {
    // Fallback for circular references
  }

  // Don't cache if output is randomized or user-specific
  if (parameters && (parameters.isRandomized || parameters.isUserSpecific)) {
    return false;
  }

  return true;
}

/**
 * Serialize output for storage (handle non-JSON types)
 */
function serializeOutput(output) {
  if (typeof output === 'string') {
    return output;
  }
  try {
    return JSON.stringify(output);
  } catch (e) {
    // Fallback for circular references or other issues
    return String(output);
  }
}

/**
 * Build metadata tags for cache entry
 */
function buildTags(agentType, parameters) {
  const tags = [agentType];

  if (parameters && parameters.taskType) {
    tags.push(parameters.taskType);
  }

  if (parameters && parameters.domain) {
    tags.push(parameters.domain);
  }

  if (parameters && parameters.complexity) {
    tags.push(`complexity-${parameters.complexity}`);
  }

  return tags.filter(Boolean);
}

/**
 * Calculate TTL (time-to-live) for cache entry
 */
function calculateTTL(parameters) {
  // Override with explicit TTL if provided
  if (parameters && parameters.cacheTTL) {
    return parameters.cacheTTL;
  }

  // Default TTLs by complexity
  const complexity = (parameters && parameters.complexity) || 'medium';
  const ttlMap = {
    simple: 7 * 24 * 60 * 60 * 1000,      // 7 days
    medium: 3 * 24 * 60 * 60 * 1000,      // 3 days
    complex: 24 * 60 * 60 * 1000,         // 1 day
    'high-risk': 4 * 60 * 60 * 1000       // 4 hours
  };

  return ttlMap[complexity] || ttlMap.medium;
}

// Run the hook
main();
