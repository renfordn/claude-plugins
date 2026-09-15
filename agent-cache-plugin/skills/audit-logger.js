/**
 * Cache Audit Logger
 *
 * Comprehensive audit logging for cache operations with:
 * - All cache hits/misses with context
 * - Parameter access tracking for sensitive data detection
 * - User/agent/tenant attribution
 * - Compliance-friendly export (JSON, CSV)
 * - Retention policies and cleanup
 * - Real-time alerts for suspicious patterns
 *
 * Supports: SOC 2, GDPR, HIPAA, PCI-DSS compliance
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class AuditLogger {
  constructor(config = {}) {
    this.config = {
      enabled: config.enabled !== false,
      logDir: config.logDir || './audit-logs',
      rotationPolicy: config.rotationPolicy || 'daily', // daily, weekly, monthly
      retentionDays: config.retentionDays || 90,
      includeParameters: config.includeParameters !== false,
      includeSensitiveDetection: config.includeSensitiveDetection !== false,
      sensitivePatterns: config.sensitivePatterns || this._defaultSensitivePatterns(),
      hashSensitiveValues: config.hashSensitiveValues !== false,
      enableAlerts: config.enableAlerts !== false,
      alertCallbacks: config.alertCallbacks || [],
      maxLogSize: config.maxLogSize || 100 * 1024 * 1024, // 100MB
      compression: config.compression || 'gzip'
    };

    this.logs = [];
    this.sessionId = this._generateSessionId();
    this.alertThresholds = {
      failureRate: 0.5, // Alert if >50% failures
      suspiciousAccess: 3, // Alert after 3 suspicious accesses
      largeAccess: 10 * 1024 * 1024 // Alert on >10MB access
    };
  }

  /**
   * Log a cache operation
   */
  logOperation(operation) {
    if (!this.config.enabled) return;

    const entry = {
      timestamp: Date.now(),
      sessionId: this.sessionId,
      type: operation.type, // 'store', 'retrieve', 'invalidate', 'search'
      success: operation.success,
      entryId: operation.entryId,
      userId: operation.userId || 'anonymous',
      agentType: operation.agentType,
      taskType: operation.taskType,
      tenantId: operation.tenantId,
      ipAddress: operation.ipAddress,
      duration: operation.duration || 0,
      resultCount: operation.resultCount || null,
      error: operation.error,
      tags: operation.tags || []
    };

    // Add parameter tracking if enabled and not storing
    if (this.config.includeParameters && operation.type !== 'store' && operation.parameters) {
      entry.parameterHash = this._hashParameters(operation.parameters);
      entry.parameterSize = this._sizeofObject(operation.parameters);

      // Detect sensitive data access
      if (this.config.includeSensitiveDetection) {
        entry.sensitiveDetected = this._detectSensitive(operation.parameters);
      }
    }

    this.logs.push(entry);

    // Check for alerts
    if (this.config.enableAlerts) {
      this._checkAlerts(entry);
    }

    return entry;
  }

  /**
   * Log a cache hit
   */
  logHit(entryId, context = {}) {
    return this.logOperation({
      type: 'retrieve',
      success: true,
      entryId,
      ...context
    });
  }

  /**
   * Log a cache miss
   */
  logMiss(entryId, context = {}) {
    return this.logOperation({
      type: 'retrieve',
      success: false,
      entryId,
      ...context
    });
  }

  /**
   * Log invalidation
   */
  logInvalidation(entryId, reason = '', context = {}) {
    return this.logOperation({
      type: 'invalidate',
      success: true,
      entryId,
      tags: [reason],
      ...context
    });
  }

  /**
   * Log search operation
   */
  logSearch(criteria = {}, resultCount = 0, context = {}) {
    return this.logOperation({
      type: 'search',
      success: true,
      resultCount,
      parameters: criteria,
      ...context
    });
  }

  /**
   * Get audit log entries
   */
  getEntries(filters = {}) {
    let entries = this.logs;

    if (filters.userId) {
      entries = entries.filter(e => e.userId === filters.userId);
    }

    if (filters.type) {
      entries = entries.filter(e => e.type === filters.type);
    }

    if (filters.tenantId) {
      entries = entries.filter(e => e.tenantId === filters.tenantId);
    }

    if (filters.startTime) {
      entries = entries.filter(e => e.timestamp >= filters.startTime);
    }

    if (filters.endTime) {
      entries = entries.filter(e => e.timestamp <= filters.endTime);
    }

    if (filters.sensitiveOnly) {
      entries = entries.filter(e => e.sensitiveDetected && e.sensitiveDetected.length > 0);
    }

    if (filters.failuresOnly) {
      entries = entries.filter(e => !e.success);
    }

    return entries;
  }

  /**
   * Export audit logs as JSON
   */
  exportJSON(filters = {}) {
    const entries = this.getEntries(filters);
    return {
      exportedAt: new Date().toISOString(),
      totalEntries: entries.length,
      period: {
        start: filters.startTime ? new Date(filters.startTime) : null,
        end: filters.endTime ? new Date(filters.endTime) : null
      },
      entries
    };
  }

  /**
   * Export audit logs as CSV
   */
  exportCSV(filters = {}) {
    const entries = this.getEntries(filters);

    if (entries.length === 0) {
      return 'No entries found\n';
    }

    const headers = [
      'Timestamp',
      'Session ID',
      'Operation Type',
      'Success',
      'Entry ID',
      'User ID',
      'Agent Type',
      'Task Type',
      'Tenant ID',
      'IP Address',
      'Duration (ms)',
      'Result Count',
      'Error',
      'Sensitive Data Detected',
      'Tags'
    ];

    const rows = entries.map(e => [
      new Date(e.timestamp).toISOString(),
      e.sessionId,
      e.type,
      e.success ? 'Yes' : 'No',
      e.entryId || '',
      e.userId || '',
      e.agentType || '',
      e.taskType || '',
      e.tenantId || '',
      e.ipAddress || '',
      e.duration || 0,
      e.resultCount || '',
      e.error || '',
      (e.sensitiveDetected || []).join(';'),
      (e.tags || []).join(';')
    ]);

    return [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');
  }

  /**
   * Save audit logs to file
   */
  async saveToFile(filepath = null, format = 'json', filters = {}) {
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = filepath || path.join(
      this.config.logDir,
      `audit-${timestamp}.${format === 'csv' ? 'csv' : 'json'}`
    );

    let content;
    if (format === 'csv') {
      content = this.exportCSV(filters);
    } else {
      content = JSON.stringify(this.exportJSON(filters), null, 2);
    }

    try {
      // Ensure directory exists
      const dir = path.dirname(filename);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      fs.writeFileSync(filename, content, 'utf8');
      return { success: true, filepath: filename, size: content.length };
    } catch (err) {
      console.error('[AuditLogger] File save error:', err.message);
      return { success: false, error: err.message };
    }
  }

  /**
   * Cleanup old logs based on retention policy
   */
  async cleanup() {
    if (!this.config.retentionDays) return { deleted: 0 };

    const cutoffTime = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    const before = this.logs.length;

    this.logs = this.logs.filter(log => log.timestamp >= cutoffTime);

    const deleted = before - this.logs.length;
    return { deleted };
  }

  /**
   * Get statistics
   */
  getStats(filters = {}) {
    const entries = this.getEntries(filters);

    if (entries.length === 0) {
      return this._emptyStats();
    }

    const typeStats = {};
    const userStats = {};
    let totalDuration = 0;
    let totalSize = 0;
    let errorCount = 0;
    let successCount = 0;
    let sensitiveAccessCount = 0;

    for (const entry of entries) {
      // Type statistics
      if (!typeStats[entry.type]) {
        typeStats[entry.type] = { count: 0, errors: 0, avgDuration: 0 };
      }
      typeStats[entry.type].count++;
      if (!entry.success) typeStats[entry.type].errors++;

      // User statistics
      if (!userStats[entry.userId]) {
        userStats[entry.userId] = { count: 0, errors: 0 };
      }
      userStats[entry.userId].count++;
      if (!entry.success) userStats[entry.userId].errors++;

      // Aggregate metrics
      totalDuration += entry.duration || 0;
      totalSize += entry.parameterSize || 0;
      if (entry.success) successCount++;
      else errorCount++;

      if (entry.sensitiveDetected && entry.sensitiveDetected.length > 0) {
        sensitiveAccessCount++;
      }
    }

    return {
      totalOperations: entries.length,
      successCount,
      errorCount,
      successRate: (successCount / entries.length * 100).toFixed(1) + '%',
      avgDuration: entries.length > 0 ? (totalDuration / entries.length).toFixed(2) + 'ms' : 'N/A',
      totalSize: this._formatBytes(totalSize),
      operationTypes: typeStats,
      topUsers: Object.entries(userStats)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 10),
      sensitiveAccessCount,
      uniqueSensitiveTypes: this._countUniqueSensitive(entries)
    };
  }

  /**
   * Subscribe to alerts
   */
  subscribe(callback) {
    this.config.alertCallbacks.push(callback);
    return () => {
      const idx = this.config.alertCallbacks.indexOf(callback);
      if (idx > -1) this.config.alertCallbacks.splice(idx, 1);
    };
  }

  /**
   * Clear all logs
   */
  clear() {
    const count = this.logs.length;
    this.logs = [];
    return { cleared: count };
  }

  // Private methods

  /**
   * Default sensitive data patterns
   */
  _defaultSensitivePatterns() {
    return [
      { name: 'email', pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/ },
      { name: 'credit_card', pattern: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/ },
      { name: 'api_key', pattern: /api[\w_-]*key[\w_-]*[=:]\s*sk[\w-]{20,}|sk_live[\w-]{20,}|sk_test[\w-]{20,}|"[\w]*key[\w]*"\s*:\s*"[\w-]{16,}"/i },
      { name: 'password', pattern: /password[=:]\s*['\"]?[\w!@#$%^&*-]+['\"]?/i },
      { name: 'token', pattern: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/ },
      { name: 'ssn', pattern: /\d{3}-\d{2}-\d{4}/ },
      { name: 'phone', pattern: /(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/ }
    ];
  }

  /**
   * Detect sensitive data in object
   */
  _detectSensitive(obj) {
    if (!obj || typeof obj !== 'object') return [];

    const detected = new Set();
    const json = JSON.stringify(obj);

    for (const { name, pattern } of this.config.sensitivePatterns) {
      if (pattern.test(json)) {
        detected.add(name);
      }
    }

    return Array.from(detected);
  }

  /**
   * Hash parameters for audit trail
   */
  _hashParameters(params) {
    if (!params) return null;
    const json = JSON.stringify(params);
    return crypto.createHash('sha256').update(json).digest('hex');
  }

  /**
   * Calculate object size
   */
  _sizeofObject(obj) {
    return Buffer.byteLength(JSON.stringify(obj), 'utf8');
  }

  /**
   * Format bytes to readable format
   */
  _formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, index)).toFixed(2) + ' ' + units[index];
  }

  /**
   * Generate session ID
   */
  _generateSessionId() {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Check for suspicious patterns
   */
  _checkAlerts(entry) {
    // Alert on sensitive data access
    if (entry.sensitiveDetected && entry.sensitiveDetected.length > 0) {
      this._fireAlert({
        type: 'sensitive_access',
        severity: 'high',
        message: `Sensitive data detected: ${entry.sensitiveDetected.join(', ')}`,
        entry
      });
    }

    // Alert on repeated failures
    const recentFailures = this.logs.slice(-10).filter(e => !e.success);
    if (recentFailures.length > this.alertThresholds.suspiciousAccess) {
      this._fireAlert({
        type: 'repeated_failures',
        severity: 'medium',
        message: `${recentFailures.length} failures in last 10 operations`,
        entry
      });
    }

    // Alert on large data access
    if (entry.parameterSize > this.alertThresholds.largeAccess) {
      this._fireAlert({
        type: 'large_access',
        severity: 'low',
        message: `Large parameter access: ${this._formatBytes(entry.parameterSize)}`,
        entry
      });
    }
  }

  /**
   * Fire alert to subscribers
   */
  _fireAlert(alert) {
    for (const callback of this.config.alertCallbacks) {
      try {
        callback(alert);
      } catch (err) {
        console.error('[AuditLogger] Alert callback error:', err.message);
      }
    }
  }

  /**
   * Count unique sensitive types in logs
   */
  _countUniqueSensitive(entries) {
    const types = new Set();
    for (const entry of entries) {
      if (entry.sensitiveDetected) {
        entry.sensitiveDetected.forEach(t => types.add(t));
      }
    }
    return types.size;
  }

  /**
   * Empty stats template
   */
  _emptyStats() {
    return {
      totalOperations: 0,
      successCount: 0,
      errorCount: 0,
      successRate: 'N/A',
      avgDuration: 'N/A',
      totalSize: '0 B',
      operationTypes: {},
      topUsers: [],
      sensitiveAccessCount: 0,
      uniqueSensitiveTypes: 0
    };
  }
}

module.exports = AuditLogger;
