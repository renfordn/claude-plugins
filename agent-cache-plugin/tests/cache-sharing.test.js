/**
 * Test Suite: Cache Sharing
 *
 * Tests for cross-project cache sharing with access control
 */

const CacheSharing = require('../skills/cache-sharing/CacheSharing');

describe('CacheSharing', () => {
  let sharing;
  let auditLogger;

  beforeEach(() => {
    // Mock audit logger
    auditLogger = {
      logOperation: jest.fn()
    };

    sharing = new CacheSharing({
      enableSharing: true,
      defaultAccessPolicy: 'private',
      allowPublicSharing: true,
      autoDegradeIfSensitive: false,
      restrictedTags: ['confidential']
    }, auditLogger);
  });

  describe('Configuration', () => {
    test('should initialize with default config', () => {
      const s = new CacheSharing();
      expect(s.config.enableSharing).toBe(true);
      expect(s.config.defaultAccessPolicy).toBe('private');
      expect(s.config.allowPublicSharing).toBe(false);
    });

    test('should accept custom configuration', () => {
      const s = new CacheSharing({
        enableSharing: false,
        defaultAccessPolicy: 'tenant',
        allowPublicSharing: true
      });
      expect(s.config.enableSharing).toBe(false);
      expect(s.config.defaultAccessPolicy).toBe('tenant');
      expect(s.config.allowPublicSharing).toBe(true);
    });

    test('should disable sharing when disabled in config', async () => {
      const s = new CacheSharing({ enableSharing: false });
      const entry = { id: 'entry-1', prompt: 'test' };

      const result = await s.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('disabled');
    });
  });

  describe('Enable Sharing', () => {
    test('should enable sharing with valid policy', async () => {
      const entry = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };

      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        projectId: 'proj-1',
        tenantId: 'tenant-1'
      });

      expect(result.success).toBe(true);
      expect(result.sharing.enabled).toBe(true);
      expect(result.sharing.accessPolicy).toBe('tenant');
      expect(result.sharing.createdBy).toBe('user-1');
    });

    test('should reject invalid access policy', async () => {
      const entry = { id: 'entry-1', prompt: 'test' };

      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'invalid',
        createdBy: 'user-1'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid access policy');
    });

    test('should reject public sharing when disabled', async () => {
      const s = new CacheSharing({ allowPublicSharing: false });
      const entry = { id: 'entry-1', prompt: 'test' };

      const result = await s.enableSharing(entry, {
        accessPolicy: 'public',
        createdBy: 'user-1'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Public sharing is disabled');
    });

    test('should prevent sharing entries with restricted tags', async () => {
      const s = new CacheSharing({
        restrictedTags: ['confidential'],
        autoDegradeIfSensitive: false
      });
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: ['confidential'] }
      };

      const result = await s.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('restricted tags');
    });

    test('should track shared entries per user', async () => {
      const entry = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };

      await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });

      const shared = await sharing.getSharedByUser('user-1');
      expect(shared).toContain('entry-1');
    });

    test('should log sharing in audit logger', async () => {
      const entry = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };

      await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });

      expect(auditLogger.logOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'share_enabled',
          entryId: 'entry-1',
          userId: 'user-1'
        })
      );
    });
  });

  describe('Access Validation', () => {
    let entry;

    beforeEach(async () => {
      entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        projectId: 'proj-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = result.sharing;
    });

    test('should deny access to non-shared entries', async () => {
      const unsharedEntry = { id: 'entry-2', prompt: 'test' };
      const user = { id: 'user-2', tenantId: 'tenant-1' };

      const result = await sharing.validateAccess(unsharedEntry, user);
      expect(result.allowed).toBe(false);
    });

    test('should allow owner access regardless of policy', async () => {
      const user = { id: 'user-1', tenantId: 'tenant-1' };

      const result = await sharing.validateAccess(entry, user);
      expect(result.allowed).toBe(true);
    });

    test('should allow tenant access for same organization', async () => {
      const user = { id: 'user-2', tenantId: 'tenant-1' };

      const result = await sharing.validateAccess(entry, user);
      expect(result.allowed).toBe(true);
    });

    test('should deny tenant access for different organization', async () => {
      const user = { id: 'user-2', tenantId: 'tenant-2' };

      const result = await sharing.validateAccess(entry, user);
      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('organization');
    });

    test('should allow project access for project members', async () => {
      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'project',
        createdBy: 'user-1',
        projectId: 'proj-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = result.sharing;

      const user = { id: 'user-2', tenantId: 'tenant-1', projects: ['proj-1'] };

      const validation = await sharing.validateAccess(entry, user);
      expect(validation.allowed).toBe(true);
    });

    test('should deny project access for non-members', async () => {
      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'project',
        createdBy: 'user-1',
        projectId: 'proj-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = result.sharing;

      const user = { id: 'user-2', tenantId: 'tenant-1', projects: ['proj-2'] };

      const validation = await sharing.validateAccess(entry, user);
      expect(validation.allowed).toBe(false);
    });

    test('should allow public access for anyone', async () => {
      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'public',
        createdBy: 'user-1'
      });
      entry.sharing = result.sharing;

      const user = { id: 'user-999', tenantId: 'unknown-tenant' };

      const validation = await sharing.validateAccess(entry, user);
      expect(validation.allowed).toBe(true);
    });

    test('should respect allowed users list', async () => {
      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1',
        allowedUsers: ['user-2']
      });
      entry.sharing = result.sharing;

      const allowedUser = { id: 'user-2', tenantId: 'tenant-1' };
      const deniedUser = { id: 'user-3', tenantId: 'tenant-1' };

      const allowResult = await sharing.validateAccess(entry, allowedUser);
      const denyResult = await sharing.validateAccess(entry, deniedUser);

      expect(allowResult.allowed).toBe(true);
      expect(denyResult.allowed).toBe(false);
    });

    test('should respect denied users list', async () => {
      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1',
        deniedUsers: ['user-2']
      });
      entry.sharing = result.sharing;

      const deniedUser = { id: 'user-2', tenantId: 'tenant-1' };
      const allowedUser = { id: 'user-3', tenantId: 'tenant-1' };

      const denyResult = await sharing.validateAccess(entry, deniedUser);
      const allowResult = await sharing.validateAccess(entry, allowedUser);

      expect(denyResult.allowed).toBe(false);
      expect(allowResult.allowed).toBe(true);
    });
  });

  describe('Access Recording', () => {
    test('should record access on shared entry', async () => {
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await sharing.enableSharing(entry, {
        accessPolicy: 'public',
        createdBy: 'user-1'
      });
      entry.sharing = sharedResult.sharing;

      const user = { id: 'user-2' };
      await sharing.recordAccess(entry, user);

      expect(entry.sharing.shareCount).toBe(1);
      expect(entry.sharing.lastAccessedBy).toBe('user-2');
      expect(entry.sharing.lastAccessedAt).toBeDefined();
      expect(auditLogger.logOperation).toHaveBeenCalled();
    });

    test('should increment share count on multiple accesses', async () => {
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await sharing.enableSharing(entry, {
        accessPolicy: 'public',
        createdBy: 'user-1'
      });
      entry.sharing = sharedResult.sharing;

      const user1 = { id: 'user-2' };
      const user2 = { id: 'user-3' };

      await sharing.recordAccess(entry, user1);
      await sharing.recordAccess(entry, user2);

      expect(entry.sharing.shareCount).toBe(2);
    });

    test('should respect rate limiting', async () => {
      const s = new CacheSharing({
        shareAccessRateLimit: 2
      });

      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await s.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = sharedResult.sharing;

      const user = { id: 'user-2', tenantId: 'tenant-1' };

      await s.recordAccess(entry, user);
      await s.recordAccess(entry, user);

      // Third access should be rate limited
      const result = await s.recordAccess(entry, user);
      expect(result.allowed).toBe(false);
    });
  });

  describe('Disable Sharing', () => {
    test('should disable sharing on entry', async () => {
      const entry = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };

      await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });

      await sharing.disableSharing('entry-1', 'user-1');

      const shared = await sharing.getSharedByUser('user-1');
      expect(shared).not.toContain('entry-1');
    });

    test('should log sharing disable in audit logger', async () => {
      await sharing.disableSharing('entry-1', 'user-1');

      expect(auditLogger.logOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'share_disabled',
          entryId: 'entry-1',
          userId: 'user-1'
        })
      );
    });
  });

  describe('Access List Management', () => {
    test('should get access list for shared entry', async () => {
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        projectId: 'proj-1',
        tenantId: 'tenant-1',
        allowedUsers: ['user-2', 'user-3']
      });
      entry.sharing = sharedResult.sharing;

      const list = await sharing.getAccessList(entry);

      expect(list.policy).toBe('tenant');
      expect(list.sharedBy).toBe('user-1');
      expect(list.allowedUsers).toEqual(['user-2', 'user-3']);
    });

    test('should update access list', async () => {
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = sharedResult.sharing;

      await sharing.updateAccessList(entry, 'user-1', {
        allowedUsers: ['user-2', 'user-3']
      });

      expect(entry.sharing.allowedUsers).toEqual(['user-2', 'user-3']);
      expect(auditLogger.logOperation).toHaveBeenCalled();
    });

    test('should prevent non-owner from updating access list', async () => {
      const entry = {
        id: 'entry-1',
        prompt: 'test',
        metadata: { tags: [] }
      };

      const sharedResult = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });
      entry.sharing = sharedResult.sharing;

      const result = await sharing.updateAccessList(entry, 'user-2', {
        allowedUsers: ['user-3']
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('owner');
    });
  });

  describe('Sharing Statistics', () => {
    test('should return empty stats initially', () => {
      const stats = sharing.getSharingStats();
      expect(stats.totalSharedEntries).toBe(0);
      expect(stats.usersWithSharedEntries).toBe(0);
    });

    test('should track sharing statistics', async () => {
      const entry1 = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };
      const entry2 = { id: 'entry-2', prompt: 'test', metadata: { tags: [] } };

      await sharing.enableSharing(entry1, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });

      await sharing.enableSharing(entry2, {
        accessPolicy: 'public',
        createdBy: 'user-2'
      });

      const stats = sharing.getSharingStats();
      expect(stats.totalSharedEntries).toBe(2);
      expect(stats.usersWithSharedEntries).toBe(2);
    });
  });

  describe('Filter for User', () => {
    test('should filter entries based on user access', async () => {
      const entries = [
        {
          id: 'entry-1',
          prompt: 'test',
          metadata: { tags: [] },
          sharing: {
            enabled: true,
            accessPolicy: 'tenant',
            createdBy: 'user-1',
            tenantId: 'tenant-1',
            shareCount: 0
          }
        },
        {
          id: 'entry-2',
          prompt: 'test',
          metadata: { tags: [] },
          sharing: {
            enabled: true,
            accessPolicy: 'project',
            createdBy: 'user-1',
            projectId: 'proj-1',
            shareCount: 0
          }
        }
      ];

      const user = { id: 'user-2', tenantId: 'tenant-1', projects: [] };
      const filtered = await sharing.filterForUser(entries, user);

      // Only entry-1 should pass (tenant match)
      expect(filtered.length).toBe(1);
      expect(filtered[0].id).toBe('entry-1');
    });
  });

  describe('Edge Cases', () => {
    test('should handle entries with no metadata', async () => {
      const entry = { id: 'entry-1', prompt: 'test' };

      const result = await sharing.enableSharing(entry, {
        accessPolicy: 'tenant',
        createdBy: 'user-1',
        tenantId: 'tenant-1'
      });

      expect(result.success).toBe(true);
    });

    test('should handle multiple users sharing same entry', async () => {
      const entry = { id: 'entry-1', prompt: 'test', metadata: { tags: [] } };

      await sharing.enableSharing(entry, {
        accessPolicy: 'public',
        createdBy: 'user-1'
      });

      const shared1 = await sharing.getSharedByUser('user-1');
      const shared2 = await sharing.getSharedByUser('user-2');

      expect(shared1).toContain('entry-1');
      expect(shared2.length).toBe(0); // Only tracks sharing creator
    });
  });
});
