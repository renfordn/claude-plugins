/**
 * Scoring Utilities
 *
 * Centralized relevance scoring and similarity calculations.
 * Used by cache-orchestration, cache-validation, and related skills.
 */

const DEFAULTS = {
  MIN_WORD_LENGTH: 2,
  MIN_WORD_LENGTH_STRICT: 3
};

/**
 * Score relevance between two prompts using Jaccard similarity.
 * Algorithm: Word-based similarity (order-independent, short words filtered).
 * Result: 0-100 score where 100 = identical, 0 = completely different.
 *
 * Uses strict filtering (words > 3 chars) for better discrimination.
 * Handles null/undefined gracefully; returns 0 for empty inputs.
 *
 * Examples:
 * - scoreRelevance("test", "test") = 100
 * - scoreRelevance("test prompt", "test") = ~67
 * - scoreRelevance("test", "gardening") = 0
 *
 * @param {string} text1 - First prompt/text
 * @param {string} text2 - Second prompt/text
 * @param {Object} options - Configuration: { minWordLength: 3 }
 * @returns {number} Relevance score 0-100
 */
function scoreRelevance(text1, text2, options = {}) {
  if (!text1 || !text2) return 0;

  // Exact match
  if (text1 === text2) return 100;

  const minWordLength = options.minWordLength || DEFAULTS.MIN_WORD_LENGTH_STRICT;

  // Normalize and tokenize
  const normalize = (text) => {
    return text
      .toLowerCase()
      .split(/\s+/)
      .filter(word => word.length > minWordLength)
      .sort();
  };

  const words1 = normalize(text1);
  const words2 = normalize(text2);

  if (words1.length === 0 || words2.length === 0) return 0;

  // Calculate Jaccard similarity: |intersection| / |union|
  const set1 = new Set(words1);
  const set2 = new Set(words2);

  const intersection = [...set1].filter(w => set2.has(w)).length;
  const union = new Set([...set1, ...set2]).size;

  return Math.round((intersection / (union || 1)) * 100);
}

/**
 * Score relevance with less strict filtering (words > 2 chars).
 * Used by cache-validator for more lenient matching.
 *
 * @param {string} text1 - First prompt/text
 * @param {string} text2 - Second prompt/text
 * @returns {number} Relevance score 0-100
 */
function scoreRelevancePermissive(text1, text2) {
  return scoreRelevance(text1, text2, { minWordLength: DEFAULTS.MIN_WORD_LENGTH });
}

/**
 * Calculate similarity score with additional weighting.
 * Accounts for length ratio and word overlap percentage.
 *
 * Useful for ranking multiple candidates where Jaccard alone is insufficient.
 *
 * @param {string} cached - Cached text
 * @param {string} current - Current text
 * @returns {number} Weighted similarity score 0-100
 */
function scoreRelevanceWeighted(cached, current) {
  if (!cached || !current) return 0;

  const baseScore = scoreRelevance(cached, current);

  // Normalize and get word lists for additional weighting
  const normalize = (text) => {
    return text
      .toLowerCase()
      .split(/\s+/)
      .filter(word => word.length > DEFAULTS.MIN_WORD_LENGTH_STRICT);
  };

  const words1 = normalize(cached);
  const words2 = normalize(current);

  if (words1.length === 0 || words2.length === 0) return baseScore;

  // Prefer similar lengths (penalties for large length differences)
  const lengthRatio = Math.min(words1.length, words2.length) / Math.max(words1.length, words2.length);
  const lengthPenalty = Math.max(0, 1 - Math.abs(words1.length - words2.length) / Math.max(words1.length, words2.length));

  // Weighted combination: 70% jaccard, 30% length similarity
  const weightedScore = baseScore * 0.7 + (lengthPenalty * 100) * 0.3;

  return Math.round(weightedScore);
}

/**
 * Compare parameter values and detect conflicts.
 * Returns true if any critical parameters differ.
 *
 * @param {Object} cachedParams - Cached entry parameters
 * @param {Object} currentParams - Current context parameters
 * @param {Array<string>} criticalParams - Parameter names to check
 * @returns {boolean} True if conflicts detected
 */
function hasParameterConflicts(cachedParams, currentParams, criticalParams = []) {
  const params = criticalParams.length > 0 ? criticalParams : ['userId', 'projectId', 'domain'];

  for (const param of params) {
    if (cachedParams[param] && currentParams[param]) {
      if (cachedParams[param] !== currentParams[param]) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Detailed parameter conflict detection.
 * Returns array of specific conflicts found.
 *
 * @param {Object} cachedParams - Cached entry parameters
 * @param {Object} currentParams - Current context parameters
 * @param {Array<string>} criticalParams - Parameter names to check
 * @returns {Array<Object>} Array of {parameter, cached, current} conflicts
 */
function findParameterConflicts(cachedParams, currentParams, criticalParams = []) {
  const conflicts = [];
  const params = criticalParams.length > 0 ? criticalParams : ['userId', 'projectId', 'domain'];

  for (const param of params) {
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

/**
 * Normalize text for comparison.
 * Useful for preprocessing text before scoring.
 *
 * @param {string} text - Text to normalize
 * @param {Object} options - { lowercase: true, removeSpecial: false, trim: true }
 * @returns {string} Normalized text
 */
function normalizeText(text, options = {}) {
  let result = text;

  if (options.lowercase !== false) {
    result = result.toLowerCase();
  }

  if (options.removeSpecial) {
    result = result.replace(/[^\w\s]/g, ' ');
  }

  if (options.trim !== false) {
    result = result.trim();
  }

  return result;
}

module.exports = {
  scoreRelevance,
  scoreRelevancePermissive,
  scoreRelevanceWeighted,
  hasParameterConflicts,
  findParameterConflicts,
  normalizeText,

  // Exports constants for tests
  DEFAULTS
};
