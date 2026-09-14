# Cross-Project Cache Sharing

## Overview

Enables safe cache sharing across multiple projects, teams, and users within an organization while maintaining strict privacy and access control boundaries.

**Key Features**:
- 🔒 Fine-grained access control (owner, project, tenant, public)
- 🏢 Organization and tenant isolation
- 👥 User-level allow/deny lists
- 📊 Share statistics and tracking
- ⚠️ Rate limiting for shared entry access
- 🔍 Sensitive data protection
- 📝 Comprehensive audit logging
- ⚡ Zero-overhead for private entries

## Access Policies

### Owner (Private)
- Only the entry creator can access
- Default policy for all new entries
- Maximum privacy
- Ideal for: Sensitive, proprietary, or experimental results

**Configuration**:
```javascript
await cache.share(entryId, {
  accessPolicy: 'owner',
  createdBy: 'user-123'
});
```

### Project
- Accessible to all members of the same project
- Requires user to be a project member
- Optional allow/deny lists for fine-tuning
- Ideal for: Team-specific computations, project-scoped data

**Configuration**:
```javascript
await cache.share(entryId, {
  accessPolicy: 'project',
  projectId: 'proj-456',
  createdBy: 'user-123'
});
```

### Tenant (Organization)
- Accessible to all users in the same organization
- Requires organization membership
- Supports explicit allow/deny lists
- Ideal for: Cross-team shared computations, org-wide knowledge

**Configuration**:
```javascript
await cache.share(entryId, {
  accessPolicy: 'tenant',
  tenantId: 'tenant-789',
  createdBy: 'user-123'
});
```

### Public
- Accessible to anyone with cache access
- No organization boundaries
- Maximum reach
- Ideal for: Non-sensitive, widely-applicable results

**Configuration**:
```javascript
await cache.share(entryId, {
  accessPolicy: 'public',
  createdBy: 'user-123'
});
```

## Installation & Setup

### Basic Configuration

```javascript
const CacheSharing = require('./skills/cache-sharing/CacheSharing');
const AuditLogger = require('./skills/audit-logger');

// With audit logging (recommended)
const auditLogger = new AuditLogger({ enableAlerts: true });
const sharing = new CacheSharing({
  enableSharing: true,
  defaultAccessPolicy: 'private',
  allowPublicSharing: true
}, auditLogger);

// Without audit logging
const sharing = new CacheSharing({
  enableSharing: true
});
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enableSharing` | boolean | `true` | Enable/disable sharing feature |
| `defaultAccessPolicy` | string | `'private'` | Default policy for new shares |
| `allowPublicSharing` | boolean | `false` | Allow public (org-wide) sharing |
| `requireApprovalForSharing` | boolean | `false` | Require admin approval for shares |
| `maxSharedEntriesPerUser` | number | `10000` | Max entries user can share |
| `autoDegradeIfSensitive` | boolean | `true` | Auto-block sharing of sensitive data |
| `restrictedTags` | array | `['confidential']` | Tags that block sharing |
| `shareAccessRateLimit` | number | `1000` | Max accesses per user per hour |

## Usage Examples

### Enable Sharing on Entry

```javascript
const entry = await cache.retrieve('entry-123');

// Share with organization
const result = await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  projectId: 'proj-456',
  tenantId: 'tenant-789',
  createdBy: 'user-123'
});

if (result.success) {
  console.log('Entry shared:', result.sharing);
  entry.sharing = result.sharing;
}
```

### Validate User Access

```javascript
const user = {
  id: 'user-456',
  tenantId: 'tenant-789',
  projects: ['proj-100', 'proj-200']
};

// Check if user can access shared entry
const access = await sharing.validateAccess(sharedEntry, user);

if (access.allowed) {
  console.log('Access granted to:', user.id);
  // Return entry to user
  return sharedEntry;
} else {
  console.log('Access denied:', access.reason);
  return null;
}
```

### Record Access for Audit

```javascript
// After user accesses shared entry
const recordResult = await sharing.recordAccess(entry, {
  id: 'user-456',
  tenantId: 'tenant-789'
});

if (!recordResult.allowed) {
  console.log('Rate limited:', recordResult.reason);
}
```

### Disable Sharing

```javascript
await sharing.disableSharing('entry-123', 'user-456');
console.log('Entry is now private');
```

### Manage Access Lists

```javascript
// Get who can access entry
const accessList = await sharing.getAccessList(entry);
console.log({
  policy: accessList.policy,
  sharedBy: accessList.sharedBy,
  allowedUsers: accessList.allowedUsers,
  accessCount: accessList.shareCount
});

// Update who can access
await sharing.updateAccessList(entry, 'user-123', {
  allowedUsers: ['user-456', 'user-789'],
  deniedUsers: ['user-999']
});
```

### Get Sharing Statistics

```javascript
const stats = sharing.getSharingStats();
console.log({
  totalSharedEntries: stats.totalSharedEntries,
  usersWithSharedEntries: stats.usersWithSharedEntries
});
```

### Filter Entries for User

```javascript
// All entries (mix of shared and private)
const allEntries = await cache.search({ tags: ['ml'] });

// Filter to only entries user can access
const userEntries = await sharing.filterForUser(allEntries, {
  id: 'user-456',
  tenantId: 'tenant-789',
  projects: ['proj-100']
});

console.log('User can access:', userEntries.length, 'entries');
```

## Security Considerations

### Sensitive Data Protection

Entries with restricted tags are prevented from sharing:

```javascript
const entry = {
  id: 'entry-123',
  prompt: 'Analyze customer data',
  output: {...},
  metadata: {
    tags: ['confidential']  // Restricted tag
  }
};

// This will fail
const result = await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  createdBy: 'user-123'
});

// result.error: 'Entry has restricted tags and cannot be shared'
```

### Explicit Allow Lists

For sensitive project data, use allow lists:

```javascript
await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  tenantId: 'tenant-789',
  createdBy: 'user-123',
  allowedUsers: ['user-456', 'user-789']  // Only these users
});

// Only user-456 and user-789 can access, even if in same org
```

### Rate Limiting

Prevent abuse of shared entries:

```javascript
// After 1000 accesses per hour, user is rate limited
const access = await sharing.recordAccess(entry, user);

if (!access.allowed) {
  // Temporarily deny access
  res.status(429).send('Too many requests');
}
```

### Audit Trail

All sharing operations are logged:

```javascript
// Logs entry when shared
// Logs every access to shared entry
// Logs access denials and rate limits
// Logs policy changes
```

## Integration with Cache Manager

### Complete Flow

```javascript
// 1. Initialize
const cache = new CacheManager({ backend: 'redis' });
const auditLogger = new AuditLogger();
const sharing = new CacheSharing({}, auditLogger);

// 2. Store entry
const result = await cache.store({
  prompt: 'Analyze dataset',
  output: { analysis: '...' },
  metadata: {
    agentType: 'analyzer',
    tags: ['ml', 'data']
  }
});

// 3. Enable sharing
const entry = await cache.retrieve(result.entryId);
await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  projectId: 'proj-456',
  tenantId: 'tenant-789',
  createdBy: 'user-123'
});

// 4. Return shared entry to user
const user = { id: 'user-456', tenantId: 'tenant-789' };
const access = await sharing.validateAccess(entry, user);

if (access.allowed) {
  await sharing.recordAccess(entry, user);
  return entry;
}
```

### Middleware Integration

```javascript
app.get('/cache/:entryId', async (req, res) => {
  const user = req.user;  // From auth
  const entry = await cache.retrieve(req.params.entryId);

  if (!entry) {
    return res.status(404).send('Not found');
  }

  // Check sharing permissions
  const access = await sharing.validateAccess(entry, user);
  if (!access.allowed) {
    return res.status(403).send(access.reason);
  }

  // Record access
  const recordResult = await sharing.recordAccess(entry, user);
  if (!recordResult.allowed) {
    return res.status(429).send('Rate limited');
  }

  res.json(entry);
});
```

## Best Practices

### 1. Default to Private
Always keep entries private unless explicitly sharing:

```javascript
// Good - private by default
const entry = await cache.retrieve(entryId);
// entry is private, only creator can access

// Bad - accidentally public
await sharing.enableSharing(entry, {
  accessPolicy: 'public'  // Don't do this without approval
});
```

### 2. Use Appropriate Policies
Match policy to data sensitivity:

```javascript
// Sensitive results
accessPolicy: 'owner'  // Only creator

// Team data
accessPolicy: 'project'  // Team members only

// General knowledge
accessPolicy: 'tenant'  // Organization only

// Non-sensitive, public
accessPolicy: 'public'  // Everyone
```

### 3. Monitor Sensitive Accesses
Subscribe to audit alerts:

```javascript
auditLogger.subscribe((alert) => {
  if (alert.type === 'shared_access' && 
      alert.entry.metadata.tags.includes('confidential')) {
    console.warn('Sensitive entry accessed:', alert.entry.id, 'by', alert.userId);
    // Alert security team
  }
});
```

### 4. Use Allow Lists for Controlled Sharing
When sharing with specific users:

```javascript
await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  tenantId: 'tenant-789',
  createdBy: 'user-123',
  allowedUsers: ['user-456', 'user-789']  // Explicit control
});
```

### 5. Disable Sharing When No Longer Needed
Clean up shared entries:

```javascript
// After analysis complete, make private again
await sharing.disableSharing(entryId, userId);
```

## Compliance & Audit

### GDPR Data Access Tracking
```javascript
// Get all accesses to entry
const accesses = auditLogger.getEntries({
  type: 'shared_entry_accessed',
  entryId: 'entry-123'
});
```

### Audit Report
```javascript
// Who has access to what
const stats = sharing.getSharingStats();

// Export access history
const report = auditLogger.exportJSON({
  startTime: Date.now() - 30 * 24 * 60 * 60 * 1000,
  type: 'shared_entry_accessed'
});
```

## Performance Considerations

- **Lookup overhead**: +2-5% for access control validation
- **Audit logging**: +1-3% (batched async writes)
- **Rate limiting**: O(1) with cleanup
- **Storage**: ~200 bytes per shared entry for metadata

## Troubleshooting

### Entry Not Accessible
```javascript
const access = await sharing.validateAccess(entry, user);
console.log('Reason:', access.reason);
// Check: different tenant, not project member, in denied list, rate limited
```

### Cannot Share Sensitive Data
```javascript
const result = await sharing.enableSharing(entry, {
  accessPolicy: 'tenant',
  createdBy: 'user-123'
});

if (!result.success) {
  console.log('Error:', result.error);
  // Entry has restricted tags - change tags or set accessPolicy: 'owner'
}
```

### Rate Limited
```javascript
const access = await sharing.recordAccess(entry, user);
if (!access.allowed) {
  // User has accessed 1000+ shared entries in last hour
  // Retry after some time
}
```

## See Also

- [AUDIT.md](../AUDIT.md) - Audit logging system
- [REDIS.md](../cache-storage/REDIS.md) - Distributed cache backend
- [DESIGN.md](./DESIGN.md) - Detailed architecture & design
