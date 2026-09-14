---
description: Intelligent cache decision-making with relevance scoring and staleness detection
keywords: [orchestration, decision-making, relevance, staleness, conflict-detection]
version: 1.0.0
---

# Skill: Cache Orchestration

## Overview

Cache Orchestration is an internal helper skill that decides whether to use a cached result or perform fresh reasoning. It scores cached entries for relevance to the current task, enforces staleness thresholds, and detects parameter conflicts.

## What It Does

- **Evaluates cache hits** based on task similarity (using Jaccard similarity scoring)
- **Enforces relevance thresholds** (default 75%) to ensure cached results are sufficiently similar
- **Checks staleness** (default 24 hours) to avoid using outdated cached results
- **Detects conflicts** in critical parameters (userId, projectId, domain) that invalidate cache reuse
- **Records metrics** for both cache hits and misses to track effectiveness

## Key Features

### Relevance Scoring
Scores two prompts on a scale of 0–100 using word-based similarity. Word order and exact phrasing don't matter; only the overlap of significant words counts. Identical prompts score ~100, similar prompts score 50–90, and dissimilar prompts score <50.

### Staleness Checking
Marks cache entries as stale if they exceed the configured threshold (default 24 hours). Stale entries are discarded even if relevant, ensuring freshness.

### Conflict Detection
Checks for mismatches in critical parameters (userId, projectId, domain) between the cached entry and current request. Mismatches indicate the cache result would be incorrect for the new context and cause the cache to be bypassed.

### Decision Output
Returns one of three decisions:
- **use_cache**: Cache hit with sufficient relevance; cached output will be returned
- **fresh_reasoning**: No suitable cache found; a new answer is needed
- **update**: Entry is acceptable but may be outdated; fresh reasoning recommended

## Usage Example

```javascript
const { CacheOrchestration } = require('./skills/cache-orchestration');

const orchestration = new CacheOrchestration({
  relevanceThreshold: 80,  // Higher = stricter matching
  stalenessThreshold: 48 * 60 * 60 * 1000  // 48 hours
});

const decision = await orchestration.makeDecision({
  agentType: 'agent-tdd',
  prompt: 'Create unit tests for this function',
  parameters: { taskType: 'test', userId: 'user-123' }
});

console.log(decision.decision);  // 'use_cache' | 'fresh_reasoning' | 'update'
console.log(decision.relevanceScore);  // 0–100
console.log(decision.tokenSavings);  // Estimated tokens saved if using cache
```

## Configuration

- **relevanceThreshold** (default: 75): Minimum similarity score (0–100) to use cache
- **stalenessThreshold** (default: 24h): Maximum age in milliseconds for cache entries

Higher relevance thresholds reduce false positives but increase cache misses. Longer staleness thresholds increase cache hits but may surface outdated results.

## Integration

This skill is used internally by:
- **pre-agent-spawn hook**: Determines cache usage before starting an agent
- **cache-validation skill**: Validates cache hits after retrieval
- **metrics tracking**: Provides hit/miss data for cache analytics

Not typically called directly by user code.

## Performance Notes

- Relevance scoring uses word-set intersection and runs in O(n+m) time (n, m = unique words in prompts)
- Cache search is delegated to Cache Management skill and respects its performance characteristics
- Metrics recording is asynchronous and does not block decision-making

## Best Practices

1. **Adjust thresholds per use case**: 75% works for general tasks; increase to 85–90% for safety-critical decisions
2. **Monitor metrics**: Track hit rates and token savings to fine-tune thresholds
3. **Validate conflicts**: Ensure critical parameters are correctly set; conflicts cause unnecessary misses
4. **Consider time sensitivity**: For tasks where freshness matters (current events, real-time data), lower staleness thresholds
