/**
 * Cache Sharing Manager
 *
 * Enables safe cross-project cache sharing with:
 * - Fine-grained access control (private, project, tenant, public)
 * - Organization and tenant isolation
 * - Sensitive data protection
 * - Comprehensive audit logging
 * - Sharing policies and rate limiting
 */

class CacheSharing {
  constructor(config = {}, auditLogger = null) {
    this.config = {
      enableSharing: config.enableSharing !== false,
      defaultAccessPolicy: config.defaultAccessPolicy || 'private',
      allowPublicSharing: config.allowPublicSharing || false,
      requireApprovalForSharing: config.requireApprovalForSharing || false,
      maxSharedEntriesPerUser: config.maxSharedEntriesPerUser || 10000,
      autoDegradeIfSensitive: config.autoDegradeIfSensitive !== false,
      restrictedTags: config.restrictedTags || ['confidential', 'internal-only'],
      allowCrossOrgSharing: config.allowCrossOrgSharing || false,
      shareAccessRateLimit: config.shareAccessRateLimit || 1000, // per user per hour
      sensitiveDataPatterns: config.sensitiveDataPatterns || []
    };

    this.auditLogger = auditLogger;
    this.accessLog = new Map(); // userId -> { timestamp, count }
    this.sharedEntriesIndex = new Map(); // userId -> Set of shared entryIds
  }

  /**
   * Enable sharing on an existing entry
   */
  async enableSharing(entry, policy = {}) {
    if (!this.config.enableSharing) {
      return { success: false, error: 'Sharing is disabled' };
    }

    const accessPolicy = policy.accessPolicy || this.config.defaultAccessPolicy;

    // Validate access policy
    if (!this._isValidAccessPolicy(accessPolicy)) {
      return { success: false, error: `Invalid access policy: ${accessPolicy}` };
    }

    // Check if public sharing is allowed
    if (accessPolicy === 'public' && !this.config.allowPublicSharing) {
      return { success: false, error: 'Public sharing is disabled by organization' };
    }

    // Check if entry has restricted tags
    const tags = entry.metadata?.tags || [];
    const hasRestrictedTags = tags.some(t => this.config.restrictedTags.includes(t));
    if (hasRestrictedTags && accessPolicy !== 'private') {
      return {
        success: false,
        error: 'Entry has restricted tags and cannot be shared',
        suggestedPolicy: 'private'
      };
    }

    // Initialize sharing metadata
    const sharing = {
      enabled: true,
      accessPolicy,
      createdBy: policy.createdBy,
      projectId: policy.projectId,
      tenantId: policy.tenantId,
      sharedAt: Date.now(),
      allowedUsers: policy.allowedUsers || [],
      deniedUsers: policy.deniedUsers || [],
      shareCount: 0,
      lastAccessedBy: null,
      lastAccessedAt: null
    };

    // Add to audit log
    if (this.auditLogger) {
      this.auditLogger.logOperation({
        type: 'share_enabled',
        entryId: entry.id,
        success: true,
        userId: policy.createdBy,
        parameters: {
          accessPolicy,
          projectId: policy.projectId,
          tenantId: policy.tenantId
        }
      });
    }

    // Track in user's shared entries
    if (!this.sharedEntriesIndex.has(policy.createdBy)) {
      this.sharedEntriesIndex.set(policy.createdBy, new Set());
    }
    this.sharedEntriesIndex.get(policy.createdBy).add(entry.id);

    return { success: true, sharing };
  }

  /**
   * Disable sharing on an entry
   */
  async disableSharing(entryId, userId) {
    if (this.sharedEntriesIndex.has(userId)) {
      this.sharedEntriesIndex.get(userId).delete(entryId);
    }

    if (this.auditLogger) {
      this.auditLogger.logOperation({
        type: 'share_disabled',
        entryId,
        success: true,
        userId
      });
    }

    return { success: true };
  }

  /**
   * Validate if user can access a shared entry
   */
  async validateAccess(entry, user) {
    if (!entry.sharing || !entry.sharing.enabled) {
      return { allowed: false, reason: 'Entry sharing not enabled' };
    }

    const sharing = entry.sharing;
    const policy = sharing.accessPolicy;
    const deniedUsers = sharing.deniedUsers || [];
    const allowedUsers = sharing.allowedUsers || [];

    // Check if user is in denied list
    if (deniedUsers.includes(user.id)) {
      this._logAccessDenial(entry.id, user.id, 'User in denied list');
      return { allowed: false, reason: 'Access denied' };
    }

    // Public access always allowed
    if (policy === 'public') {
      return { allowed: true };
    }

    // Owner always has access
    if (user.id === sharing.createdBy) {
      return { allowed: true };
    }

    // Tenant access - same organization
    if (policy === 'tenant') {
      if (user.tenantId && user.tenantId === sharing.tenantId) {
        // Check explicit allow list if set
        if (allowedUsers.length > 0 && !allowedUsers.includes(user.id)) {
          this._logAccessDenial(entry.id, user.id, 'Not in allowed list');
          return { allowed: false, reason: 'Access denied' };
        }
        return { allowed: true };
      }
      this._logAccessDenial(entry.id, user.id, 'Different tenant');
      return { allowed: false, reason: 'Different organization' };
    }

    // Project access
    if (policy === 'project') {
      if (user.projects && user.projects.includes(sharing.projectId)) {
        // Check explicit allow list if set
        if (allowedUsers.length > 0 && !allowedUsers.includes(user.id)) {
          this._logAccessDenial(entry.id, user.id, 'Not in allowed list');
          return { allowed: false, reason: 'Access denied' };
        }
        return { allowed: true };
      }
      this._logAccessDenial(entry.id, user.id, 'Not project member');
      return { allowed: false, reason: 'Not a project member' };
    }

    // Owner access only
    if (policy === 'owner') {
      this._logAccessDenial(entry.id, user.id, 'Entry is private');
      return { allowed: false, reason: 'Entry is private' };
    }

    return { allowed: false, reason: 'Unknown policy' };
  }

  /**
   * Record shared entry access
   */
  async recordAccess(entry, user) {
    if (!entry.sharing || !entry.sharing.enabled) {
      return { allowed: true };
    }

    // Check rate limiting
    const limited = this._checkRateLimit(user.id);
    if (limited) {
      this._logAccessDenial(entry.id, user.id, 'Rate limited');
      return { allowed: false, reason: 'Rate limit exceeded' };
    }

    // Update share count
    if (entry.sharing) {
      entry.sharing.shareCount = (entry.sharing.shareCount || 0) + 1;
      entry.sharing.lastAccessedBy = user.id;
      entry.sharing.lastAccessedAt = Date.now();
    }

    // Log access
    if (this.auditLogger) {
      this.auditLogger.logOperation({
        type: 'shared_entry_accessed',
        entryId: entry.id,
        success: true,
        userId: user.id,
        parameters: {
          accessPolicy: entry.sharing.accessPolicy,
          projectId: entry.sharing.projectId,
          sharedBy: entry.sharing.createdBy
        }
      });
    }

    return { allowed: true };
  }

  /**
   * Filter entries for shared access (for search results)
   */
  async filterForUser(entries, user) {
    const filtered = [];

    for (const entry of entries) {
      // Include non-shared entries (user owns them)
      if (!entry.sharing || !entry.sharing.enabled) {
        continue;
      }

      // Check if user can access
      const access = await this.validateAccess(entry, user);
      if (access.allowed) {
        await this.recordAccess(entry, user);
        filtered.push(entry);
      }
    }

    return filtered;
  }

  /**
   * Get entries shared by a user
   */
  async getSharedByUser(userId) {
    if (!this.sharedEntriesIndex.has(userId)) {
      return [];
    }
    return Array.from(this.sharedEntriesIndex.get(userId));
  }

  /**
   * Get sharing statistics
   */
  getSharingStats() {
    const stats = {
      totalSharedEntries: 0,
      totalAccessesByPolicy: {
        owner: 0,
        project: 0,
        tenant: 0,
        public: 0
      },
      usersWithSharedEntries: this.sharedEntriesIndex.size,
      averageSharesPerEntry: 0
    };

    for (const entryIds of this.sharedEntriesIndex.values()) {
      stats.totalSharedEntries += entryIds.size;
    }

    return stats;
  }

  /**
   * Get access list for an entry
   */
  async getAccessList(entry) {
    if (!entry.sharing || !entry.sharing.enabled) {
      return { sharedWith: [], policy: 'private' };
    }

    const sharing = entry.sharing;
    return {
      policy: sharing.accessPolicy,
      sharedBy: sharing.createdBy,
      sharedAt: sharing.sharedAt,
      allowedUsers: sharing.allowedUsers,
      deniedUsers: sharing.deniedUsers,
      shareCount: sharing.shareCount,
      lastAccessedBy: sharing.lastAccessedBy,
      lastAccessedAt: sharing.lastAccessedAt
    };
  }

  /**
   * Update access list for an entry
   */
  async updateAccessList(entry, userId, updates) {
    if (!entry.sharing || !entry.sharing.enabled) {
      return { success: false, error: 'Entry not shared' };
    }

    if (entry.sharing.createdBy !== userId) {
      return { success: false, error: 'Only entry owner can update access' };
    }

    if (updates.allowedUsers) {
      entry.sharing.allowedUsers = updates.allowedUsers;
    }
    if (updates.deniedUsers) {
      entry.sharing.deniedUsers = updates.deniedUsers;
    }

    if (this.auditLogger) {
      this.auditLogger.logOperation({
        type: 'access_list_updated',
        entryId: entry.id,
        success: true,
        userId,
        parameters: updates
      });
    }

    return { success: true, sharing: entry.sharing };
  }

  // Private methods

  /**
   * Check if access policy is valid
   */
  _isValidAccessPolicy(policy) {
    return ['owner', 'project', 'tenant', 'public'].includes(policy);
  }

  /**
   * Check rate limit for shared entry access
   */
  _checkRateLimit(userId) {
    const now = Date.now();
    const hourAgo = now - 60 * 60 * 1000;

    if (!this.accessLog.has(userId)) {
      this.accessLog.set(userId, []);
    }

    const accesses = this.accessLog.get(userId);
    const recentAccesses = accesses.filter(t => t > hourAgo);

    // Check if limit exceeded (before adding this access)
    if (recentAccesses.length >= this.config.shareAccessRateLimit) {
      return true; // Rate limited
    }

    // Add current access and update log
    recentAccesses.push(now);
    this.accessLog.set(userId, recentAccesses);

    return false;
  }

  /**
   * Log access denial
   */
  _logAccessDenial(entryId, userId, reason) {
    if (this.auditLogger) {
      this.auditLogger.logOperation({
        type: 'shared_access_denied',
        entryId,
        success: false,
        userId,
        error: reason
      });
    }
  }
}

module.exports = CacheSharing;
