# Audit & Compliance Logging

## Overview

The Audit Logger provides comprehensive logging of all cache operations for compliance, security, and operational insights. It enables:

- **Complete audit trails** for SOC 2, GDPR, HIPAA, PCI-DSS compliance
- **Sensitive data detection** (emails, credit cards, API keys, passwords)
- **User/agent attribution** for accountability
- **Real-time alerts** for suspicious access patterns
- **Export in multiple formats** (JSON, CSV) for compliance reports
- **Retention policies** with automatic cleanup

**Key Features**:
- 🔐 Sensitive data pattern detection
- 📊 Operation tracking (store, retrieve, invalidate, search)
- 📈 Statistical analysis and reporting
- 🚨 Real-time alerts for security events
- 📁 File export with retention management
- 🔍 Flexible filtering and search

## Installation & Setup

### Basic Configuration

```javascript
const AuditLogger = require('./skills/audit-logger');

const logger = new AuditLogger({
  enabled: true,
  logDir: './audit-logs',
  retentionDays: 90,  // Keep logs for 90 days
  includeParameters: true,
  includeSensitiveDetection: true,
  enableAlerts: true
});
```

### With Cache Integration

```javascript
const CacheManager = require('./skills/cache-storage');
const AuditLogger = require('./skills/audit-logger');

const cache = new CacheManager({ backend: 'redis' });
const logger = new AuditLogger({ retentionDays: 90 });

// Log cache operations
cache.on('hit', (entryId, duration) => {
  logger.logHit(entryId, {
    userId: req.user?.id,
    agentType: req.agentType,
    duration
  });
});

cache.on('miss', (entryId, duration) => {
  logger.logMiss(entryId, {
    userId: req.user?.id,
    agentType: req.agentType,
    duration
  });
});
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable logging |
| `logDir` | string | `./audit-logs` | Directory for log files |
| `retentionDays` | number | `90` | Keep logs for N days |
| `includeParameters` | boolean | `true` | Include request parameters in logs |
| `includeSensitiveDetection` | boolean | `true` | Detect sensitive data |
| `sensitivePatterns` | array | Built-in patterns | Custom sensitive data patterns |
| `hashSensitiveValues` | boolean | `true` | Hash sensitive values in logs |
| `enableAlerts` | boolean | `true` | Enable real-time alerts |
| `alertCallbacks` | array | `[]` | Alert handler functions |
| `maxLogSize` | number | `100MB` | Max log file size before rotation |
| `compression` | string | `gzip` | Log compression method |

## Logging Operations

### Log Cache Hit

```javascript
logger.logHit('entry-123', {
  userId: 'user-456',
  agentType: 'analyzer',
  taskType: 'document-analysis',
  tenantId: 'tenant-789',
  ipAddress: '192.168.1.1',
  duration: 2.5
});
```

### Log Cache Miss

```javascript
logger.logMiss('entry-123', {
  userId: 'user-456',
  agentType: 'analyzer'
});
```

### Log Invalidation

```javascript
logger.logInvalidation('entry-123', 'manual_clear', {
  userId: 'admin-user',
  reason: 'data_refresh'
});
```

### Log Search Operation

```javascript
logger.logSearch(
  { tags: ['ml', 'ai'], agentType: 'analyzer' },
  5,  // result count
  { userId: 'user-456' }
);
```

## Sensitive Data Detection

### Built-in Patterns

The logger automatically detects:
- **Email addresses**: `user@example.com`
- **Credit cards**: `4532-1234-5678-9012`
- **Social Security**: `123-45-6789`
- **API keys**: `sk_live_1234567890abcdef`
- **Passwords**: `password=mysecretpass`
- **Bearer tokens**: `Bearer eyJhbGci...`
- **Phone numbers**: `(555) 123-4567`

### Custom Patterns

```javascript
const logger = new AuditLogger({
  sensitivePatterns: [
    { name: 'customer_id', pattern: /CUS-\d{8}/ },
    { name: 'internal_code', pattern: /CODE:[A-Z]{3}\d{4}/ }
  ]
});
```

### Detection in Action

```javascript
logger.logOperation({
  type: 'retrieve',
  success: true,
  parameters: { email: 'user@example.com', card: '4532-1234-5678-9012' }
});

const logs = logger.getEntries({ sensitiveOnly: true });
// Returns only operations accessing sensitive data
// logs[0].sensitiveDetected = ['email', 'credit_card']
```

## Filtering & Queries

### Filter by User

```javascript
const userLogs = logger.getEntries({
  userId: 'user-456'
});
```

### Filter by Operation Type

```javascript
const retrievals = logger.getEntries({
  type: 'retrieve'
});
```

### Filter by Tenant

```javascript
const tenantLogs = logger.getEntries({
  tenantId: 'tenant-789'
});
```

### Filter by Time Range

```javascript
const recent = logger.getEntries({
  startTime: Date.now() - 24 * 60 * 60 * 1000,  // Last 24h
  endTime: Date.now()
});
```

### Sensitive Data Only

```javascript
const suspicious = logger.getEntries({
  sensitiveOnly: true
});
```

### Failures Only

```javascript
const errors = logger.getEntries({
  failuresOnly: true
});
```

## Export & Reporting

### Export to JSON

```javascript
const report = logger.exportJSON({
  startTime: Date.now() - 7 * 24 * 60 * 60 * 1000,  // Last 7 days
  userId: 'specific-user'
});

console.log(report);
// {
//   exportedAt: "2026-08-26T...",
//   totalEntries: 1250,
//   period: { start: Date, end: Date },
//   entries: [...]
// }
```

### Export to CSV

```javascript
const csv = logger.exportCSV({
  startTime: Date.now() - 30 * 24 * 60 * 60 * 1000,  // Last 30 days
  tenantId: 'tenant-123'
});

// Save to file
fs.writeFileSync('audit-report.csv', csv);
```

### Save to File

```javascript
const result = await logger.saveToFile(
  './reports/audit-2026-08-26.json',
  'json',
  {
    startTime: Date.now() - 24 * 60 * 60 * 1000,
    userId: 'admin'
  }
);

console.log(result);
// { success: true, filepath: '...', size: 45821 }
```

## Statistics & Analysis

### Get Overall Statistics

```javascript
const stats = logger.getStats();

console.log(stats);
// {
//   totalOperations: 5000,
//   successCount: 4750,
//   errorCount: 250,
//   successRate: "95.0%",
//   avgDuration: "2.5ms",
//   totalSize: "15.2 MB",
//   operationTypes: {
//     retrieve: { count: 3000, errors: 50, avgDuration: 2.1 },
//     store: { count: 1500, errors: 0, avgDuration: 3.2 },
//     search: { count: 500, errors: 200, avgDuration: 8.5 }
//   },
//   topUsers: [
//     ['user-456', { count: 1200, errors: 5 }],
//     ['user-789', { count: 980, errors: 3 }]
//   ],
//   sensitiveAccessCount: 12,
//   uniqueSensitiveTypes: 3  // email, credit_card, api_key
// }
```

### Filter Statistics

```javascript
const stats = logger.getStats({
  startTime: Date.now() - 24 * 60 * 60 * 1000,
  userId: 'user-456'
});
```

## Alerts & Monitoring

### Subscribe to Alerts

```javascript
const unsubscribe = logger.subscribe((alert) => {
  console.log(`[${alert.severity}] ${alert.type}: ${alert.message}`);
  
  // Send to monitoring system
  if (alert.severity === 'high') {
    sendSlackAlert(alert);
  }
});
```

### Alert Types

**Sensitive Data Access** (Severity: HIGH)
```javascript
{
  type: 'sensitive_access',
  severity: 'high',
  message: 'Sensitive data detected: email, credit_card',
  entry: { ... }
}
```

**Repeated Failures** (Severity: MEDIUM)
```javascript
{
  type: 'repeated_failures',
  severity: 'medium',
  message: '5 failures in last 10 operations',
  entry: { ... }
}
```

**Large Data Access** (Severity: LOW)
```javascript
{
  type: 'large_access',
  severity: 'low',
  message: 'Large parameter access: 12.5 MB',
  entry: { ... }
}
```

### Unsubscribe from Alerts

```javascript
unsubscribe();  // Stop receiving alerts
```

## Compliance Use Cases

### SOC 2 Audit Trail

```javascript
// Maintain complete audit trail for SOC 2
const logger = new AuditLogger({
  retentionDays: 365,  // 1 year retention
  includeParameters: true,
  includeSensitiveDetection: true,
  enableAlerts: true
});

// Export monthly for compliance review
const monthly = await logger.saveToFile(
  `./compliance/audit-${month}.json`,
  'json'
);
```

### GDPR Data Access Log

```javascript
// Track all access to personal data
const gdprLogs = logger.getEntries({
  sensitiveOnly: true,
  startTime: compliancePeriodStart,
  endTime: compliancePeriodEnd
});

// Export for data subject access requests
const report = logger.exportJSON({ sensitiveOnly: true });
await logger.saveToFile('./gdpr/dsar-report.json', 'json');
```

### HIPAA Protected Health Information

```javascript
// Alert on any PHI access
logger.subscribe((alert) => {
  if (alert.type === 'sensitive_access') {
    // Log immediately for HIPAA audit
    logToHIPAAAuditSystem(alert);
    
    // Alert compliance officer
    notifyComplianceOfficer(alert);
  }
});
```

### PCI-DSS Payment Card Compliance

```javascript
// Never log full card numbers
const logger = new AuditLogger({
  sensitivePatterns: [
    { name: 'full_card', pattern: /\d{4}-\d{4}-\d{4}-\d{4}/ }
  ],
  hashSensitiveValues: true  // Hash all sensitive values
});
```

## Maintenance

### Cleanup Old Logs

```javascript
// Manual cleanup (automatic also runs based on retentionDays)
const result = await logger.cleanup();
console.log(`Deleted ${result.deleted} old log entries`);
```

### Clear All Logs

```javascript
const result = logger.clear();
console.log(`Cleared ${result.cleared} log entries`);
```

### Rotate Logs

```javascript
// Save current logs and start fresh
await logger.saveToFile('./archive/audit-archive.json', 'json');
logger.clear();
```

## Best Practices

1. **Always log user/tenant context** for accountability
   ```javascript
   logger.logHit(entryId, {
     userId: req.user?.id,
     tenantId: req.tenant?.id
   });
   ```

2. **Use custom patterns for domain-specific data**
   ```javascript
   // Add company-specific PII patterns
   ```

3. **Enable real-time alerts for sensitive data**
   ```javascript
   logger.subscribe((alert) => {
     if (alert.type === 'sensitive_access') {
       // Take immediate action
     }
   });
   ```

4. **Regular compliance reports**
   ```javascript
   // Weekly export for compliance team
   const report = logger.exportJSON({
     startTime: Date.now() - 7 * 24 * 60 * 60 * 1000
   });
   ```

5. **Monitor alert patterns**
   ```javascript
   // Track which users access sensitive data
   // Track which operations fail most
   // Identify unusual access patterns
   ```

6. **Archive logs securely**
   ```javascript
   // Export to encrypted storage
   // Keep offline backup for compliance
   // Document chain of custody
   ```

## Compliance Mapping

| Standard | Requirement | Audit Logger Support |
|----------|-------------|----------------------|
| SOC 2 | Audit trails | Complete operation logging ✅ |
| SOC 2 | Access control | User attribution ✅ |
| GDPR | Data access log | Sensitive data detection ✅ |
| GDPR | DSAR | Export filtering ✅ |
| HIPAA | Audit log | PHI detection alerts ✅ |
| HIPAA | Access control | User/tenant tracking ✅ |
| PCI-DSS | Card data logging | Sensitive detection ✅ |
| PCI-DSS | Audit retention | Configurable retention ✅ |

## Performance Considerations

- **Minimal overhead**: <1ms per operation logged
- **Memory efficient**: Logs held in memory (export to file for long-term)
- **Automatic cleanup**: Old logs removed based on retention policy
- **Batch export**: Export large log sets without loading all in memory

## Troubleshooting

### Alert Not Firing

**Issue**: Configured alerts not triggering  
**Solution**:
```javascript
// Verify alerts enabled
logger.config.enableAlerts = true;

// Check callback subscription
logger.config.alertCallbacks.length > 0
```

### Sensitive Data Not Detected

**Issue**: Expected sensitive data patterns not matching  
**Solution**:
```javascript
// Verify pattern is in sensitivePatterns
// Test pattern manually
const pattern = /your-pattern/;
pattern.test(testData);

// Add custom pattern if needed
```

### Log File Issues

**Issue**: Cannot save logs to file  
**Solution**:
```javascript
// Check directory permissions
// Ensure logDir path is valid
// Verify disk space available
```

## See Also

- [REDIS.md](./cache-storage/REDIS.md) - Distributed cache backend
- [DASHBOARD.md](./cache-validation/DASHBOARD.md) - Metrics dashboard
- [PERSISTENCE.md](./cache-storage/PERSISTENCE.md) - Storage backends
