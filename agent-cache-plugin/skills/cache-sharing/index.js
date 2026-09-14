/**
 * Cache Sharing Skill
 *
 * Cross-project and cross-user cache sharing with fine-grained access control.
 * Enables safe, secure sharing of cache entries across organization while maintaining
 * privacy and access boundaries.
 *
 * Supports:
 * - Access policies: owner, project, tenant, public
 * - User allow/deny lists
 * - Rate limiting for shared access
 * - Sensitive data protection
 * - Comprehensive audit logging
 */

module.exports = require('./CacheSharing');
