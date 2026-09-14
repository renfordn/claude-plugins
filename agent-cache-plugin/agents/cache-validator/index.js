/**
 * Agent: Cache Validator
 *
 * Validates cache hits, scores relevance, and detects stale or irrelevant entries.
 * Provides confidence scores and recommendations for cache reuse.
 */

class CacheValidator {
  constructor(options = {}) {
    this.minRelevanceScore = options.minRelevanceScore || 70;
    this.maxEntryAge = options.maxEntryAge || 7 * 24 * 60 * 60 * 1000; // 7 days
  }

  /**
   * Validate a cache entry
   */
  async validate(cachedEntry, currentContext) {
    try {
      const validationResults = {
        isValid: true,
        issues: [],
        relevanceScore: 0,
        isStale: false,
        hasConflicts: false,
        confidence: 100
      };

      // Check 1: Entry integrity
      const integrityCheck = this._validateIntegrity(cachedEntry);
      if (!integrityCheck.valid) {
        validationResults.isValid = false;
        validationResults.issues.push(...integrityCheck.issues);
        validationResults.confidence -= 30;
      }

      // Check 2: Staleness
      const now = Date.now();
      const age = now - cachedEntry.metadata.timestamp;
      validationResults.isStale = age > this.maxEntryAge;

      if (validationResults.isStale) {
        validationResults.isValid = false;
        validationResults.issues.push('Entry exceeds maximum age');
        validationResults.confidence -= 50;
      }

      // Check 3: Relevance scoring
      validationResults.relevanceScore = this._scoreRelevance(
        cachedEntry.prompt,
        currentContext.task
      );

      if (validationResults.relevanceScore < this.minRelevanceScore) {
        validationResults.isValid = false;
        validationResults.issues.push(
          `Relevance score (${validationResults.relevanceScore}) below minimum (${this.minRelevanceScore})`
        );
        validationResults.confidence -= 40;
      }

      // Check 4: Parameter conflicts
      const conflicts = this._checkParameterConflicts(
        cachedEntry.metadata.parameters || {},
        currentContext.parameters || {}
      );

      if (conflicts.length > 0) {
        validationResults.hasConflicts = true;
        validationResults.issues.push(`Parameter conflicts: ${conflicts.join(', ')}`);
        validationResults.confidence -= 60;
      }

      // Check 5: Output format validation
      const formatCheck = this._validateOutputFormat(cachedEntry.output);
      if (!formatCheck.valid) {
        validationResults.issues.push(`Invalid output format: ${formatCheck.reason}`);
        validationResults.confidence -= 20;
      }

      // Determine recommendation
      validationResults.recommendation = this._makeRecommendation(validationResults);

      // Ensure confidence is valid
      validationResults.confidence = Math.max(0, Math.min(100, validationResults.confidence));

      return validationResults;
    } catch (error) {
      return {
        isValid: false,
        issues: [`Validation error: ${error.message}`],
        relevanceScore: 0,
        isStale: true,
        hasConflicts: true,
        confidence: 0,
        recommendation: 'discard'
      };
    }
  }

  /**
   * Validate multiple cache entries and return best match
   */
  async validateMultiple(cachedEntries, currentContext) {
    const validations = await Promise.all(
      cachedEntries.map(entry => this.validate(entry, currentContext))
    );

    // Score entries by validity and relevance
    const scored = cachedEntries.map((entry, idx) => ({
      entry,
      validation: validations[idx],
      score: this._calculateScore(validations[idx])
    })).sort((a, b) => b.score - a.score);

    return {
      best: scored[0]?.entry || null,
      validations: scored.map(s => ({
        entryId: s.entry.id,
        validation: s.validation,
        score: s.score
      }))
    };
  }

  /**
   * Batch validate cache entries with time efficiency
   */
  async batchValidate(cachedEntries, currentContext) {
    const startTime = Date.now();
    const results = [];

    for (const entry of cachedEntries) {
      if (Date.now() - startTime > 5000) {
        // Timeout after 5 seconds for large batches
        break;
      }

      const validation = await this.validate(entry, currentContext);
      results.push({
        entryId: entry.id,
        validation,
        recommendations: this._makeRecommendation(validation)
      });
    }

    return {
      processedCount: results.length,
      totalCount: cachedEntries.length,
      results
    };
  }

  // Private methods

  /**
   * Validate cache entry structure and required fields
   */
  _validateIntegrity(entry) {
    const issues = [];
    const required = ['id', 'prompt', 'output', 'metadata'];

    for (const field of required) {
      if (!entry[field]) {
        issues.push(`Missing required field: ${field}`);
      }
    }

    if (entry.metadata) {
      if (!entry.metadata.timestamp) {
        issues.push('Missing timestamp in metadata');
      }
      if (!entry.metadata.ttl) {
        issues.push('Missing TTL in metadata');
      }
    }

    return {
      valid: issues.length === 0,
      issues
    };
  }

  /**
   * Score relevance between cached and current prompts
   */
  _scoreRelevance(cachedPrompt, currentPrompt) {
    if (!cachedPrompt || !currentPrompt) return 0;

    // Exact match
    if (cachedPrompt === currentPrompt) return 100;

    // Normalize and tokenize
    const normalize = (text) => {
      return text
        .toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 2);
    };

    const cached = normalize(cachedPrompt);
    const current = normalize(currentPrompt);

    if (cached.length === 0 || current.length === 0) return 0;

    // Calculate token overlap
    const cachedSet = new Set(cached);
    const overlap = current.filter(token => cachedSet.has(token)).length;

    // Jaccard similarity
    const union = new Set([...cached, ...current]).size;
    return Math.round((overlap / (union || 1)) * 100);
  }

  /**
   * Check for parameter conflicts between cached and current context
   */
  _checkParameterConflicts(cachedParams, currentParams) {
    const conflicts = [];
    const criticalParams = ['userId', 'projectId', 'domain', 'version', 'environment'];

    for (const param of criticalParams) {
      const cached = cachedParams[param];
      const current = currentParams[param];

      if (cached && current && cached !== current) {
        conflicts.push(`${param}: ${cached} ≠ ${current}`);
      }
    }

    return conflicts;
  }

  /**
   * Validate output format and structure
   */
  _validateOutputFormat(output) {
    try {
      // Try to parse if string
      if (typeof output === 'string') {
        try {
          JSON.parse(output);
        } catch (e) {
          // Valid string output even if not JSON
        }
      } else if (typeof output === 'object') {
        // Valid object
      } else {
        return { valid: false, reason: 'Invalid output type' };
      }

      return { valid: true };
    } catch (error) {
      return { valid: false, reason: error.message };
    }
  }

  /**
   * Make recommendation based on validation results
   */
  _makeRecommendation(validation) {
    if (!validation.isValid) {
      return 'discard';
    }

    if (validation.confidence >= 80) {
      return 'use';
    } else if (validation.confidence >= 50) {
      return 'update';
    } else {
      return 'discard';
    }
  }

  /**
   * Calculate overall score for ranking
   */
  _calculateScore(validation) {
    if (!validation.isValid) return 0;

    const scores = {
      relevance: Math.max(0, validation.relevanceScore) * 0.5,
      confidence: validation.confidence * 0.3,
      freshness: Math.max(0, 100 - (validation.isStale ? 100 : 0)) * 0.2
    };

    return scores.relevance + scores.confidence + scores.freshness;
  }
}

// Export agent
module.exports = {
  name: 'cache-validator',
  version: '1.0.0',
  description: 'Validates cache entries and scores relevance',

  create: (options) => new CacheValidator(options),

  /**
   * Main agent entry point for Cowork integration
   */
  async execute(input) {
    const validator = new CacheValidator(input.options || {});

    if (Array.isArray(input.cachedEntries)) {
      return {
        status: 'completed',
        result: await validator.validateMultiple(
          input.cachedEntries,
          input.currentContext
        )
      };
    } else {
      return {
        status: 'completed',
        result: await validator.validate(
          input.cachedEntry,
          input.currentContext
        )
      };
    }
  },

  // Export class for testing
  CacheValidator
};
