/**
 * Hook: pre-agent-spawn
 *
 * CLI entry point: reads stdin JSON, outputs stdout JSON, uses exit codes.
 * Checks cache for similar previous agent runs and decides whether to reuse cached context.
 *
 * Input (stdin JSON): { toolName: string, input: object, sessionId: string }
 * Output (stdout JSON): { cacheHit: boolean, cachedOutput?: object, relevance?: number, ttlRemaining?: number }
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
    if (!input.toolName || typeof input.toolName !== 'string' || input.toolName.trim() === '') {
      writeAllow('Missing or invalid required field: toolName');
      process.exit(0);
    }

    if (!input.sessionId || typeof input.sessionId !== 'string' || input.sessionId.trim() === '') {
      writeAllow('Missing or invalid required field: sessionId');
      process.exit(0);
    }

    if (!input.input || typeof input.input !== 'object') {
      writeAllow('Missing or invalid required field: input (must be object)');
      process.exit(0);
    }

    // Get cache and metrics managers
    const cache = cacheSkill.getSingleton();
    const metrics = metricsSkill.getSingleton();

    // Generate input string for relevance scoring
    const inputStr = JSON.stringify(input.input);

    // Search cache for similar entries
    const cachedCandidates = await cache.search({
      pattern: input.toolName,
      tags: [input.toolName],
      maxAge: 24 * 60 * 60 * 1000, // 24 hours
      limit: 5
    });

    if (cachedCandidates.length === 0) {
      // Cache miss
      await metrics.recordMiss({
        query: inputStr,
        agentType: input.toolName,
        taskType: 'general'
      });

      writeAllow();
      process.exit(0);
    }

    // Score relevance of candidates
    const scoredCandidates = cachedCandidates.map(candidate => ({
      ...candidate,
      relevanceScore: scoreRelevance(inputStr, candidate.prompt)
    })).sort((a, b) => b.relevanceScore - a.relevanceScore);

    const bestMatch = scoredCandidates[0];
    const RELEVANCE_THRESHOLD = 75; // 75% similarity required

    if (bestMatch.relevanceScore >= RELEVANCE_THRESHOLD) {
      const tokenSavings = bestMatch.metadata.tokenCount || 0;
      const now = Date.now();
      const createdAt = bestMatch.metadata.timestamp || now;
      const ttl = bestMatch.metadata.ttl || (24 * 60 * 60 * 1000);
      const ttlRemaining = Math.max(0, ttl - (now - createdAt));

      // Record cache hit
      await metrics.recordHit({
        cachedEntryId: bestMatch.id,
        agentType: input.toolName,
        taskType: 'general',
        tokensSaved: tokenSavings,
        relevanceScore: bestMatch.relevanceScore
      });

      writeAllow('cache hit (informational only, agent proceeds)');
      process.exit(0);
    }

    // Cache miss (below threshold)
    await metrics.recordMiss({
      query: inputStr,
      agentType: input.toolName,
      taskType: 'general'
    });

    writeAllow();
    process.exit(0);

  } catch (error) {
    // Invalid JSON or other execution error
    writeAllow(error.message);
    process.exit(0);
  }
}

/**
 * Write a harness-recognized PreToolUse "allow" decision to stdout.
 * Never sets updatedInput: this hook is informational-only and must never
 * alter or replace the tool call's original input.
 * @param {string} [reason] Optional permissionDecisionReason for observability.
 */
function writeAllow(reason) {
  const hookSpecificOutput = {
    hookEventName: 'PreToolUse',
    permissionDecision: 'allow'
  };
  if (reason) {
    hookSpecificOutput.permissionDecisionReason = reason;
  }
  process.stdout.write(JSON.stringify({ hookSpecificOutput }) + '\n');
}

/**
 * Score relevance of two prompts (0-100)
 * Simplified scoring based on keyword overlap
 */
function scoreRelevance(prompt1, prompt2) {
  const normalize = (text) => {
    try {
      const str = typeof text === 'string' ? text : JSON.stringify(text);
      return str.toLowerCase()
        .split(/\s+/)
        .filter(word => word.length > 3)
        .sort();
    } catch {
      return [];
    }
  };

  const words1 = new Set(normalize(prompt1));
  const words2 = new Set(normalize(prompt2));

  // Jaccard similarity
  const intersection = [...words1].filter(w => words2.has(w)).length;
  const union = new Set([...words1, ...words2]).size;

  return Math.round((intersection / (union || 1)) * 100);
}

// Run the hook
main();
