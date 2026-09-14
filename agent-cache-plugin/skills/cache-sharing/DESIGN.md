# Cross-Project Cache Sharing Design

## Overview

Enables safe cache sharing across multiple projects, teams, and users within an organization while maintaining privacy and access control boundaries.

## Key Concepts

### Sharing Levels

1. **Private** (default)
   - Entry only accessible to owner/project
   - No cross-project visibility
   - Ideal for sensitive or project-specific results

2. **Internal** 
   - Accessible to all users within same organization
   - Requires valid org membership
   - Suitable for general-purpose computations

3. **Public**
   - Accessible to anyone with cache access
   - No org boundary restrictions
   - Use for completely non-sensitive, widely-applicable results

### Access Control

- **EntryOwner**: User/agent who created the entry
- **ProjectId**: Project that owns the entry
- **TenantId**: Organization tenant
- **AccessPolicy**: Determines who can access entry
  - `owner`: Only creator
  - `project`: Project members
  - `tenant`: Organization members
  - `public`: Anyone

## Entry Structure

```javascript
{
  id: 'entry-id',
  prompt: '...',
  output: {...},
  metadata: {
    agentType: 'analyzer',
    taskType: 'document-analysis',
    tags: ['ml', 'ai'],
    ttl: 3600000,
    tokenCount: 250
  },
  sharing: {
    enabled: true,           // Is this entry shareable?
    accessPolicy: 'tenant',  // owner | project | tenant | public
    createdBy: 'user-123',   // User/agent who created
    projectId: 'proj-456',   // Owning project
    tenantId: 'tenant-789',  // Organization
    sharedAt: 1693065600000, // When sharing was enabled
    allowedUsers: [],        // Explicit whitelist (if needed)
    deniedUsers: []          // Explicit blacklist (if needed)
  }
}
```

## Access Validation

When retrieving a shared entry, validate:

1. **Entry exists and not expired**
2. **User is authenticated** (for non-public entries)
3. **Organization match** (for tenant/project entries)
4. **Project membership** (for project entries)
5. **Explicit allow/deny lists** (if configured)
6. **Audit logging** (track who accessed what)

## Sharing Policies

### Policy Configuration

```javascript
{
  enableSharing: true,
  defaultAccessPolicy: 'private',
  allowPublicSharing: false,      // Org-level control
  requireApprovalForSharing: false,
  maxSharedEntriesPerUser: 10000,
  sharingScopeRestrictions: {
    // Can only share within org
    allowCrossOrgSharing: false,
    // Can only share certain content types
    restrictedTags: ['confidential', 'internal-only'],
    // Auto-downgrade sharing level for sensitive data
    autoDegradeIfSensitive: true
  }
}
```

## Use Cases

### Case 1: ML Model Reuse
- Data scientist trains a model
- Shares training results with tenant (`accessPolicy: 'tenant'`)
- Other teams reuse results without recomputing
- Audit trail shows which teams accessed results

### Case 2: Code Analysis Cache
- Agent analyzes codebase from Project A
- Wants to share analysis patterns with Project B
- Uses `accessPolicy: 'project'` with allowedProjects list
- Only Project B members can access

### Case 3: Public Knowledge Base
- Organization publishes FAQ analysis
- Set `accessPolicy: 'public'`
- Internal and external users can access
- Used for public-facing services

### Case 4: Sensitive Data Isolation
- Entry contains sensitive customer data
- Explicitly set `accessPolicy: 'owner'`
- Not eligible for sharing regardless of config
- Marked in audit logs for compliance

## Implementation

### CacheSharing Class

Handles:
- Sharing policy enforcement
- Access control validation
- Cross-project entry lookups
- Shared entry statistics
- Access audit logging

### Methods

```javascript
// Enable sharing on entry
await cache.share(entryId, { accessPolicy: 'tenant' })

// Get shared entries (with access control)
await cache.getSharedEntries(criteria)

// Validate access before returning entry
await cache._validateAccess(entry, user, org)

// Get sharing statistics
await cache.getSharingStats()

// List who can access an entry
await cache.getAccessList(entryId)
```

### Integration Points

1. **CacheManager**: Add sharing parameter to store/retrieve
2. **StorageBackend**: Add sharing filter to search
3. **AuditLogger**: Log all shared entry accesses
4. **Redis**: Use key pattern for shared entry discovery

## Audit Logging Integration

Track:
- Who shared an entry and when
- Who accessed a shared entry
- Access denials and reasons
- Policy changes
- Sensitive data detection on shared entries

```javascript
logger.logSharing({
  type: 'share_enabled',
  entryId: 'entry-123',
  accessPolicy: 'tenant',
  userId: 'user-456',
  projectId: 'proj-789',
  tenantId: 'tenant-111'
});

logger.logSharedAccess({
  type: 'shared_entry_accessed',
  entryId: 'entry-123',
  accessedBy: 'user-999',
  accessPolicy: 'tenant',
  allowed: true
});
```

## Security Considerations

1. **Sensitive Data Detection**
   - Prevent sharing if entry contains sensitive data
   - Unless explicitly approved by admin
   - Auto-downgrade to private if detected

2. **Audit Trail**
   - Log all sharing operations
   - Log all access attempts (allowed and denied)
   - Immutable access records for compliance

3. **Default Private**
   - All entries private by default
   - Explicit sharing opt-in required
   - Prevents accidental exposure

4. **Rate Limiting**
   - Limit shared entry accesses per user/hour
   - Prevent abuse of shared cache
   - Alert on unusual patterns

5. **Encryption**
   - Shared entries stored in Redis with same encryption as private
   - No reduction in data protection
   - Tenant isolation maintained

## Performance Impact

- **Lookup overhead**: +2-5% for access control checks
- **Audit logging**: +1-3% (async batched writes)
- **Storage**: Minimal (sharing metadata ~200 bytes per entry)
- **Redis prefix**: Different key pattern for shared entries

## Testing Strategy

1. **Unit Tests**
   - Access control validation
   - Policy enforcement
   - Audit logging

2. **Integration Tests**
   - Cross-project retrieval
   - Access denial scenarios
   - Sensitive data protection
   - Audit trail completeness

3. **Security Tests**
   - Unauthorized access attempts
   - Policy bypass attempts
   - Sensitive data leakage

## Backwards Compatibility

- All entries default to `sharing.enabled: false`
- Existing code works unchanged
- Sharing is opt-in per entry
- No breaking changes to API

## Future Enhancements

- Delegated sharing (user A shares with user B)
- Time-limited sharing (expires at date)
- Usage quotas (max accesses)
- Collaborative caching (multiple projects contribute results)
- Sharing workflows/approvals
