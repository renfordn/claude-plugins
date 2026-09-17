/**
 * Skill: Cache Orchestration
 *
 * Orchestrates cache decisions - decides whether to use cached contexts
 * or perform fresh reasoning based on relevance scoring and validation.
 *
 * This skill is an internal implementation used by hooks and plugins,
 * not user-invocable.
 *
 * Core responsibility: Given a prompt and context, evaluate cached entries
 * for relevance, staleness, and conflicts, then recommend whether to use
 * cached output or perform fresh reasoning.
 */

const cacheManagement = require('../cache-management');
const metricsTracker = require('../metrics-tracker');

// Configuration constants (extracted for maintainability)
const CONFIG = {
  RELEVANCE_THRESHOLD: 75,
  STALENESS_THRESHOLD_MS: 24 * 60 * 60 * 1000, // 24 hours
  CANDIDATE_LIMIT: 10,
  MIN_WORD_LENGTH: 3,
  CRITICAL_PARAMS: ['userId', 'projectId', 'domain', 'model', 'modelTier', 'noCache']
};

class CacheOrchestration {
  constructor(options = {}) {
    this.cache = options.cache || cacheManagement.getSingleton();
    this.metrics = options.metrics || metricsTracker.getSingleton();
    this.relevanceThreshold = options.relevanceThreshold || CONFIG.RELEVANCE_THRESHOLD;
    this.stalenessThreshold = options.stalenessThreshold || CONFIG.STALENESS_THRESHOLD_MS;
  }

  /**
   * Make a cache reuse decision
   */
  async makeDecision(context) {
    try {
      const {
        agentType,
        prompt,
        parameters = {},
        currentTime = Date.now()
      } = context;

      // Step 1: Query cache for similar agent runs
      const candidates = await this.cache.search({
        pattern: agentType,
        tags: [agentType, parameters.taskType || 'general'].filter(Boolean),
        maxAge: this.stalenessThreshold,
        limit: CONFIG.CANDIDATE_LIMIT
      });

      if (candidates.length === 0) {
        await this.metrics.recordMiss({
          query: prompt,
          taskType: parameters.taskType || 'general',
          agentType: agentType
        });

        return {
          decision: 'fresh_reasoning',
          cachedContextId: null,
          relevanceScore: 0,
          tokenSavings: 0,
          reasoning: 'No relevant cached contexts found'
        };
      }

      // Step 2: Score candidates by relevance
      const scored = candidates.map(candidate => ({
        ...candidate,
        relevanceScore: this._scoreRelevance(prompt, candidate.prompt)
      })).sort((a, b) => b.relevanceScore - a.relevanceScore);

      const bestMatch = scored[0];

      // Step 3: Check for conflicts (including model dimension)
      const hasConflicts = this._checkConflicts(
        bestMatch.metadata?.parameters || {},
        parameters || {}
      );

      // Step 4: Make decision
      if (bestMatch.relevanceScore >= this.relevanceThreshold && !hasConflicts) {
        // Use cache
        const tokenSavings = bestMatch.metadata?.tokenCount || 0;

        await this.metrics.recordHit({
          cachedEntryId: bestMatch.id,
          taskType: parameters.taskType || 'general',
          agentType: agentType,
          tokensSaved: tokenSavings,
          relevanceScore: bestMatch.relevanceScore
        });

        return {
          decision: 'use_cache',
          cachedContextId: bestMatch.id,
          relevanceScore: bestMatch.relevanceScore,
          tokenSavings: tokenSavings,
          reasoning: `Cache hit: ${bestMatch.relevanceScore}% relevance match (threshold: ${this.relevanceThreshold}%)`
        };
      } else {
        // Record miss
        await this.metrics.recordMiss({
          query: prompt,
          taskType: parameters.taskType || 'general',
          agentType: agentType
        });

        const reason = hasConflicts
          ? `Parameter conflicts detected (model mismatch or other critical params)`
          : `Best match relevance (${bestMatch.relevanceScore}%) below threshold (${this.relevanceThreshold}%)`;

        return {
          decision: 'fresh_reasoning',
          cachedContextId: null,
          relevanceScore: bestMatch.relevanceScore,
          tokenSavings: 0,
          reasoning: reason
        };
      }
    } catch (error) {
      console.error('Orchestration error:', error);
      return {
        decision: 'fresh_reasoning',
        cachedContextId: null,
        relevanceScore: 0,
        tokenSavings: 0,
        reasoning: `Error during cache check: ${error.message}`
      };
    }
  }

  /**
   * Evaluate and validate a cached context
   */
  async validateCachedContext(cachedContextId, currentContext) {
    try {
      const cached = await this.cache.retrieve(cachedContextId);

      if (!cached.found) {
        return {
          isValid: false,
          recommendation: 'discard',
          reason: 'Cache entry not found or expired'
        };
      }

      // Check age
      const age = Date.now() - cached.entry.metadata.timestamp;
      const isStale = age > this.stalenessThreshold;

      // Score relevance to current context
      const relevance = this._scoreRelevance(
        currentContext.prompt,
        cached.entry.prompt
      );

      // Check for model dimension mismatch (legacy entries without model)
      const hasModelMismatch = this._checkModelDimensionMismatch(
        cached.entry.metadata.parameters || {},
        currentContext.parameters || {}
      );

      // Check for conflicts
      const hasConflicts = this._checkConflicts(
        cached.entry.metadata.parameters || {},
        currentContext.parameters || {}
      );

      if (isStale) {
        return {
          isValid: false,
          recommendation: 'discard',
          reason: 'Cache entry is stale',
          age: age
        };
      }

      if (hasModelMismatch) {
        return {
          isValid: false,
          recommendation: 'discard',
          reason: 'Cache entry lacks model dimension (legacy entry)',
          modelMismatch: {
            cached: cached.entry.metadata.parameters || {},
            current: currentContext.parameters || {}
          }
        };
      }

      if (hasConflicts) {
        return {
          isValid: false,
          recommendation: 'discard',
          reason: 'Parameter conflicts detected',
          conflicts: this._findConflicts(
            cached.entry.metadata.parameters || {},
            currentContext.parameters || {}
          )
        };
      }

      if (relevance < this.relevanceThreshold) {
        return {
          isValid: true,
          recommendation: 'update',
          relevance: relevance,
          reason: 'Cache entry acceptable but consider refreshing'
        };
      }

      return {
        isValid: true,
        recommendation: 'use',
        relevance: relevance,
        reason: 'Cache entry valid and relevant'
      };
    } catch (error) {
      return {
        isValid: false,
        recommendation: 'discard',
        reason: `Validation error: ${error.message}`
      };
    }
  }

  /**
   * Get cache metrics and statistics
   */
  async getStats() {
    return this.cache.stats();
  }

  /**
   * Configure cache and orchestration settings
   */
  async configure(options) {
    if (options.relevanceThreshold !== undefined) {
      this.relevanceThreshold = options.relevanceThreshold;
    }

    if (options.stalenessThreshold !== undefined) {
      this.stalenessThreshold = options.stalenessThreshold;
    }

    const cacheConfig = await this.cache.configure(options.cache || {});

    return {
      success: true,
      settings: {
        relevanceThreshold: this.relevanceThreshold,
        stalenessThreshold: this.stalenessThreshold,
        cache: cacheConfig
      }
    };
  }

  // Private methods

  /**
   * Score relevance between two prompts using Jaccard similarity.
   *
   * Algorithm: Word-based similarity ignoring order and short words (<3 chars).
   * Jaccard = |intersection| / |union| of word sets, scaled to 0-100.
   *
   * Examples:
   * - "test prompt" vs "test prompt" = 100
   * - "test prompt" vs "test" = ~67 (1 word in common, 2 unique total)
   * - "test" vs "completely different" = 0
   */
  _scoreRelevance(prompt1, prompt2) {
    const normalize = (text) => {
      return text
        .toLowerCase()
        .split(/\s+/)
        .filter(word => word.length > CONFIG.MIN_WORD_LENGTH)
        .sort();
    };

    const words1 = normalize(prompt1 || '');
    const words2 = normalize(prompt2 || '');

    const set1 = new Set(words1);
    const set2 = new Set(words2);

    // Jaccard similarity: |intersection| / |union|
    const intersection = [...set1].filter(w => set2.has(w)).length;
    const union = new Set([...set1, ...set2]).size;

    return Math.round((intersection / (union || 1)) * 100);
  }

  /**
   * Check if model dimension is missing in cached entry but present in current context.
   * Legacy cache entries without model/modelTier should be treated as misses.
   * Returns true if current context has model/modelTier but cached doesn't, false otherwise.
   */
  _checkModelDimensionMismatch(cachedParams, currentParams) {
    const modelFields = ['model', 'modelTier'];
    const currentHasModel = modelFields.some(field => currentParams[field] !== undefined);
    const cachedHasModel = modelFields.some(field => cachedParams[field] !== undefined);

    // Only flag mismatch if current has model but cached doesn't
    return currentHasModel && !cachedHasModel;
  }

  /**
   * Check if any critical parameters conflict between cached and current contexts.
   * Returns true if any mismatch found, false otherwise.
   */
  _checkConflicts(cachedParams, currentParams) {
    for (const param of CONFIG.CRITICAL_PARAMS) {
      if (cachedParams[param] && currentParams[param]) {
        if (cachedParams[param] !== currentParams[param]) {
          return true;
        }
      }
    }
    return false;
  }

  /**
   * Find and collect specific parameter conflicts.
   * Only includes context-specific params (excludes noCache).
   */
  _findConflicts(cachedParams, currentParams) {
    const conflicts = [];
    const contextParams = CONFIG.CRITICAL_PARAMS.filter(p => p !== 'noCache');

    for (const param of contextParams) {
      if (cachedParams[param] && currentParams[param]) {
        if (cachedParams[param] !== currentParams[param]) {
          conflicts.push({
            parameter: param,
            cached: cachedParams[param],
            current: currentParams[param]
          });
        }
      }
    }
    return conflicts;
  }
}

// Singleton instance
let singleton = null;

/**
 * Get or create singleton instance
 */
function getSingleton(options) {
  if (!singleton) {
    singleton = new CacheOrchestration(options);
  }
  return singleton;
}

/**
 * Reset singleton (for testing)
 */
function resetSingleton() {
  singleton = null;
}

module.exports = {
  CacheOrchestration,
  getSingleton,
  resetSingleton
};
