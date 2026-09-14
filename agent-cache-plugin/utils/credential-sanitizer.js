/**
 * Credential Sanitizer
 *
 * Regex-based credential detection and redaction.
 * Detects API keys, tokens, secrets, passwords, and other credentials
 * by field name patterns, replacing values with '[REDACTED]' string.
 *
 * Patterns are compiled once at module load (efficiency optimization).
 */

// Regex pattern to detect credential field names (underscore/hyphen-aware boundaries)
// Matches credential keywords at word boundaries separated by underscores or hyphens
// Handles: api_key, api-key, apikey, token, secret, password, credential/credentials, auth, authorization, key, passwd, pwd
// Pattern: (start or - or _) + keyword + (end or - or _)
const CREDENTIAL_PATTERN = /(?:^|[-_])(api[-_]?key|apikey|passwd|pwd|token|secret|password|credentials?|auth|authorization|key)(?:[-_]|$)/i;

// Pattern to exclude non-credential fields (e.g., api_version, auth_method, key_size)
// Matches fields ending with common non-credential qualifiers
const NON_CREDENTIAL_PATTERN = /(version|method|size|type|answer|policy|rotation_days|docs_url|number|count)$/i;

/**
 * Sanitize parameters by redacting credential field values
 *
 * @param {object} parameters - Object with arbitrary key-value pairs
 * @returns {object} Same object structure with credential values replaced by '[REDACTED]'
 *
 * @example
 * sanitizeParameters({ apiKey: 'secret123', taskType: 'research' })
 * // => { apiKey: '[REDACTED]', taskType: 'research' }
 */
function sanitizeParameters(parameters) {
  if (!parameters) return {};

  const sanitized = { ...parameters };

  Object.keys(sanitized).forEach(key => {
    // Redact if matches credential pattern AND doesn't end with non-credential qualifier
    if (CREDENTIAL_PATTERN.test(key) && !NON_CREDENTIAL_PATTERN.test(key)) {
      sanitized[key] = '[REDACTED]';
    }
  });

  return sanitized;
}

module.exports = {
  sanitizeParameters,
  // Export patterns for testing/documentation purposes
  CREDENTIAL_PATTERN,
  NON_CREDENTIAL_PATTERN
};
