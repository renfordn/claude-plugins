---
description: Five-layer validation model for cache quality assurance with relevance scoring
keywords: [validation, integrity, recency, relevance, confidence]
version: 1.0.0
---

# Skill: Cache Validation

## Overview

Cache Validation is an internal helper skill that evaluates whether a cached entry is safe and relevant for reuse. It performs five integrity checks, scores relevance, and provides explicit recommendations (use, update, or discard) with confidence levels.

## What It Does

- **Integrity checking**: Verifies required fields (id, prompt, output, metadata, timestamp, TTL) are present
- **Staleness detection**: Marks entries beyond the age limit (default 7 days) as unusable
- **Relevance scoring**: Compares cached entry prompt to current task using word-based similarity
- **Conflict detection**: Identifies mismatches in critical parameters (userId, projectId, domain, version, environment)
- **Output validation**: Ensures output format is JSON-compatible or valid string/object
- **Confidence scoring**: Combines all checks into a 0–100 confidence score and recommendation

## Key Features

### Five-Layer Validation

1. **Integrity** (-30 confidence if failed): All required fields present and non-empty
2. **Staleness** (-50 confidence if failed): Entry age does not exceed configured maximum (default 7 days)
3. **Relevance** (-40 confidence if failed): Relevance score meets minimum threshold (default 70%)
4. **Conflicts** (-60 confidence if failed): No mismatches in critical parameters
5. **Format** (-20 confidence if failed): Output is valid JSON, string, or object

### Relevance Scoring
Scores cached entry prompt vs current task (0–100) using word-based Jaccard similarity. Exact matches score 100, completely different prompts score 0. Short words (<2 chars) are ignored.

### Recommendations
- **use**: Confidence ≥80 (high trust; cache is fresh, relevant, and conflict-free)
- **update**: Confidence 50–79 (medium trust; usable but may be slightly stale or marginally relevant)
- **discard**: Confidence <50 or isValid=false (low trust; reject cache and compute fresh)

### Ranking Multiple Entries
When validating multiple entries, ranks by composite score:
- Relevance: 50% weight
- Confidence: 30% weight
- Freshness: 20% weight

Returns best match (highest score) with full validation details for each entry.

## Usage Example

```javascript
const { CacheValidator } = require('./skills/cache-validation');

const validator = new CacheValidator({
  minRelevanceScore: 75,   // Higher = stricter matching
  maxEntryAge: 14 * 24 * 60 * 60 * 1000  // 14 days
});

const result = await validator.validate(cachedEntry, {
  task: 'My current prompt',
  parameters: { userId: 'user-123', projectId: 'proj-456' }
});

console.log(result.recommendation);  // 'use' | 'update' | 'discard'
console.log(result.confidence);      // 0–100
console.log(result.issues);          // Array of detected problems
```

## Configuration

- **minRelevanceScore** (default: 70): Minimum word-overlap percentage (0–100) to accept cache entry
- **maxEntryAge** (default: 7 days): Maximum age in milliseconds; older entries marked stale

Stricter settings (higher relevance, shorter age) reduce false positives but increase cache misses.

## Batch Validation

For validating many entries, `batchValidate()` processes entries with a 5-second timeout to prevent hangs on large batches.

```javascript
const result = await validator.batchValidate(cachedEntries, context);
// result.processedCount: actual entries validated before timeout
// result.totalCount: total entries provided
// result.results: array of validation results
```

## Integration

Used by:
- **Cache Orchestration**: Ranks cache candidates before decision
- **Hooks**: Final validation before returning cached output
- **Cache Management**: Audit and validation workflows

## Performance Notes

- Relevance scoring: O(n+m) where n, m = unique words in prompts
- Batch processing: ~100–200 entries per second; limited to 5 seconds
- Multiple entry validation: Parallelized via Promise.all()

## Best Practices

1. **Tune thresholds per use case**: 70% works for general tasks; increase to 80–85% for safety-critical or time-sensitive work
2. **Monitor recommendations**: Track ratio of use/update/discard to fine-tune settings
3. **Validate conflicts**: Ensure critical parameters are correctly identified; add custom parameters if needed
4. **Check confidence scores**: Low confidence (0–50) often indicates need for fresh reasoning
5. **Use batch validation for audits**: Validate large entry sets without blocking; check processedCount vs totalCount for timeout detection

## Error Handling

If validation fails (e.g., null entry or malformed context), returns:
- `isValid: false`
- `confidence: 0`
- `recommendation: 'discard'`
- `issues: [error message]`

Never throws; always returns a valid result object.
