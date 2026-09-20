/**
 * Agent: Cache Orchestrator
 *
 * Orchestrates cache decisions - decides whether to use cached contexts
 * or perform fresh reasoning based on relevance scoring and validation.
 */

const cacheManagement = require('../../skills/sqlite-cache');
const metricsTracker = require('../../skills/metrics-tracker');

class CacheOrchestrator {
  constructor(options = {}) {
    this.cache = options.cache || cacheManagement.getSingleton();
    this.metrics = options.metrics || metricsTracker.getSingleton();
    this.relevanceThreshold = options.relevanceThreshold || 75;
    this.stalenessThreshold = options.stalenessThreshold || 24 * 60 * 60 * 1000; // 24h
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
        limit: 10
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

      // Step 3: Make decision
      if (bestMatch.relevanceScore >= this.relevanceThreshold) {
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

        return {
          decision: 'fresh_reasoning',
          cachedContextId: null,
          relevanceScore: bestMatch.relevanceScore,
          tokenSavings: 0,
          reasoning: `Best match relevance (${bestMatch.relevanceScore}%) below threshold (${this.relevanceThreshold}%)`
        };
      }
    } catch (error) {
      console.error('Orchestrator error:', error);
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
    return this.cache.getStats();
  }

  /**
   * Configure cache and orchestrator settings
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
   * Score relevance between two prompts using Jaccard similarity
   */
  _scoreRelevance(prompt1, prompt2) {
    const normalize = (text) => {
      return text
        .toLowerCase()
        .split(/\s+/)
        .filter(word => word.length > 3)
        .sort();
    };

    const words1 = normalize(prompt1);
    const words2 = normalize(prompt2);

    const set1 = new Set(words1);
    const set2 = new Set(words2);

    // Jaccard similarity: |intersection| / |union|
    const intersection = [...set1].filter(w => set2.has(w)).length;
    const union = new Set([...set1, ...set2]).size;

    return Math.round((intersection / (union || 1)) * 100);
  }

  /**
   * Check for conflicts between parameters
   */
  _checkConflicts(cachedParams, currentParams) {
    const criticalParams = ['userId', 'projectId', 'domain', 'noCache'];

    for (const param of criticalParams) {
      if (cachedParams[param] && currentParams[param]) {
        if (cachedParams[param] !== currentParams[param]) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Find specific conflicts
   */
  _findConflicts(cachedParams, currentParams) {
    const conflicts = [];
    const criticalParams = ['userId', 'projectId', 'domain'];

    for (const param of criticalParams) {
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

// Export agent
module.exports = {
  name: 'agent-cache-orchestrator',
  version: '1.0.0',
  description: 'Orchestrates cache decisions and context reuse',

  create: (options) => new CacheOrchestrator(options),

  /**
   * Main agent entry point for Cowork integration
   */
  async execute(input) {
    const orchestrator = new CacheOrchestrator(input.options || {});

    const decision = await orchestrator.makeDecision({
      agentType: input.agentType,
      prompt: input.prompt,
      parameters: input.parameters
    });

    return {
      status: 'completed',
      result: decision
    };
  },

  // Export class for testing
  CacheOrchestrator
};
