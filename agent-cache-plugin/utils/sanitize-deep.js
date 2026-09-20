'use strict';
/**
 * sanitize-deep.js
 *
 * Recursively applies credential-sanitizer.sanitizeParameters() to every
 * object node in an arbitrary JS value (handles arrays, nested objects,
 * primitives, null).
 */

const { sanitizeParameters } = require('./credential-sanitizer');

/**
 * @param {*} value
 * @returns {*} Deep-sanitized copy
 */
function sanitizeDeep(value) {
  if (value === null || typeof value !== 'object') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(sanitizeDeep);
  }
  // Flat-sanitize this object level
  const sanitized = sanitizeParameters(value);
  // Recurse into object values
  for (const k of Object.keys(sanitized)) {
    if (sanitized[k] !== null && typeof sanitized[k] === 'object') {
      sanitized[k] = sanitizeDeep(sanitized[k]);
    }
  }
  return sanitized;
}

module.exports = { sanitizeDeep };
